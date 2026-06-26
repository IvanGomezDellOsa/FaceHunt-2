"""Gestor de jobs asíncronos de reconocimiento.

Cada job corre en un hilo propio (la inferencia es bloqueante). El estado se
expone de forma thread-safe para que el endpoint SSE lo transmita en vivo.
"""

from __future__ import annotations

import logging
import threading
import uuid
from pathlib import Path

import numpy as np

from .config import settings
from .pipeline.clips import generate_clips
from .pipeline.downloader import DownloadError, download_youtube
from .pipeline.engine import engine
from .pipeline.frame_reader import FrameReader
from .pipeline.recognizer import AppearanceRange, recognize
from .schemas import JobStatus, RangeOut
from .utils.files import safe_remove
from .utils.power import keep_awake
from .utils.timefmt import format_range, format_timestamp, youtube_url_with_time

logger = logging.getLogger("facehunt2.jobs")

# Estados terminales (la conexión SSE se cierra al alcanzarlos).
TERMINAL = {"done", "error", "cancelled"}


class Job:
    def __init__(
        self,
        reference: np.ndarray,
        source_kind: str,
        *,
        video_path: str | None,
        video_url: str | None,
        sample_fps: float,
        det_size: int,
        det_thresh: float,
        threshold: float,
        merge_gap: float,
        cleanup_video: bool,
    ) -> None:
        self.id = uuid.uuid4().hex
        self.reference = reference
        self.source_kind = source_kind
        self.video_path = video_path     # ruta local (o destino tras descarga)
        self.video_url = video_url
        self.sample_fps = sample_fps
        self.det_size = det_size
        self.det_thresh = det_thresh
        self.threshold = threshold
        self.merge_gap = merge_gap
        self.cleanup_video = cleanup_video  # borrar el video al terminar (descargas / subidas)

        self.status = "pending"
        self.progress = 0.0
        self.processed = 0
        self.total = 0
        self.matches = 0
        self.message = "En cola…"
        self.fps = 0.0
        self.duration = 0.0
        self.ranges: list[AppearanceRange] = []

        self.thumb_dir = settings.temp_dir / "thumbs" / self.id
        self._lock = threading.Lock()
        self.stop_event = threading.Event()

    # -- mutadores thread-safe ---------------------------------------------
    def set(self, **kwargs) -> None:
        with self._lock:
            for k, v in kwargs.items():
                setattr(self, k, v)

    def on_progress(self, processed: int, total: int, matches: int) -> None:
        with self._lock:
            self.processed = processed
            self.total = total
            self.matches = matches
            self.progress = (processed / total) if total else 0.0

    # -- serialización ------------------------------------------------------
    def to_status(self) -> JobStatus:
        with self._lock:
            ranges = [self._range_out(r) for r in self.ranges]
            return JobStatus(
                id=self.id,
                status=self.status,
                progress=round(self.progress, 4),
                processed=self.processed,
                total=self.total,
                matches=self.matches,
                message=self.message,
                provider=engine.provider,
                using_gpu=engine.using_gpu,
                source_kind=self.source_kind,
                fps=self.fps,
                duration=self.duration,
                ranges=ranges,
            )

    def _range_out(self, r: AppearanceRange) -> RangeOut:
        thumb = None
        if r.thumbnail:
            thumb = f"/api/jobs/{self.id}/thumb/{r.thumbnail}?token={settings.auth_token}"
        clip = None
        if r.clip:
            clip = f"/api/jobs/{self.id}/clip/{r.clip}?token={settings.auth_token}"
        seek = None
        if self.source_kind == "youtube" and self.video_url:
            seek = youtube_url_with_time(self.video_url, r.best_timestamp)
        return RangeOut(
            start=round(r.start, 2),
            end=round(r.end, 2),
            start_label=format_timestamp(r.start),
            end_label=format_timestamp(r.end),
            range_label=format_range(r.start, r.end),
            best_timestamp=round(r.best_timestamp, 2),
            best_score=round(r.best_score, 4),
            count=r.count,
            thumbnail_url=thumb,
            clip_url=clip,
            seek_url=seek,
        )

    # -- ejecución ----------------------------------------------------------
    def run(self) -> None:
        try:
            with keep_awake():  # evita que la PC se suspenda durante el análisis
                self._run()
        except DownloadError as exc:
            self.set(status="error", message=str(exc))
        except Exception as exc:  # noqa: BLE001
            logger.exception("Job %s falló", self.id)
            self.set(status="error", message=f"Error interno: {exc}")
        finally:
            # El archivo temporal (subida local o descarga de YouTube) se borra;
            # los thumbnails quedan disponibles hasta que se cierra la app.
            if self.cleanup_video and self.video_path:
                safe_remove(self.video_path)

    def _run(self) -> None:
        # 1) Resolver el video.
        if self.source_kind == "youtube":
            self.set(status="downloading", message="Descargando video de YouTube…")
            self.video_path = download_youtube(
                self.video_url or "",
                on_progress=lambda f: self.set(progress=round(f, 4)),
            )

        if not self.video_path or not Path(self.video_path).exists():
            self.set(status="error", message="No se encontró el archivo de video.")
            return

        # 2) Abrir y muestrear.
        reader = FrameReader(self.video_path, self.sample_fps)
        ok, msg = reader.open()
        if not ok:
            self.set(status="error", message=msg)
            return

        self.set(
            status="processing",
            message="Cargando modelo y analizando frames…",
            total=reader.total_samples,
            fps=reader.fps,
            duration=reader.duration,
            progress=0.0,
        )

        # Configura el detector según el modo (esfuerzo de detección).
        engine.configure_detector(self.det_size, self.det_thresh)

        # 3) Reconocer.
        try:
            result = recognize(
                reader,
                self.reference,
                threshold=self.threshold,
                merge_gap=self.merge_gap,
                min_face_px=settings.min_face_px,
                thumbnail_dir=self.thumb_dir,
                thumbnail_prefix="r",
                on_progress=self.on_progress,
                stop_event=self.stop_event,
            )
        finally:
            reader.close()

        if result.cancelled:
            self.set(status="cancelled", message="Análisis cancelado.")
            return

        if result.processed == 0:
            self.set(
                status="error",
                message=(
                    "No se pudo decodificar ningún frame del video. El códec "
                    "puede no ser compatible: probá con un archivo MP4 (H.264)."
                ),
            )
            return

        # Mini-clips animados por aparición (el video todavía existe; la limpieza
        # ocurre en run() tras volver de _run). Best-effort: no aborta el job.
        if settings.make_clips and result.ranges and self.video_path:
            generate_clips(
                self.video_path,
                result.ranges,
                self.thumb_dir,
                prefix="r",
                seconds=settings.clip_seconds,
                fps_target=settings.clip_fps,
                max_side=settings.clip_max_side,
            )

        n = len(result.ranges)
        if n == 0:
            if result.faces_detected == 0:
                msg = (
                    "0 apariciones: no se detectaron caras en el video "
                    f"({result.processed} frames analizados)."
                )
            else:
                msg = (
                    f"0 apariciones. Se vieron caras, pero la mejor similitud fue "
                    f"{result.best_similarity:.2f} (umbral {self.threshold:.2f}). "
                    "Probá con fotos de referencia más nítidas o el modo Exhaustivo."
                )
        else:
            msg = (
                f"Listo: {n} aparición(es). "
                f"Mejor similitud observada: {result.best_similarity:.2f}."
            )
        self.set(status="done", ranges=result.ranges, progress=1.0, message=msg)

    def cancel(self) -> None:
        self.stop_event.set()


class JobManager:
    def __init__(self) -> None:
        self._jobs: dict[str, Job] = {}
        self._lock = threading.Lock()

    def submit(self, job: Job) -> Job:
        with self._lock:
            self._jobs[job.id] = job
        thread = threading.Thread(target=job.run, name=f"job-{job.id}", daemon=True)
        thread.start()
        return job

    def get(self, job_id: str) -> Job | None:
        with self._lock:
            return self._jobs.get(job_id)

    def cancel(self, job_id: str) -> bool:
        job = self.get(job_id)
        if job:
            job.cancel()
            return True
        return False


manager = JobManager()
