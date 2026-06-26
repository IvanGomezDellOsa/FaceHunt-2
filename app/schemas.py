"""Modelos Pydantic de la API (request/response)."""

from __future__ import annotations

from pydantic import BaseModel, Field


class ReferenceResponse(BaseModel):
    reference_id: str
    message: str
    num_images: int
    multiple_faces_warning: bool = False


class VideoValidateResponse(BaseModel):
    kind: str                      # 'local' | 'youtube'
    message: str
    title: str = ""
    duration: float = 0.0
    video_token: str | None = None  # presente sólo para archivos locales


class JobCreateRequest(BaseModel):
    reference_id: str
    video_token: str | None = None
    video_url: str | None = None
    # "balanced" (rápido) o "precision" (más esfuerzo de detección).
    mode: str = "balanced"


class JobCreateResponse(BaseModel):
    job_id: str


class RangeOut(BaseModel):
    start: float
    end: float
    start_label: str
    end_label: str
    range_label: str
    best_timestamp: float
    best_score: float
    count: int
    thumbnail_url: str | None = None
    clip_url: str | None = None     # WebP animado del momento; null si no se generó
    seek_url: str | None = None     # link de YouTube con &t=; null para local


class JobStatus(BaseModel):
    id: str
    status: str                     # pending|downloading|processing|done|error|cancelled
    progress: float                 # 0..1
    processed: int = 0
    total: int = 0
    matches: int = 0
    message: str = ""
    provider: str = ""
    using_gpu: bool = False
    source_kind: str = ""           # 'local' | 'youtube'
    fps: float = 0.0
    duration: float = 0.0
    ranges: list[RangeOut] = Field(default_factory=list)
