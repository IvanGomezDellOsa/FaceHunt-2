"""API FastAPI de FaceHunt-2 (servida localmente).

Diseño local-first:
- Escucha sólo en 127.0.0.1.
- Protegida por un token de sesión (query ``?token=`` o header ``X-Auth-Token``)
  para que otros procesos en localhost no puedan usar la API.
- Sirve el frontend estático y expone la API en ``/api``.
"""

from __future__ import annotations

import asyncio
import logging
import os
import shutil
import tempfile
import uuid

import numpy as np
from fastapi import (
    APIRouter,
    Depends,
    FastAPI,
    File,
    Form,
    Header,
    HTTPException,
    Query,
    UploadFile,
)
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles

from .config import settings
from .jobs import TERMINAL, Job, manager
from .pipeline import video_source
from .pipeline.reference import build_reference
from .schemas import (
    JobCreateRequest,
    JobCreateResponse,
    JobStatus,
    ReferenceResponse,
    VideoValidateResponse,
)
from .utils.files import safe_remove

logger = logging.getLogger("facehunt2.server")

app = FastAPI(title=settings.app_name, version=settings.version)

# Almacenes en memoria (app local de un solo usuario).
_references: dict[str, np.ndarray] = {}
_videos: dict[str, str] = {}  # video_token -> ruta temporal


# --------------------------------------------------------------------------
# Autenticación local
# --------------------------------------------------------------------------
def require_token(
    token: str | None = Query(None),
    x_auth_token: str | None = Header(None),
) -> None:
    provided = token or x_auth_token
    if provided != settings.auth_token:
        raise HTTPException(status_code=401, detail="Token inválido o ausente.")


api = APIRouter(prefix="/api", dependencies=[Depends(require_token)])


# --------------------------------------------------------------------------
# Helpers
# --------------------------------------------------------------------------
def _save_upload(file: UploadFile, max_mb: int) -> str:
    """Guarda un upload a un archivo temporal, validando el tamaño."""
    suffix = os.path.splitext(file.filename or "")[1]
    fd, path = tempfile.mkstemp(suffix=suffix, dir=str(settings.temp_dir))
    os.close(fd)
    size = 0
    limit = max_mb * 1024 * 1024
    try:
        with open(path, "wb") as out:
            while chunk := file.file.read(1024 * 1024):
                size += len(chunk)
                if size > limit:
                    raise HTTPException(
                        status_code=413,
                        detail=f"Archivo demasiado grande (máx {max_mb} MB).",
                    )
                out.write(chunk)
    except HTTPException:
        safe_remove(path)
        raise
    finally:
        file.file.close()
    return path


# --------------------------------------------------------------------------
# Endpoints
# --------------------------------------------------------------------------
@api.post("/reference", response_model=ReferenceResponse)
async def post_reference(files: list[UploadFile] = File(...)) -> ReferenceResponse:
    temp_paths: list[str] = []
    try:
        for f in files:
            temp_paths.append(_save_upload(f, settings.max_image_mb))
        result = build_reference(temp_paths)
        if not result.ok or result.embedding is None:
            raise HTTPException(status_code=400, detail=result.message)

        ref_id = uuid.uuid4().hex
        _references[ref_id] = result.embedding
        return ReferenceResponse(
            reference_id=ref_id,
            message=result.message,
            num_images=result.num_images,
            multiple_faces_warning=result.multiple_faces_warning,
        )
    finally:
        for p in temp_paths:
            safe_remove(p)


@api.post("/video/validate", response_model=VideoValidateResponse)
async def post_validate_video(
    source: str | None = Form(None),
    file: UploadFile | None = File(None),
) -> VideoValidateResponse:
    if bool(source) == bool(file):
        raise HTTPException(
            status_code=400, detail="Indicá una URL o un archivo (no ambos)."
        )

    if file:
        path = _save_upload(file, settings.max_video_mb)
        info = video_source.probe(path, is_url=False)
        if not info.ok:
            safe_remove(path)
            raise HTTPException(status_code=400, detail=info.message)
        token = uuid.uuid4().hex
        _videos[token] = path
        return VideoValidateResponse(
            kind=info.kind, message=info.message,
            duration=info.duration, video_token=token,
        )

    info = video_source.probe(source or "", is_url=True)
    if not info.ok:
        raise HTTPException(status_code=400, detail=info.message)
    return VideoValidateResponse(
        kind=info.kind, message=info.message,
        title=info.title, duration=info.duration,
    )


@api.post("/jobs", response_model=JobCreateResponse)
async def create_job(req: JobCreateRequest) -> JobCreateResponse:
    reference = _references.get(req.reference_id)
    if reference is None:
        raise HTTPException(status_code=404, detail="Referencia no encontrada o expirada.")

    if bool(req.video_token) == bool(req.video_url):
        raise HTTPException(
            status_code=400, detail="Indicá video_token (local) o video_url (YouTube)."
        )

    if req.video_url:
        source_kind, video_path = "youtube", None
    else:
        video_path = _videos.get(req.video_token or "")
        if not video_path:
            raise HTTPException(status_code=404, detail="Video no encontrado o expirado.")
        source_kind = "local"

    mode_cfg = settings.modes.get(req.mode, settings.modes["balanced"])

    job = Job(
        reference=reference,
        source_kind=source_kind,
        video_path=video_path,
        video_url=req.video_url,
        sample_fps=mode_cfg["sample_fps"],
        det_size=mode_cfg["det_size"],
        det_thresh=mode_cfg["det_thresh"],
        threshold=settings.match_threshold,
        merge_gap=settings.merge_gap_seconds,
        # Sólo se borra al terminar lo descargado de YouTube (re-descargable).
        # El upload local vive en _videos hasta cerrar la app, para que
        # "Reintentar" pueda reusar el mismo video_token sin re-subir.
        cleanup_video=(source_kind == "youtube"),
    )
    manager.submit(job)
    return JobCreateResponse(job_id=job.id)


@api.get("/jobs/{job_id}", response_model=JobStatus)
async def get_job(job_id: str) -> JobStatus:
    job = manager.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job no encontrado.")
    return job.to_status()


@api.get("/jobs/{job_id}/events")
async def job_events(job_id: str) -> StreamingResponse:
    job = manager.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job no encontrado.")

    async def stream():
        last = None
        while True:
            status = job.to_status()
            payload = status.model_dump_json()
            if payload != last:
                yield f"data: {payload}\n\n"
                last = payload
            if status.status in TERMINAL:
                break
            await asyncio.sleep(0.4)

    return StreamingResponse(
        stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@api.delete("/jobs/{job_id}")
async def cancel_job(job_id: str) -> dict:
    if not manager.cancel(job_id):
        raise HTTPException(status_code=404, detail="Job no encontrado.")
    return {"cancelled": True}


@api.get("/jobs/{job_id}/thumb/{name}")
async def get_thumb(job_id: str, name: str) -> FileResponse:
    return _serve_asset(job_id, name, "image/jpeg", "Thumbnail")


@api.get("/jobs/{job_id}/clip/{name}")
async def get_clip(job_id: str, name: str) -> FileResponse:
    return _serve_asset(job_id, name, "image/webp", "Clip")


def _serve_asset(job_id: str, name: str, media_type: str, label: str) -> FileResponse:
    job = manager.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job no encontrado.")
    # Evita path traversal: sólo nombres simples.
    if "/" in name or "\\" in name or ".." in name:
        raise HTTPException(status_code=400, detail="Nombre inválido.")
    path = job.thumb_dir / name
    if not path.exists():
        raise HTTPException(status_code=404, detail=f"{label} no encontrado.")
    return FileResponse(str(path), media_type=media_type)


app.include_router(api)


# --------------------------------------------------------------------------
# Frontend estático
# --------------------------------------------------------------------------
@app.get("/healthz")
async def healthz() -> dict:
    return {"status": "ok", "app": settings.app_name, "version": settings.version}


@app.get("/")
async def index(token: str | None = Query(None)) -> FileResponse:
    # El launcher abre la app con ?token=...; el frontend lo lee de la URL.
    return FileResponse(str(settings.web_dir / "index.html"))


app.mount("/", StaticFiles(directory=str(settings.web_dir), html=True), name="web")
