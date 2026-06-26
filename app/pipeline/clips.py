"""Mini-clips animados (WebP) alrededor del mejor frame de cada aparición.

Se generan tras el reconocimiento, releyendo el video alrededor del instante de
mayor similitud. WebP animado se reproduce en loop nativo dentro de un ``<img>``
del frontend, sin depender de códecs de ``<video>`` ni de ffmpeg.
"""

from __future__ import annotations

import logging
from pathlib import Path

import cv2
import numpy as np
from PIL import Image

from .ranges import AppearanceRange

logger = logging.getLogger("facehunt2.clips")


def _crop_region(
    h: int, w: int, bbox: tuple[int, int, int, int] | None,
    margin: float, aspect: float,
) -> tuple[int, int, int, int]:
    """Región fija (x1,y1,x2,y2) centrada en la cara, expandida a ``aspect``.

    Es estable durante todo el clip (no sigue a la cara): un margen amplio deja
    que la persona se mueva sin salirse del recuadro en ~2 s.
    """
    if bbox is None:
        return 0, 0, w, h
    x1, y1, x2, y2 = bbox
    bw, bh = x2 - x1, y2 - y1
    mx, my = int(bw * margin), int(bh * margin)
    cx1, cy1 = max(0, x1 - mx), max(0, y1 - my)
    cx2, cy2 = min(w, x2 + mx), min(h, y2 + my)
    cw, ch = cx2 - cx1, cy2 - cy1
    if cw <= 0 or ch <= 0:
        return 0, 0, w, h
    if cw / ch < aspect:
        tw = min(w, int(round(ch * aspect)))
        cc = (cx1 + cx2) / 2
        cx1 = int(max(0, min(cc - tw / 2, w - tw)))
        cx2 = cx1 + tw
    else:
        th = min(h, int(round(cw / aspect)))
        cc = (cy1 + cy2) / 2
        cy1 = int(max(0, min(cc - th / 2, h - th)))
        cy2 = cy1 + th
    return cx1, cy1, cx2, cy2


def _read_window(
    cap: cv2.VideoCapture, src_fps: float, center_ts: float,
    bbox: tuple[int, int, int, int] | None,
    *, seconds: float, fps_target: int, max_side: int, aspect: float,
) -> list[Image.Image]:
    """Lee una ventana de frames alrededor de ``center_ts`` y los recorta/escala.

    Devuelve una lista de imágenes PIL (RGB) listas para el WebP animado.
    """
    start_ts = max(0.0, center_ts - seconds / 2.0)
    start_frame = int(start_ts * src_fps)
    n_to_read = max(1, int(seconds * src_fps))
    step = max(1, round(src_fps / fps_target))

    cap.set(cv2.CAP_PROP_POS_FRAMES, start_frame)
    region: tuple[int, int, int, int] | None = None
    out: list[Image.Image] = []
    for i in range(n_to_read):
        ok, frame = cap.read()
        if not ok:
            break
        if i % step != 0:
            continue
        if region is None:
            h, w = frame.shape[:2]
            region = _crop_region(h, w, bbox, margin=1.0, aspect=aspect)
        rx1, ry1, rx2, ry2 = region
        crop = frame[ry1:ry2, rx1:rx2]
        if crop.size == 0:
            crop = frame
        ch, cw = crop.shape[:2]
        longest = max(ch, cw)
        if longest > max_side:
            s = max_side / longest
            crop = cv2.resize(crop, (int(cw * s), int(ch * s)), interpolation=cv2.INTER_AREA)
        out.append(Image.fromarray(cv2.cvtColor(crop, cv2.COLOR_BGR2RGB)))
        if len(out) >= 30:  # cota de tamaño del clip
            break
    return out


def generate_clips(
    video_path: str,
    ranges: list[AppearanceRange],
    out_dir: Path,
    *,
    prefix: str = "r",
    seconds: float = 2.0,
    fps_target: int = 12,
    max_side: int = 360,
    aspect: float = 4 / 3,
) -> None:
    """Genera un WebP animado por rango y setea ``range.clip`` con su nombre.

    Abre el video una sola vez y busca el instante de cada rango. Best-effort:
    si un clip falla, se omite (la tarjeta cae al thumbnail estático).
    """
    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        logger.warning("No pude abrir el video para generar clips: %s", video_path)
        return

    src_fps = cap.get(cv2.CAP_PROP_FPS)
    if not src_fps or src_fps <= 1.0:
        src_fps = 25.0

    out_dir.mkdir(parents=True, exist_ok=True)
    duration_ms = int(round(1000.0 / fps_target))
    made = 0
    try:
        for i, r in enumerate(ranges):
            try:
                frames = _read_window(
                    cap, src_fps, r.best_timestamp, r.best_bbox,
                    seconds=seconds, fps_target=fps_target,
                    max_side=max_side, aspect=aspect,
                )
                if not frames:
                    continue
                name = f"{prefix}_{i:04d}.webp"
                frames[0].save(
                    str(out_dir / name),
                    format="WEBP",
                    save_all=True,
                    append_images=frames[1:],
                    duration=duration_ms,
                    loop=0,
                    quality=70,
                    method=4,
                )
                r.clip = name
                made += 1
            except Exception:  # noqa: BLE001 - un clip que falla no aborta el job
                logger.debug("Clip omitido para rango %d", i, exc_info=True)
    finally:
        cap.release()
    logger.info("Clips generados: %d/%d", made, len(ranges))
