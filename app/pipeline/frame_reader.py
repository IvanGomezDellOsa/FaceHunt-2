"""Lectura y muestreo de frames de video.

Un hilo productor decodifica el video y deja en una cola acotada sólo los
frames muestreados (``sample_fps`` por segundo). Así la decodificación (I/O)
se solapa con la inferencia (CPU/GPU) que corre en el hilo consumidor.
"""

from __future__ import annotations

import logging
import threading
from dataclasses import dataclass
from queue import Queue
from typing import Iterator

import cv2
import numpy as np

logger = logging.getLogger("facehunt2.frames")

_SENTINEL = object()


@dataclass
class Sample:
    index: int            # índice de frame original en el video
    timestamp: float      # segundos
    frame: np.ndarray     # BGR


class FrameReader:
    """Muestrea frames a ``sample_fps`` desde un archivo de video."""

    def __init__(self, path: str, sample_fps: float, queue_size: int = 24) -> None:
        self.path = path
        self.sample_fps = max(0.1, sample_fps)
        self.queue_size = queue_size

        self.fps: float = 30.0
        self.total_frames: int = 0
        self.interval: int = 1
        self.total_samples: int = 0
        self.duration: float = 0.0

        self._cap: cv2.VideoCapture | None = None
        self._thread: threading.Thread | None = None
        self._queue: Queue = Queue(maxsize=queue_size)
        self._stop = threading.Event()

    def open(self) -> tuple[bool, str]:
        cap = cv2.VideoCapture(self.path)
        if not cap.isOpened():
            cap.release()
            return False, "No se pudo abrir el video."

        self.fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
        if self.fps <= 0:
            self.fps = 30.0
        self.total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
        self.interval = max(1, round(self.fps / self.sample_fps))
        self.duration = self.total_frames / self.fps if self.total_frames else 0.0
        self.total_samples = (
            self.total_frames // self.interval if self.total_frames else 0
        )
        self._cap = cap
        logger.info(
            "Video abierto: fps=%.2f total_frames=%d intervalo=%d muestras≈%d dur=%.1fs",
            self.fps, self.total_frames, self.interval,
            self.total_samples, self.duration,
        )
        return True, "ok"

    # -- productor ----------------------------------------------------------
    def _produce(self) -> None:
        # grab() avanza el frame sin decodificarlo del todo; retrieve() hace la
        # conversión a BGR (lo caro) sólo en los frames muestreados. Evita
        # decodificar los ~(interval-1) frames descartados de cada intervalo.
        cap = self._cap
        assert cap is not None
        idx = 0
        try:
            while not self._stop.is_set():
                if not cap.grab():
                    break
                if idx % self.interval == 0:
                    ret, frame = cap.retrieve()
                    if not ret:
                        break
                    self._queue.put(Sample(idx, idx / self.fps, frame))
                idx += 1
        except Exception as exc:  # pragma: no cover
            logger.exception("Error leyendo frames: %s", exc)
        finally:
            self._queue.put(_SENTINEL)

    def stream(self) -> Iterator[Sample]:
        """Itera los frames muestreados. Lanza el hilo productor en el primer uso."""
        if self._cap is None:
            raise RuntimeError("Llamá a open() antes de stream().")
        self._thread = threading.Thread(target=self._produce, daemon=True)
        self._thread.start()

        while True:
            item = self._queue.get()
            if item is _SENTINEL:
                break
            yield item  # type: ignore[misc]

    def stop(self) -> None:
        """Detiene el productor (cancelación) y libera recursos."""
        self._stop.set()
        # Drenar la cola para que el productor no quede bloqueado en put().
        try:
            while not self._queue.empty():
                self._queue.get_nowait()
        except Exception:
            pass

    def close(self) -> None:
        self.stop()
        if self._cap is not None:
            self._cap.release()
            self._cap = None
