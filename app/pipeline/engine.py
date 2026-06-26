"""Motor de detección + embeddings faciales sobre InsightFace / ONNXRuntime.

Encapsula el pack configurado (por defecto ``antelopev2``: detector SCRFD +
ArcFace ResNet100 @ Glint360K, 512-d). Selecciona el mejor execution provider
disponible (CUDA → DirectML → CPU) según la build de onnxruntime instalada.

La carga del modelo es perezosa y thread-safe.
"""

from __future__ import annotations

import logging
import shutil
import threading
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from ..config import settings

logger = logging.getLogger("facehunt2.engine")


def flatten_model_dir(model_dir: Path) -> bool:
    """Corrige el zip de algunos packs (p. ej. antelopev2) que se descomprime
    con una carpeta anidada ``<name>/<name>/*.onnx``.

    Mueve los ``.onnx`` un nivel hacia arriba. Devuelve True si reorganizó algo.
    """
    nested = model_dir / model_dir.name
    if not nested.is_dir():
        return False
    moved = False
    for item in nested.iterdir():
        dest = model_dir / item.name
        if not dest.exists():
            shutil.move(str(item), str(dest))
            moved = True
    try:
        nested.rmdir()
    except OSError:
        pass
    if moved:
        logger.info("Modelo reorganizado (carpeta anidada aplanada): %s", model_dir)
    return moved


@dataclass
class DetectedFace:
    """Una cara detectada en un frame."""
    embedding: np.ndarray   # 512-d, L2-normalizado (listo para coseno vía dot)
    bbox: tuple[int, int, int, int]  # x1, y1, x2, y2
    det_score: float
    quality: float = 1.0    # norma del embedding pre-normalización (proxy de calidad)

    @property
    def width(self) -> int:
        return self.bbox[2] - self.bbox[0]

    @property
    def height(self) -> int:
        return self.bbox[3] - self.bbox[1]


def cosine_similarity(a: np.ndarray, b: np.ndarray) -> float:
    """Similitud coseno entre dos vectores (robusta ante normas != 1)."""
    denom = float(np.linalg.norm(a) * np.linalg.norm(b))
    if denom == 0.0:
        return 0.0
    return float(np.dot(a, b) / denom)


class FaceEngine:
    """Wrapper perezoso y thread-safe sobre ``insightface.app.FaceAnalysis``."""

    def __init__(self) -> None:
        self._app = None
        self._rec = None              # modelo de reconocimiento (para flip-TTA)
        self._face_align = None       # insightface.utils.face_align
        self._rec_size: int = 112
        self._providers: list[str] = []
        self._ctx_id: int = -1
        self._det_size: int = settings.det_size
        self._det_thresh: float = settings.det_thresh
        self._lock = threading.Lock()

    # -- selección de provider ---------------------------------------------
    @staticmethod
    def _select_providers() -> list[str]:
        try:
            import onnxruntime as ort
            available = set(ort.get_available_providers())
        except Exception as exc:  # pragma: no cover - depende del entorno
            logger.warning("No pude consultar onnxruntime: %s", exc)
            available = {"CPUExecutionProvider"}

        chosen = [p for p in settings.provider_priority if p in available]
        return chosen or ["CPUExecutionProvider"]

    # -- carga --------------------------------------------------------------
    def load(self) -> None:
        if self._app is not None:
            return
        with self._lock:
            if self._app is not None:
                return

            providers = self._select_providers()
            ctx_id = -1 if providers[0] == "CPUExecutionProvider" else 0

            self._check_model_present()
            flatten_model_dir(settings.models_dir / settings.model_name)

            from insightface.app import FaceAnalysis

            # Sólo detección + reconocimiento: evita cargar y ejecutar por cada
            # cara los modelos de landmarks (2d106/3d68) y género/edad, que no
            # usamos. Los keypoints del flip-TTA salen del detector (bnkps).
            app = FaceAnalysis(
                name=settings.model_name,
                root=str(settings.insightface_root),
                providers=providers,
                allowed_modules=["detection", "recognition"],
            )
            app.prepare(
                ctx_id=ctx_id,
                det_thresh=self._det_thresh,
                det_size=(self._det_size, self._det_size),
            )

            self._app = app
            self._providers = providers
            self._ctx_id = ctx_id

            # Modelo de reconocimiento + alineación, para el flip-TTA.
            self._rec = app.models.get("recognition")
            if self._rec is not None and getattr(self._rec, "input_size", None):
                self._rec_size = int(self._rec.input_size[0])
            try:
                from insightface.utils import face_align
                self._face_align = face_align
            except Exception:  # pragma: no cover
                self._face_align = None

            logger.info(
                "Motor listo | modelo=%s | provider=%s | device=%s | det_size=%d "
                "det_thresh=%.2f flip_tta=%s",
                settings.model_name,
                providers[0],
                "GPU" if ctx_id >= 0 else "CPU",
                self._det_size,
                self._det_thresh,
                settings.use_flip_tta,
            )
            if ctx_id < 0:
                # Sin GPU: el R100 es pesado en CPU. En Windows con GPU, la build
                # DirectML acelera varias veces y se autodetecta (DmlExecutionProvider).
                logger.warning(
                    "Corriendo en CPU. Para acelerar con tu GPU en Windows: "
                    "pip uninstall -y onnxruntime && pip install onnxruntime-directml "
                    "(NVIDIA: onnxruntime-gpu). No requiere cambios de código.",
                )

    def configure_detector(self, det_size: int, det_thresh: float) -> None:
        """Reconfigura el detector (tamaño de entrada y sensibilidad).

        Permite que el modo "alta precisión" use un detector más grande y más
        sensible. Re-prepara el modelo sólo si cambió algún valor.

        DirectML (AMD/Intel/NVIDIA en Windows) no soporta el Reshape dinámico de
        SCRFD fuera de 640×640 — en ese caso se ignora el cambio de det_size.
        """
        self.load()
        # DML no soporta det_size != 640: ignorar cambio de tamaño silenciosamente.
        if "DmlExecutionProvider" in self._providers:
            det_size = self._det_size  # mantener el tamaño ya compilado
        if det_size == self._det_size and abs(det_thresh - self._det_thresh) < 1e-6:
            return
        with self._lock:
            self._det_size = det_size
            self._det_thresh = det_thresh
            self._app.prepare(  # type: ignore[union-attr]
                ctx_id=self._ctx_id,
                det_thresh=det_thresh,
                det_size=(det_size, det_size),
            )
            logger.info(
                "Detector reconfigurado | det_size=%d det_thresh=%.2f",
                det_size, det_thresh,
            )

    def _check_model_present(self) -> None:
        """Avisa con un mensaje claro si faltan los pesos del modelo."""
        model_dir = settings.models_dir / settings.model_name
        if not model_dir.exists():
            logger.warning(
                "No encuentro el modelo '%s' en %s. InsightFace intentará "
                "descargarlo (requiere internet). Para uso offline ejecutá "
                "build/fetch_models.py antes de empaquetar.",
                settings.model_name,
                model_dir,
            )

    # -- inferencia ---------------------------------------------------------
    @property
    def provider(self) -> str:
        return self._providers[0] if self._providers else "?"

    @property
    def using_gpu(self) -> bool:
        return self._ctx_id >= 0

    def detect(self, frame_bgr: np.ndarray, min_face_px: int = 0) -> list[DetectedFace]:
        """Detecta caras en un frame BGR y devuelve embeddings normalizados.

        ``min_face_px`` descarta caras cuyo lado menor sea inferior al umbral
        (ruido de fondo / caras demasiado chicas para ser confiables).
        """
        self.load()
        faces = self._app.get(frame_bgr)  # type: ignore[union-attr]
        out: list[DetectedFace] = []
        for f in faces:
            x1, y1, x2, y2 = (int(v) for v in f.bbox)
            if min_face_px and min(x2 - x1, y2 - y1) < min_face_px:
                continue
            emb, qual = self._embedding_with_tta(frame_bgr, f)
            out.append(
                DetectedFace(
                    embedding=emb,
                    bbox=(x1, y1, x2, y2),
                    det_score=float(getattr(f, "det_score", 1.0)),
                    quality=qual,
                )
            )
        return out

    def _embedding_with_tta(self, frame_bgr: np.ndarray, face) -> tuple[np.ndarray, float]:
        """Devuelve (embedding 512-d normalizado, calidad).

        Con flip-TTA, promedia el embedding de la cara alineada y el de su espejo
        horizontal y re-normaliza. La calidad es la norma del vector antes de
        normalizar (magnitud de la feature ArcFace, proxy de calidad).
        """
        base = getattr(face, "embedding", None)
        if (
            settings.use_flip_tta
            and self._rec is not None
            and self._face_align is not None
            and base is not None
            and getattr(face, "kps", None) is not None
        ):
            try:
                aimg = self._face_align.norm_crop(
                    frame_bgr, face.kps, image_size=self._rec_size
                )
                flip_feat = self._rec.get_feat(np.fliplr(aimg))[0]
                combined = np.asarray(base, dtype=np.float32) + np.asarray(
                    flip_feat, dtype=np.float32
                )
                norm = float(np.linalg.norm(combined))
                if norm > 0:
                    return (combined / norm).astype(np.float32), norm / 2.0
            except Exception:  # pragma: no cover - fallback al embedding normal
                pass

        norm = float(np.linalg.norm(base)) if base is not None else 1.0
        emb = getattr(face, "normed_embedding", None)
        if emb is None:
            emb = base / (norm + 1e-9)
        return np.asarray(emb, dtype=np.float32), norm


# Instancia compartida por toda la app (el modelo se carga una sola vez).
engine = FaceEngine()
