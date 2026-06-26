[English](README.en.md) | [Español](README.md)

# FaceHunt 2

FaceHunt 2 is a **100% local desktop application** that finds every appearance of a
person inside a video from a single reference photo. You upload one or more photos
and a video (local file or YouTube URL) and get the **exact time ranges** where that
person appears, each one with a thumbnail, an animated mini-clip and a direct jump
to that moment.

> A complete rewrite of [FaceHunt](https://github.com/IvanGomezDellOsa/FaceHunt).
> No Tkinter, no TensorFlow, no dependency on an online server. ~10x faster, higher
> accuracy, more complete results and new features.

---

## Demo

<p align="center">
  <a href="https://www.youtube.com/watch?v=rJLyYJcEm7c" target="_blank">
    <img
      alt="Watch the demo on YouTube"
      src="https://img.shields.io/badge/▶_WATCH_DEMO_ON_YOUTUBE-FF0000?style=for-the-badge&logo=youtube&logoColor=white"
      height="60"
    >
  </a>
</p>

---

## Features

- **100% local and private** — Your photos and videos never leave your device. No online server, no cloud upload.

- **State-of-the-art facial recognition** — InsightFace `antelopev2` engine (SCRFD-10G + ArcFace ResNet100 @ Glint360K, 512-d embeddings) on ONNXRuntime, with flip-TTA for higher recall.

- **Automatic GPU acceleration** — Detects and uses the best available execution provider (CUDA → DirectML → CPU). Works with NVIDIA, AMD and Intel GPUs on Windows via DirectML.

- **Temporal tracking** — Groups faces into tracklets across frames and matches against the aggregated embedding, recovering appearances in degraded frames (profile, occlusion, low resolution).

- **Detailed results** — Appearance ranges with a face thumbnail, an animated mini-clip of the moment and a clickable timeline of the whole video.

- **Asynchronous processing** — Background jobs with live progress via SSE (percentage, ETA and matches), cancellation included.

- **Robust reference** — Accepts multiple photos of the same person and averages their embeddings for a more stable identification.

---

## How to use

1. **Open the app** (`FaceHunt2.exe`).
2. **Reference:** upload one or more front-facing photos of the person to look for.
3. **Video:** choose a local file or paste a YouTube URL.
4. **Mode:** pick *Fast* or *Thorough* (more frames per second and smaller faces).
5. **Results:** watch the live progress and, when it finishes, browse the appearance ranges. Click any of them (or the timeline) to jump to that moment.

> On Windows 11 the app opens in a native window (WebView2, already preinstalled). If it isn't available, it automatically opens the default browser.

---

## Download

<p align="center">
  <a href="https://github.com/IvanGomezDellOsa/FaceHunt-2/releases" target="_blank">
    <img
      alt="Download"
      src="https://img.shields.io/badge/⬇_DOWNLOAD_(Releases)-2563eb?style=for-the-badge"
      height="55"
    >
  </a>
</p>

---

<details>
<summary>Architecture and main modules</summary>

```
app/
  config.py            Central configuration + path resolution (dev and PyInstaller)
  main.py              Launcher: uvicorn in a thread + pywebview window (or browser)
  server.py            FastAPI: routes, local token, SSE, static files
  schemas.py           Pydantic models (request/response)
  jobs.py              Async JobManager: state, progress, cancellation
  pipeline/
    engine.py          InsightFace/ONNX, auto-provider, detect + embeddings
    reference.py       Reference photo(s) -> normalized 512-d embedding
    video_source.py    Validation and metadata (local / YouTube)
    downloader.py      YouTube download with yt-dlp
    frame_reader.py    Frame sampling (grab/retrieve) with producer thread + queue
    recognizer.py      Cosine comparison + tracking + thumbnails (green box)
    tracker.py         Tracklets (IoU + appearance) + temporal aggregation
    clips.py           Animated WebP mini-clips around the best frame
    ranges.py          Grouping of matches into ranges
  utils/
    timefmt.py         Time formatting + YouTube links with &t
    files.py           Safe filenames and temporaries
    power.py           Prevents system sleep during analysis
web/                   Frontend (HTML/CSS/JS, no build step)
build/                 fetch_models.py, FaceHunt2.spec, build_windows.ps1
tests/                 Pure-logic tests (pytest)
```

**Search flow**
1. `POST /api/reference` validates the photo(s) and stores the embedding → `reference_id`.
2. `POST /api/video/validate` validates the video (local → `video_token`; YouTube validates the URL).
3. `POST /api/jobs` creates the job → `job_id` and starts processing in a thread.
4. `GET /api/jobs/{id}/events` (SSE) streams progress, ETA and matches live.
5. When it finishes, each range carries a thumbnail, a mini-clip and a jump link.

</details>

<details open>
<summary>FaceHunt v1 → v2</summary>

FaceHunt 2 rewrote the entire stack compared to the previous version:

- **~10x faster** video analysis (ONNXRuntime with GPU vs TensorFlow-CPU, producer-consumer pipeline).
- **Higher accuracy**: ArcFace ResNet100 with 512-d embeddings trained on Glint360K + flip-TTA and temporal tracking (vs FaceNet 128-d).
- **More complete results**: appearance ranges with thumbnail, animated mini-clip and timeline (vs loose per-second timestamps).
- **New features**: multi-photo reference averaging, real-time job cancellation, live SSE progress, one-click executable with no installation required.

</details>

---

## License and models

The **InsightFace weights** (`antelopev2`, `buffalo_*`) have a **research / non-commercial** license; for commercial use you would need to license them with InsightFace or migrate to permissive weights (e.g. AdaFace, MIT).

---

## Author

**Iván Gómez Dell'Osa**

- GitHub: https://github.com/IvanGomezDellOsa
- Email: ivangomezdellosa@gmail.com
- Linkedin: https://www.linkedin.com/in/ivangomezdellosa/
---
