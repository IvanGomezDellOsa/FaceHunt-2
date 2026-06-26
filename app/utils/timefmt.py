"""Formato de tiempo y construcción de enlaces con seek temporal."""

from __future__ import annotations

from urllib.parse import urlencode, urlparse, urlunparse, parse_qsl


def format_timestamp(seconds: float) -> str:
    """Convierte segundos a ``mm:ss`` (o ``h:mm:ss`` si supera la hora).

    >>> format_timestamp(0)
    '00:00'
    >>> format_timestamp(75)
    '01:15'
    >>> format_timestamp(3661)
    '1:01:01'
    """
    if seconds < 0:
        seconds = 0
    total = int(round(seconds))
    hours, rem = divmod(total, 3600)
    minutes, secs = divmod(rem, 60)
    if hours:
        return f"{hours}:{minutes:02d}:{secs:02d}"
    return f"{minutes:02d}:{secs:02d}"


def format_range(start: float, end: float) -> str:
    """Rango legible ``mm:ss – mm:ss`` (o sólo el instante si start≈end)."""
    if abs(end - start) < 0.5:
        return format_timestamp(start)
    return f"{format_timestamp(start)} – {format_timestamp(end)}"


def youtube_url_with_time(url: str, seconds: float) -> str:
    """Devuelve la URL de YouTube con el parámetro de tiempo ``t`` aplicado.

    Preserva el resto del query string y reemplaza cualquier ``t`` previo.

    >>> youtube_url_with_time("https://youtu.be/abc", 75)
    'https://youtu.be/abc?t=75'
    """
    t = max(0, int(round(seconds)))
    parsed = urlparse(url)
    query = [(k, v) for k, v in parse_qsl(parsed.query) if k != "t"]
    query.append(("t", str(t)))
    return urlunparse(parsed._replace(query=urlencode(query)))
