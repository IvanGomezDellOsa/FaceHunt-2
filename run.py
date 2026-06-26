"""Entrypoint de FaceHunt-2.

Sirve tanto para desarrollo (``python run.py``) como de script de arranque para
PyInstaller. Importa el paquete ``app`` (con lo que los imports relativos del
paquete funcionan) y delega en ``app.main.main``.
"""

from app.main import main

if __name__ == "__main__":
    raise SystemExit(main())
