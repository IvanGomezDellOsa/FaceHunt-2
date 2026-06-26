"""Validación y metadatos de la fuente de video (archivo local o YouTube)."""

from __future__ import annotations

import logging
from dataclasses import dataclass

import cv2
import yt_dlp

logger = logging.getLogger("facehunt2.video")


@dataclass
class VideoInfo:
    ok: bool
    kind: str          # 'local' | 'youtube'
    message: str
    source: str = ""   # ruta local o URL
    title: str = ""
    duration: float = 0.0
    fps: float = 0.0


def _looks_like_youtube(url: str) -> bool:
    u = url.lower()
    return "youtube.com" in u or "youtu.be" in u


def probe_local(path: str) -> VideoInfo:
    """Abre un archivo local y extrae fps/duración."""
    cap = cv2.VideoCapture(path)
    if not cap.isOpened():
        cap.release()
        return VideoInfo(False, "local", "Formato de video inválido o no soportado.")

    fps = cap.get(cv2.CAP_PROP_FPS) or 0.0
    frames = cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0.0
    cap.release()

    if fps <= 0:
        fps = 30.0
    duration = frames / fps if frames > 0 else 0.0
    return VideoInfo(
        ok=True,
        kind="local",
        message="Archivo de video válido.",
        source=path,
        title="",
        duration=duration,
        fps=fps,
    )


def probe_youtube(url: str) -> VideoInfo:
    """Verifica accesibilidad de una URL de YouTube y trae metadatos."""
    try:
        with yt_dlp.YoutubeDL(
            {"quiet": True, "noplaylist": True, "extract_flat": False}
        ) as ydl:
            info = ydl.extract_info(url, download=False)
    except Exception as exc:
        return VideoInfo(False, "youtube", _friendly(exc))

    if not info or not info.get("id") or not info.get("duration"):
        return VideoInfo(False, "youtube", "Video no encontrado o inaccesible.")
    if not info.get("formats"):
        return VideoInfo(False, "youtube", "No hay formatos de video disponibles.")

    return VideoInfo(
        ok=True,
        kind="youtube",
        message=f"YouTube válido: {info.get('title', '?')}",
        source=url,
        title=info.get("title", ""),
        duration=float(info.get("duration", 0)),
        fps=float(info.get("fps") or 0.0),
    )


def probe(source: str, is_url: bool) -> VideoInfo:
    """Punto de entrada: decide entre local y YouTube."""
    if is_url:
        if not _looks_like_youtube(source):
            return VideoInfo(False, "youtube", "Solo se soportan URLs de YouTube.")
        return probe_youtube(source)
    return probe_local(source)


def _friendly(exc: Exception) -> str:
    msg = str(exc)
    if "Private" in msg:
        return "El video es privado."
    if "Video unavailable" in msg:
        return "El video no está disponible."
    return "URL de YouTube inválida."
