"""Agrupado de matches en rangos de aparición (lógica pura, sin dependencias).

Aislado de ``recognizer`` (que necesita cv2/numpy) para poder testearlo solo.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class MatchPoint:
    timestamp: float
    score: float
    frame_index: int


@dataclass
class AppearanceRange:
    start: float
    end: float
    best_timestamp: float
    best_score: float
    count: int
    thumbnail: str | None = None  # nombre del archivo de thumbnail (lo sirve la API)
    clip: str | None = None       # nombre del WebP animado (lo sirve la API)
    # bbox del mejor frame (x1,y1,x2,y2); lo usa el generador de clips para
    # recortar una región estable alrededor de la cara.
    best_bbox: tuple[int, int, int, int] | None = None


def build_ranges(matches: list[MatchPoint], merge_gap: float) -> list[AppearanceRange]:
    """Agrupa matches consecutivos en rangos de aparición.

    Dos matches caen en el mismo rango si la diferencia entre sus timestamps es
    <= ``merge_gap``. El instante representativo es el de mayor similitud (ante
    empate, el más temprano).
    """
    if not matches:
        return []

    ordered = sorted(matches, key=lambda m: m.timestamp)
    ranges: list[AppearanceRange] = []
    cur: list[MatchPoint] = [ordered[0]]

    def flush(group: list[MatchPoint]) -> AppearanceRange:
        best = max(group, key=lambda m: (m.score, -m.timestamp))
        return AppearanceRange(
            start=group[0].timestamp,
            end=group[-1].timestamp,
            best_timestamp=best.timestamp,
            best_score=best.score,
            count=len(group),
        )

    for m in ordered[1:]:
        if m.timestamp - cur[-1].timestamp <= merge_gap:
            cur.append(m)
        else:
            ranges.append(flush(cur))
            cur = [m]
    ranges.append(flush(cur))
    return ranges
