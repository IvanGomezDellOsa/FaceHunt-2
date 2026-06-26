"""Helpers de archivos: nombres seguros y manejo de temporales."""

from __future__ import annotations

import os
import shutil
from pathlib import Path

from unidecode import unidecode

_PROHIBITED = set('<>:"/\\|?*@#%')


def sanitize_filename(title: str, max_len: int = 100, fallback: str = "video") -> str:
    """Convierte un título arbitrario en un nombre de archivo ASCII seguro.

    >>> sanitize_filename("Café: ¿Qué? <test>")
    'Cafe_ Que_ _test_'
    >>> sanitize_filename("   ")
    'video'
    """
    ascii_title = unidecode(title or "")
    ascii_title = "".join("_" if c in _PROHIBITED else c for c in ascii_title)
    ascii_title = " ".join(ascii_title.split())
    ascii_title = ascii_title[:max_len].strip()
    return ascii_title or fallback


def safe_remove(path: str | os.PathLike | None) -> None:
    """Elimina un archivo si existe, ignorando errores."""
    if not path:
        return
    try:
        p = Path(path)
        if p.is_file():
            p.unlink()
    except OSError:
        pass


def cleanup_dir(path: str | os.PathLike | None) -> None:
    """Borra el contenido de un directorio (uploads, descargas, thumbnails)
    sin eliminar el directorio en sí. Ignora errores (best-effort al cerrar)."""
    if not path:
        return
    root = Path(path)
    if not root.is_dir():
        return
    for item in root.iterdir():
        try:
            if item.is_dir():
                shutil.rmtree(item, ignore_errors=True)
            else:
                item.unlink()
        except OSError:
            pass


def human_size(num_bytes: float) -> str:
    """Tamaño legible: 1536 -> '1.5 KB'."""
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if abs(num_bytes) < 1024.0:
            return f"{num_bytes:.1f} {unit}"
        num_bytes /= 1024.0
    return f"{num_bytes:.1f} PB"
