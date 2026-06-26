"""Seguimiento de caras entre frames + agregación temporal.

Asocia detecciones de frames sucesivos en *tracklets* combinando solapamiento
espacial (IoU) y similitud de apariencia (coseno). Por cada tracklet calcula un
embedding agregado ponderado por calidad y decide si corresponde a la referencia.

Recall: confirma un tracklet si su mejor frame O su embedding agregado superan el
umbral, y luego recupera del mismo tracklet los frames degradados (por debajo del
umbral pero >= umbral secundario), que un análisis frame-a-frame perdería.

Módulo de lógica pura (numpy, sin cv2/onnx): testeable de forma aislada.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np

Bbox = tuple[int, int, int, int]


def iou(a: Bbox, b: Bbox) -> float:
    """Intersection-over-Union entre dos cajas (x1, y1, x2, y2)."""
    ax1, ay1, ax2, ay2 = a
    bx1, by1, bx2, by2 = b
    ix1, iy1 = max(ax1, bx1), max(ay1, by1)
    ix2, iy2 = min(ax2, bx2), min(ay2, by2)
    iw, ih = max(0, ix2 - ix1), max(0, iy2 - iy1)
    inter = iw * ih
    if inter == 0:
        return 0.0
    area_a = max(0, ax2 - ax1) * max(0, ay2 - ay1)
    area_b = max(0, bx2 - bx1) * max(0, by2 - by1)
    union = area_a + area_b - inter
    return inter / union if union > 0 else 0.0


@dataclass
class FaceObs:
    """Una cara observada en un frame, lista para el tracker."""
    bbox: Bbox
    embedding: np.ndarray   # 512-d, L2-normalizado
    quality: float          # peso para la agregación (norma de la feature)
    sim_ref: float          # similitud coseno contra la referencia
    frame: Any = None       # frame BGR opcional (para el thumbnail); el tracker no lo procesa


@dataclass
class TrackPoint:
    timestamp: float
    index: int
    sim_ref: float
    bbox: Bbox


@dataclass
class ClosedTrack:
    points: list[TrackPoint]
    aggregated_sim: float
    best_sim: float
    best_timestamp: float
    best_index: int
    best_bbox: Bbox
    best_frame: Any
    is_match: bool

    def match_points(self, secondary_threshold: float) -> list[TrackPoint]:
        """Frames a contar como aparición: si el track matcheó, todos los que
        superen el umbral secundario (recupera frames degradados confirmados)."""
        if not self.is_match:
            return []
        return [p for p in self.points if p.sim_ref >= secondary_threshold]


class _ActiveTrack:
    """Tracklet en construcción (estado mutable interno del tracker)."""

    def __init__(self, ts: float, index: int, obs: FaceObs) -> None:
        self.points: list[TrackPoint] = [TrackPoint(ts, index, obs.sim_ref, obs.bbox)]
        self.last_ts = ts
        self.last_bbox = obs.bbox
        self._sum_q_emb = obs.embedding.astype(np.float32) * obs.quality
        self._sum_q = obs.quality
        self.best_sim = obs.sim_ref
        self.best = (ts, index, obs.bbox, obs.frame)

    def mean_embedding(self) -> np.ndarray:
        v = self._sum_q_emb / (self._sum_q + 1e-9)
        return v / (np.linalg.norm(v) + 1e-9)

    def add(self, ts: float, index: int, obs: FaceObs) -> None:
        self.points.append(TrackPoint(ts, index, obs.sim_ref, obs.bbox))
        self.last_ts = ts
        self.last_bbox = obs.bbox
        self._sum_q_emb = self._sum_q_emb + obs.embedding.astype(np.float32) * obs.quality
        self._sum_q += obs.quality
        if obs.sim_ref > self.best_sim:
            self.best_sim = obs.sim_ref
            self.best = (ts, index, obs.bbox, obs.frame)


class FaceTracker:
    """Agrupa observaciones de caras en tracklets y decide cuáles matchean.

    Uso: ``update(ts, index, faces)`` por cada frame muestreado (devuelve los
    tracklets que se cerraron en ese paso); ``finalize()`` al terminar.
    """

    def __init__(
        self,
        reference: np.ndarray,
        *,
        threshold: float,
        secondary_threshold: float,
        iou_thresh: float = 0.3,
        appear_thresh: float = 0.45,
        max_gap_seconds: float = 2.0,
    ) -> None:
        self.reference = reference.astype(np.float32)
        self.threshold = threshold
        self.secondary_threshold = secondary_threshold
        self.iou_thresh = iou_thresh
        self.appear_thresh = appear_thresh
        self.max_gap_seconds = max_gap_seconds
        self._active: list[_ActiveTrack] = []

    def update(self, timestamp: float, index: int, faces: list[FaceObs]) -> list[ClosedTrack]:
        # 1) Cerrar tracks que llevan demasiado tiempo sin actualizarse.
        closed: list[ClosedTrack] = []
        still: list[_ActiveTrack] = []
        for tr in self._active:
            if timestamp - tr.last_ts > self.max_gap_seconds:
                closed.append(self._close(tr))
            else:
                still.append(tr)
        self._active = still

        # 2) Asociar caras a tracks por apariencia (coseno) y/o IoU. Greedy por
        #    score descendente; cada cara y cada track se usan una sola vez.
        means = [tr.mean_embedding() for tr in self._active]
        pairs: list[tuple[float, int, int]] = []
        for fi, face in enumerate(faces):
            for ti, tr in enumerate(self._active):
                ap = float(np.dot(face.embedding, means[ti]))
                ov = iou(face.bbox, tr.last_bbox)
                if ap >= self.appear_thresh or ov >= self.iou_thresh:
                    pairs.append((ap + ov, fi, ti))
        pairs.sort(reverse=True)
        used_f: set[int] = set()
        used_t: set[int] = set()
        for _, fi, ti in pairs:
            if fi in used_f or ti in used_t:
                continue
            self._active[ti].add(timestamp, index, faces[fi])
            used_f.add(fi)
            used_t.add(ti)

        # 3) Caras sin asociar -> nuevos tracks.
        for fi, face in enumerate(faces):
            if fi not in used_f:
                self._active.append(_ActiveTrack(timestamp, index, face))

        return closed

    def finalize(self) -> list[ClosedTrack]:
        closed = [self._close(tr) for tr in self._active]
        self._active = []
        return closed

    def _close(self, tr: _ActiveTrack) -> ClosedTrack:
        agg = float(np.dot(self.reference, tr.mean_embedding()))
        is_match = tr.best_sim >= self.threshold or agg >= self.threshold
        bt, bi, bb, bf = tr.best
        return ClosedTrack(
            points=tr.points,
            aggregated_sim=agg,
            best_sim=tr.best_sim,
            best_timestamp=bt,
            best_index=bi,
            best_bbox=bb,
            best_frame=bf,
            is_match=is_match,
        )
