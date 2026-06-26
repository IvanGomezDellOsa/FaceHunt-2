"""Descarga de videos de YouTube con yt-dlp.

A diferencia de la versión online del proyecto original, acá NO hace falta el
hack de DNS (`patch_dns.py`): al ejecutarse en la máquina del usuario, yt-dlp
funciona normalmente sin chocar con el anti-bot del hosting gratuito.
"""

from __future__ import annotations

import logging
import shutil
from pathlib import Path
from typing import Callable

import yt_dlp

from ..config import settings
from ..utils.files import sanitize_filename

logger = logging.getLogger("facehunt2.downloader")

ProgressCb = Callable[[float], None]  # recibe fracción 0..1

def has_deno() -> bool:
    """True si 'deno' está en el PATH.

    yt-dlp usa deno por defecto para descifrar firmas de YouTube. No forzamos
    node/bun: su habilitación manual es inestable y rompe hasta la extracción
    de metadatos. Sin deno, la alternativa fiable es subir el video como archivo.
    """
    return shutil.which("deno") is not None


class DownloadError(Exception):
    """Error legible para mostrar al usuario."""


def download_youtube(url: str, on_progress: ProgressCb | None = None) -> str:
    """Descarga el video en MP4 (<= altura configurada) y devuelve la ruta.

    Reutiliza el archivo si ya fue descargado antes. Lanza ``DownloadError``
    con un mensaje claro ante fallos.
    """
    out_dir = settings.temp_dir / "videos"
    out_dir.mkdir(parents=True, exist_ok=True)

    # Espacio en disco
    free_mb = shutil.disk_usage(out_dir).free / (1024 * 1024)
    if free_mb < settings.min_free_disk_mb:
        raise DownloadError(
            f"Espacio en disco insuficiente (<{settings.min_free_disk_mb} MB libres)."
        )

    try:
        with yt_dlp.YoutubeDL({"quiet": True, "noplaylist": True}) as ydl:
            info = ydl.extract_info(url, download=False)
        title = sanitize_filename(info.get("title", "video"))
    except Exception as exc:
        raise DownloadError(_friendly_yt_error(exc)) from exc

    target = out_dir / f"{title}.mp4"
    if target.exists():
        logger.info("Reutilizando descarga previa: %s", target)
        if on_progress:
            on_progress(1.0)
        return str(target)

    def _hook(d: dict) -> None:
        if on_progress and d.get("status") == "downloading":
            total = d.get("total_bytes") or d.get("total_bytes_estimate")
            done = d.get("downloaded_bytes", 0)
            if total:
                on_progress(min(0.999, done / total))

    ydl_opts = {
        # Sólo se analizan frames: el audio no se usa. Priorizamos streams
        # video-only (más livianos y sin paso de merge); caemos a uno con audio
        # sólo si no hay video-only disponible.
        "format": (
            f"bestvideo[height<={settings.yt_max_height}][ext=mp4]/"
            f"bestvideo[height<={settings.yt_max_height}]/"
            f"best[height<={settings.yt_max_height}][ext=mp4]/best[ext=mp4]/best"
        ),
        "outtmpl": str(out_dir / f"{title}.%(ext)s"),
        "noplaylist": True,
        "quiet": True,
        "merge_output_format": "mp4",
        "progress_hooks": [_hook],
        # Robustez ante 403/throttling de YouTube: reintentos y descarga por
        # chunks (re-pide rangos con URLs frescas en vez de un stream largo).
        "retries": 5,
        "fragment_retries": 10,
        "http_chunk_size": 10 * 1024 * 1024,  # 10 MB
        "continuedl": True,
    }

    logger.info("Descargando: %s", url)
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([url])
    except Exception as exc:
        raise DownloadError(_friendly_yt_error(exc)) from exc

    if not target.exists():
        # yt-dlp pudo guardar con otra extensión: buscamos el resultado.
        candidates = sorted(out_dir.glob(f"{title}.*"))
        if candidates:
            return str(candidates[0])
        raise DownloadError("La descarga finalizó pero no se encontró el archivo.")

    if on_progress:
        on_progress(1.0)
    return str(target)


def _friendly_yt_error(exc: Exception) -> str:
    msg = str(exc)
    low = msg.lower()
    if "private" in low:
        return "El video es privado."
    if "unavailable" in low or "not available" in low:
        return "El video no está disponible."
    if "sign in" in low or "age" in low:
        return "El video requiere inicio de sesión o verificación de edad."
    if "is not a valid url" in low or "unsupported url" in low:
        return "La URL de YouTube no es válida."

    # Caso típico hoy: YouTube exige un runtime JS (deno) para descifrar firmas.
    if "403" in low or "forbidden" in low or "javascript runtime" in low or "po token" in low:
        if not has_deno():
            return (
                "YouTube bloqueó la descarga (cambió su protección anti-bot). "
                "Solución recomendada: instalá 'deno' (un solo comando) — yt-dlp "
                "lo usa automáticamente. Ver README. Alternativa 100% confiable: "
                "descargá el video manualmente y subilo en la pestaña "
                "'Archivo local'."
            )
        return (
            "YouTube rechazó la descarga (403) pese a tener deno. Suele ser "
            "temporal: reintentá, actualizá yt-dlp (pip install -U yt-dlp) o "
            "descargá el video y subilo como 'Archivo local'."
        )

    return f"No se pudo descargar el video: {msg}"
