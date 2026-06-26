"""Punto de entrada de FaceHunt-2 (app de escritorio local).

Flujo:
1. Arranca el servidor FastAPI/Uvicorn en un hilo, sólo en 127.0.0.1.
2. Espera a que ``/healthz`` responda.
3. Abre la UI en una ventana nativa (pywebview / WebView2).
4. Si pywebview o WebView2 no están disponibles, abre el navegador por defecto.

El token de sesión viaja en la URL inicial (``?token=...``); el frontend lo
lee y lo usa para autenticar las llamadas a la API.
"""

from __future__ import annotations

import logging
import socket
import sys
import threading
import time
import urllib.request
import webbrowser

import uvicorn

from .config import settings
from .server import app
from .utils.files import cleanup_dir

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-7s %(name)s | %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("facehunt2")


def _free_port(host: str) -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind((host, 0))
        return s.getsockname()[1]


def _wait_until_ready(url: str, timeout: float = 30.0) -> bool:
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(url, timeout=1) as resp:
                if resp.status == 200:
                    return True
        except Exception:
            time.sleep(0.2)
    return False


def main() -> int:
    host = settings.host
    port = settings.port or _free_port(host)
    base = f"http://{host}:{port}"
    app_url = f"{base}/?token={settings.auth_token}"

    config = uvicorn.Config(app, host=host, port=port, log_level="info")
    server = uvicorn.Server(config)
    thread = threading.Thread(target=server.run, name="uvicorn", daemon=True)
    thread.start()

    if not _wait_until_ready(f"{base}/healthz"):
        logger.error("El servidor no respondió a tiempo.")
        server.should_exit = True
        return 1

    logger.info("FaceHunt-2 escuchando en %s", base)

    # Aviso temprano sobre el runtime que YouTube exige hoy (deno).
    try:
        from .pipeline.downloader import has_deno
        if has_deno():
            logger.info("deno detectado: descargas de YouTube habilitadas.")
        else:
            logger.warning(
                "Sin 'deno' en el PATH: las descargas de YouTube pueden fallar "
                "(403). Instalá deno (ver README) o usá la pestaña 'Archivo "
                "local'. La carga de archivos locales funciona siempre."
            )
    except Exception:
        pass

    # --- Intento 1: ventana nativa (pywebview / WebView2) ------------------
    try:
        import webview  # import perezoso: si falta, caemos al navegador

        logger.info("Abriendo ventana nativa…")
        webview.create_window(
            settings.app_name,
            app_url,
            width=1200,
            height=840,
            min_size=(960, 640),
        )
        webview.start()  # bloquea hasta que se cierra la ventana
        logger.info("Ventana cerrada, apagando servidor…")
        server.should_exit = True
        cleanup_dir(settings.temp_dir)  # borra uploads, descargas y thumbnails
        return 0
    except Exception as exc:  # noqa: BLE001
        logger.warning("Ventana nativa no disponible (%s). Abriendo navegador…", exc)

    # --- Intento 2: navegador por defecto ----------------------------------
    webbrowser.open(app_url)
    logger.info("FaceHunt-2 abierto en el navegador. Cerrá esta consola para salir.")
    try:
        while thread.is_alive():
            time.sleep(0.5)
    except KeyboardInterrupt:
        pass
    server.should_exit = True
    cleanup_dir(settings.temp_dir)  # borra uploads, descargas y thumbnails
    return 0


if __name__ == "__main__":
    sys.exit(main())
