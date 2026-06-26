"""Entrypoint de FaceHunt-2.

Sirve tanto para desarrollo (``python run.py``) como de script de arranque para
PyInstaller. Importa el paquete ``app`` (con lo que los imports relativos del
paquete funcionan) y delega en ``app.main.main``.
"""

import os
import sys
import tempfile

# En el ejecutable empaquetado en modo ventana (PyInstaller --noconsole) no hay
# consola: sys.stdout y sys.stderr son None. Varias librerías (uvicorn) llaman
# sys.stdout.isatty() al iniciar y eso revienta. Garantizamos streams reales,
# redirigidos a un archivo de log para poder diagnosticar fallos en producción.
if sys.stdout is None or sys.stderr is None:
    try:
        stream = open(
            os.path.join(tempfile.gettempdir(), "facehunt2.log"),
            "a", buffering=1, encoding="utf-8",
        )
    except OSError:
        stream = open(os.devnull, "w")
    sys.stdout = sys.stdout or stream
    sys.stderr = sys.stderr or stream

from app.main import main

if __name__ == "__main__":
    raise SystemExit(main())
