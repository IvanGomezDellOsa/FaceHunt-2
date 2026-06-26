"""Reconocimiento facial sobre el stream de frames + agrupado en rangos.

Compara cada cara detectada contra el embedding de referencia (similitud
coseno). Los segundos con match se agrupan en *rangos de aparición* (con
tolerancia de hueco), cada uno con un thumbnail y la confianza del mejor frame.
"""

from __future__ import annotations

import logging
import threading
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

import cv2
import numpy as np

from ..config import settings
from .engine import cosine_similarity, engine
from .frame_reader import FrameReader
from .ranges import AppearanceRange, MatchPoint, build_ranges
from .tracker import FaceObs, FaceTracker

logger = logging.getLogger("facehunt2.recognizer")


# Callbacks de progreso / match en vivo.
ProgressCb = Callable[[int, int, int], None]   # (procesados, total, matches)
MatchCb = Callable[[MatchPoint], None]


@dataclass
class RecognitionResult:
    ranges: list[AppearanceRange] = field(default_factory=list)
    processed: int = 0
    total: int = 0
    cancelled: bool = False
    fps: float = 0.0
    duration: float = 0.0
    faces_detected: int = 0          # total de caras vistas (diagnóstico)
    best_similarity: float = 0.0     # mejor similitud observada (calibración)


def _save_thumbnail(
    frame_bgr: np.ndarray,
    bbox: tuple[int, int, int, int],
    out_path: Path,
    margin: float = 0.6,
    max_side: int = 360,
    aspect: float = 4 / 3,
    draw_box: bool = True,
) -> None:
    """Recorta la cara con contexto y guarda un thumbnail JPG.

    El recorte se expande a la proporción ``aspect`` de la tarjeta (sin salirse
    del frame) para llenar la preview con mínimas barras negras. Si ``draw_box``
    está activo, dibuja un recuadro verde sobre el bbox exacto (look "detección").
    """
    h, w = frame_bgr.shape[:2]
    x1, y1, x2, y2 = bbox
    bw, bh = x2 - x1, y2 - y1
    mx, my = int(bw * margin), int(bh * margin)
    cx1, cy1 = max(0, x1 - mx), max(0, y1 - my)
    cx2, cy2 = min(w, x2 + mx), min(h, y2 + my)

    # Expande el recorte a la proporción objetivo (centrado en la cara) para que
    # encaje en la tarjeta; se recorta a los bordes del frame si no hay margen.
    cw0, ch0 = cx2 - cx1, cy2 - cy1
    if cw0 > 0 and ch0 > 0:
        if cw0 / ch0 < aspect:
            target_w = min(w, int(round(ch0 * aspect)))
            ccx = (cx1 + cx2) / 2
            cx1 = int(max(0, min(ccx - target_w / 2, w - target_w)))
            cx2 = cx1 + target_w
        else:
            target_h = min(h, int(round(cw0 / aspect)))
            ccy = (cy1 + cy2) / 2
            cy1 = int(max(0, min(ccy - target_h / 2, h - target_h)))
            cy2 = cy1 + target_h

    crop = frame_bgr[cy1:cy2, cx1:cx2].copy()
    if crop.size == 0:
        crop = frame_bgr.copy()
        cx1, cy1 = 0, 0

    if draw_box:
        thick = max(2, round(min(crop.shape[:2]) * 0.012))
        cv2.rectangle(
            crop,
            (x1 - cx1, y1 - cy1), (x2 - cx1, y2 - cy1),
            (0, 220, 0), thick, lineType=cv2.LINE_AA,
        )

    # Normaliza el tamaño: baja los recortes grandes y sube los muy chicos para
    # que el thumbnail (y su recuadro) se vea consistente en la UI.
    ch, cw = crop.shape[:2]
    longest = max(ch, cw)
    min_side = 220
    if longest > max_side:
        scale = max_side / longest
    elif longest < min_side:
        scale = min_side / longest
    else:
        scale = 1.0
    if scale != 1.0:
        interp = cv2.INTER_AREA if scale < 1.0 else cv2.INTER_CUBIC
        crop = cv2.resize(crop, (int(cw * scale), int(ch * scale)), interpolation=interp)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    cv2.imwrite(str(out_path), crop, [cv2.IMWRITE_JPEG_QUALITY, 88])


def recognize(
    reader: FrameReader,
    reference: np.ndarray,
    *,
    threshold: float,
    merge_gap: float,
    min_face_px: int,
    thumbnail_dir: Path,
    thumbnail_prefix: str = "thumb",
    on_progress: ProgressCb | None = None,
    on_match: MatchCb | None = None,
    stop_event: threading.Event | None = None,
) -> RecognitionResult:
    """Procesa el video y devuelve los rangos de aparición.

    Con ``settings.use_tracking`` (por defecto), agrupa las caras en tracklets,
    matchea sobre el embedding agregado y recupera frames degradados de un
    tracklet confirmado (mayor recall). Si se desactiva, cae a un análisis
    frame-a-frame independiente. El thumbnail de cada rango es el frame de mayor
    similitud.
    """
    matches: list[MatchPoint] = []
    crops: dict[float, np.ndarray] = {}  # best_timestamp -> frame del thumbnail
    crops_bbox: dict[float, tuple[int, int, int, int]] = {}

    total = reader.total_samples
    counters = {"processed": 0, "faces": 0, "best": 0.0}

    secondary = max(0.0, threshold - settings.track_secondary_margin)
    tracker = FaceTracker(
        reference,
        threshold=threshold,
        secondary_threshold=secondary,
        iou_thresh=settings.track_iou_thresh,
        appear_thresh=settings.track_appear_thresh,
        max_gap_seconds=merge_gap,
    )

    def absorb(closed) -> None:
        """Vuelca los tracklets confirmados en matches + frames de thumbnail."""
        for ct in closed:
            if not ct.is_match:
                continue
            for p in ct.match_points(secondary):
                mpoint = MatchPoint(p.timestamp, p.sim_ref, p.index)
                matches.append(mpoint)
                if on_match is not None:
                    on_match(mpoint)
            if ct.best_frame is not None:
                crops[ct.best_timestamp] = ct.best_frame
                crops_bbox[ct.best_timestamp] = ct.best_bbox

    def process_frame(sample) -> None:
        faces = engine.detect(sample.frame, min_face_px=min_face_px)
        counters["faces"] += len(faces)

        if settings.use_tracking:
            obs: list[FaceObs] = []
            for f in faces:
                sim = float(np.dot(reference, f.embedding))
                counters["best"] = max(counters["best"], sim)
                obs.append(FaceObs(f.bbox, f.embedding, f.quality, sim, frame=sample.frame))
            absorb(tracker.update(sample.timestamp, sample.index, obs))
        else:
            best_score, best_bbox = -1.0, None
            for f in faces:
                sim = cosine_similarity(reference, f.embedding)
                if sim > best_score:
                    best_score, best_bbox = sim, f.bbox
            counters["best"] = max(counters["best"], best_score)
            if best_score >= threshold and best_bbox is not None:
                point = MatchPoint(sample.timestamp, best_score, sample.index)
                matches.append(point)
                crops[sample.timestamp] = sample.frame
                crops_bbox[sample.timestamp] = best_bbox
                if on_match is not None:
                    on_match(point)

        counters["processed"] += 1
        if on_progress is not None:
            on_progress(counters["processed"], total, len(matches))

    def build_result(cancelled: bool) -> RecognitionResult:
        ranges = _finalize(matches, merge_gap, crops, crops_bbox,
                           thumbnail_dir, thumbnail_prefix)
        logger.info(
            "Reconocimiento: frames=%d caras=%d mejor_similitud=%.3f umbral=%.2f "
            "rangos=%d tracking=%s",
            counters["processed"], counters["faces"], counters["best"],
            threshold, len(ranges), settings.use_tracking,
        )
        return RecognitionResult(
            ranges=ranges,
            processed=counters["processed"],
            total=total,
            cancelled=cancelled,
            fps=reader.fps,
            duration=reader.duration,
            faces_detected=counters["faces"],
            best_similarity=counters["best"],
        )

    for sample in reader.stream():
        if stop_event is not None and stop_event.is_set():
            reader.stop()
            absorb(tracker.finalize())
            return build_result(cancelled=True)
        process_frame(sample)

    absorb(tracker.finalize())
    return build_result(cancelled=False)


def _finalize(
    matches: list[MatchPoint],
    merge_gap: float,
    crops: dict[float, np.ndarray],
    crops_bbox: dict[float, tuple[int, int, int, int]],
    thumbnail_dir: Path,
    prefix: str,
) -> list[AppearanceRange]:
    """Construye los rangos y escribe un thumbnail por rango."""
    ranges = build_ranges(matches, merge_gap)
    for i, r in enumerate(ranges):
        frame = crops.get(r.best_timestamp)
        bbox = crops_bbox.get(r.best_timestamp)
        if frame is not None and bbox is not None:
            name = f"{prefix}_{i:04d}.jpg"
            _save_thumbnail(
                frame, bbox, thumbnail_dir / name, draw_box=settings.draw_face_box
            )
            r.thumbnail = name
            r.best_bbox = bbox  # el generador de clips recorta alrededor de esto
    return ranges
