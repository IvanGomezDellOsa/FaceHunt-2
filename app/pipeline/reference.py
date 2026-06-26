"""Construcción del embedding de referencia a partir de una o más fotos."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path

import cv2
import numpy as np

from ..config import settings
from .engine import DetectedFace, engine

logger = logging.getLogger("facehunt2.reference")

_VALID_EXT = {".jpg", ".jpeg", ".png", ".webp", ".bmp"}


def _maybe_upscale(img: np.ndarray, min_side: int) -> np.ndarray:
    """Reescala hacia arriba imágenes chicas para que el detector las vea mejor."""
    h, w = img.shape[:2]
    longest = max(h, w)
    if longest >= min_side:
        return img
    scale = min_side / longest
    return cv2.resize(
        img, (int(w * scale), int(h * scale)), interpolation=cv2.INTER_CUBIC
    )


@dataclass
class ReferenceResult:
    ok: bool
    message: str
    embedding: np.ndarray | None = None
    num_images: int = 0
    multiple_faces_warning: bool = False


def _imread_unicode(path: str) -> np.ndarray | None:
    """Lee una imagen tolerando rutas con caracteres no-ASCII (Windows)."""
    try:
        data = np.fromfile(path, dtype=np.uint8)
        if data.size == 0:
            return None
        return cv2.imdecode(data, cv2.IMREAD_COLOR)
    except Exception:
        return None


def _largest_face(faces: list[DetectedFace]) -> DetectedFace:
    return max(faces, key=lambda f: f.width * f.height)


def build_reference(image_paths: list[str]) -> ReferenceResult:
    """Extrae y promedia el embedding de referencia.

    - Con varias fotos de la misma persona, promedia los embeddings (mayor
      robustez ante ángulo/iluminación) y re-normaliza.
    - Si una imagen tiene varias caras, usa la más grande y marca un aviso.
    """
    if not image_paths:
        return ReferenceResult(False, "No se proporcionó ninguna imagen de referencia.")

    # Detector permisivo y grande SÓLO para la referencia (más fácil de aceptar).
    engine.configure_detector(settings.ref_det_size, settings.ref_det_thresh)

    embeddings: list[np.ndarray] = []
    multiple = False

    for path in image_paths:
        p = Path(path)
        if not p.exists():
            return ReferenceResult(False, f"La imagen no existe: {p.name}")
        if p.suffix.lower() not in _VALID_EXT:
            return ReferenceResult(
                False, "Formatos aceptados: JPG, PNG, JPEG, WebP o BMP."
            )

        img = _imread_unicode(str(p))
        if img is None:
            return ReferenceResult(
                False, f"No se pudo leer la imagen (¿corrupta?): {p.name}"
            )

        img = _maybe_upscale(img, settings.ref_min_side)
        faces = engine.detect(img)
        if not faces:
            return ReferenceResult(
                False,
                f"No se detectó ninguna cara en {p.name}. Usá una foto frontal y nítida.",
            )
        if len(faces) > 1:
            multiple = True
        embeddings.append(_largest_face(faces).embedding)

    # Con varias fotos: verificar que sean de la MISMA persona. Si la similitud
    # entre alguna pareja es muy baja, son personas distintas -> error claro.
    if len(embeddings) > 1:
        import itertools

        min_sim = min(
            float(np.dot(a, b)) for a, b in itertools.combinations(embeddings, 2)
        )
        if min_sim < settings.ref_same_person_min:
            return ReferenceResult(
                False,
                "Las fotos de referencia parecen ser de personas distintas. "
                "Usá varias fotos de la MISMA persona (distintos ángulos o luz).",
            )

    avg = np.mean(np.stack(embeddings, axis=0), axis=0)
    avg = avg / (np.linalg.norm(avg) + 1e-9)

    n = len(embeddings)
    if multiple:
        msg = (
            f"Referencia lista ({n} imagen/es). Aviso: alguna foto tenía varias "
            "caras; se usó la más grande."
        )
    else:
        msg = f"Referencia válida ({n} imagen/es, 1 cara)."

    return ReferenceResult(
        ok=True,
        message=msg,
        embedding=avg.astype(np.float32),
        num_images=n,
        multiple_faces_warning=multiple,
    )
