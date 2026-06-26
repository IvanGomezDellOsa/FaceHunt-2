"""Evita que el sistema entre en suspensión durante un procesamiento largo.

En Windows usa ``SetThreadExecutionState`` (ES_SYSTEM_REQUIRED) para impedir el
sleep por inactividad mientras dura el análisis. En otros sistemas es no-op.
La pantalla SÍ puede apagarse; sólo se evita la suspensión del sistema.
"""

from __future__ import annotations

import contextlib
import ctypes
import logging
import sys

logger = logging.getLogger("facehunt2.power")

_ES_CONTINUOUS = 0x80000000
_ES_SYSTEM_REQUIRED = 0x00000001


@contextlib.contextmanager
def keep_awake():
    """Context manager que mantiene el sistema despierto mientras dura el bloque."""
    if sys.platform != "win32":
        yield
        return

    try:
        ctypes.windll.kernel32.SetThreadExecutionState(
            _ES_CONTINUOUS | _ES_SYSTEM_REQUIRED
        )
        logger.debug("Suspensión del sistema deshabilitada durante el análisis.")
    except Exception as exc:  # pragma: no cover - depende del SO
        logger.warning("No pude deshabilitar la suspensión: %s", exc)

    try:
        yield
    finally:
        try:
            ctypes.windll.kernel32.SetThreadExecutionState(_ES_CONTINUOUS)
        except Exception:
            pass
