"""Configuración central de FaceHunt-2.

Resuelve rutas tanto en desarrollo como dentro del ejecutable de PyInstaller
(``sys._MEIPASS``), y expone los parámetros del motor y del servidor en un único
objeto ``settings`` importable desde cualquier módulo.
"""

from __future__ import annotations

import os
import secrets
import sys
import tempfile
from dataclasses import dataclass, field
from pathlib import Path


def _is_frozen() -> bool:
    """True si corremos dentro de un binario de PyInstaller."""
    return getattr(sys, "frozen", False)


def _resource_root() -> Path:
    """Raíz de los recursos empaquetados (web/, app/models/).

    - Congelado: el directorio temporal donde PyInstaller extrae los datos.
    - Desarrollo: la raíz del proyecto (carpeta ``FaceHunt-2``).
    """
    if _is_frozen():
        return Path(sys._MEIPASS)  # type: ignore[attr-defined]
    return Path(__file__).resolve().parent.parent


@dataclass(frozen=True)
class Settings:
    # --- Identidad ---------------------------------------------------------
    app_name: str = "FaceHunt-2"
    version: str = "2.0.0"

    # --- Servidor local ----------------------------------------------------
    host: str = "127.0.0.1"
    # 0 => el launcher elige un puerto libre. Se puede fijar con FH2_PORT.
    port: int = int(os.environ.get("FH2_PORT", "0"))
    # Token de sesión: protege la API de otros procesos en localhost.
    auth_token: str = field(default_factory=lambda: secrets.token_urlsafe(24))

    # --- Motor de reconocimiento ------------------------------------------
    # antelopev2: SCRFD + ArcFace ResNet100 @ Glint360K (512-d). Backbone más
    # profundo (R100) que el R50 de buffalo_l -> mejores embeddings, a más
    # cómputo (viable en local). Override con FH2_MODEL=buffalo_l.
    model_name: str = os.environ.get("FH2_MODEL", "antelopev2")
    det_size: int = 640                     # lado del input del detector (modo equilibrado)
    det_thresh: float = 0.5                 # confianza mínima del detector SCRFD

    # Flip-TTA: promedia el embedding de la cara y su espejo horizontal. Mejora
    # recall a costa de ~2x el cómputo de reconocimiento (no el de detección).
    use_flip_tta: bool = True

    # Referencia: detección más permisiva que en el video (una sola foto elegida
    # por el usuario; conviene aceptar caras chicas, recortadas o de baja calidad).
    ref_det_size: int = 1024
    ref_det_thresh: float = 0.3
    ref_min_side: int = 800     # reescala imágenes chicas a este lado mínimo
    # Con varias fotos, si la similitud entre ellas cae por debajo de esto se
    # asume que son personas distintas y se rechaza con aviso.
    ref_same_person_min: float = 0.20
    # Providers candidatos, en orden de preferencia. El motor usa los que
    # estén realmente disponibles en la build de onnxruntime instalada.
    provider_priority: tuple[str, ...] = (
        "CUDAExecutionProvider",
        "DmlExecutionProvider",
        "CPUExecutionProvider",
    )

    # --- Parámetros de búsqueda (config; sin control en la UI) -------------
    # Similitud coseno mínima (NO distancia) sobre embeddings normalizados.
    # La guía oficial de InsightFace sitúa los umbrales 1:1 en 0.30–0.45
    # (FMR 1e-4/1e-5). Usamos el extremo permisivo (0.30) para priorizar recall.
    match_threshold: float = 0.30
    # Huecos <= a esto (segundos) se fusionan en un mismo rango de aparición.
    merge_gap_seconds: float = 2.0
    # Caras más chicas que esto (lado en px sobre el frame muestreado) se ignoran.
    min_face_px: int = 20

    # --- Thumbnails de resultados -----------------------------------------
    # Dibuja un recuadro verde sobre la cara en el thumbnail (look "detección").
    draw_face_box: bool = True

    # --- Mini-clip por aparición ------------------------------------------
    # Genera un WebP animado (~2 s) alrededor del mejor frame de cada rango,
    # que la UI reproduce en loop al pasar el mouse sobre la tarjeta.
    make_clips: bool = True
    clip_seconds: float = 2.0       # duración total del clip (centrado en el match)
    clip_fps: int = 12              # cuadros por segundo del clip (tamaño vs fluidez)
    clip_max_side: int = 360        # lado mayor del clip en px

    # --- Tracking + agregación temporal -----------------------------------
    # Agrupa caras de frames sucesivos en tracklets y matchea sobre el embedding
    # agregado; recupera frames degradados de un tracklet confirmado (sube recall).
    use_tracking: bool = True
    track_iou_thresh: float = 0.3       # solape de caja para asociar
    track_appear_thresh: float = 0.45   # similitud de apariencia para asociar
    # Umbral secundario = match_threshold - margen: frames de un tracklet ya
    # confirmado que cuentan como aparición aunque no lleguen al umbral principal.
    track_secondary_margin: float = 0.08

    # --- Descarga de YouTube ----------------------------------------------
    # 720p da caras con más píxeles -> mejor detección que 480p.
    yt_max_height: int = 720
    min_free_disk_mb: int = 500

    # --- Modos de búsqueda -------------------------------------------------
    # El modo controla el esfuerzo de detección, no el umbral de identidad:
    # "precision" analiza más frames con un detector más grande y sensible para
    # hallar más apariciones (caras chicas o de perfil).
    modes: dict = field(
        default_factory=lambda: {
            "balanced": {"sample_fps": 2.0, "det_size": 640, "det_thresh": 0.5},
            "precision": {"sample_fps": 5.0, "det_size": 1280, "det_thresh": 0.3},
        }
    )

    # --- Límites de subida -------------------------------------------------
    max_image_mb: int = 25
    max_video_mb: int = 2048

    # --- Rutas (derivadas) -------------------------------------------------
    @property
    def resource_root(self) -> Path:
        return _resource_root()

    @property
    def web_dir(self) -> Path:
        return self.resource_root / "web"

    @property
    def insightface_root(self) -> Path:
        """Root para InsightFace: busca modelos en ``<root>/models/<name>``."""
        return self.resource_root / "app"

    @property
    def models_dir(self) -> Path:
        return self.insightface_root / "models"

    @property
    def temp_dir(self) -> Path:
        """Directorio escribible para descargas y thumbnails (no usar MEIPASS)."""
        d = Path(tempfile.gettempdir()) / "facehunt2"
        d.mkdir(parents=True, exist_ok=True)
        return d

    @property
    def is_frozen(self) -> bool:
        return _is_frozen()


settings = Settings()
