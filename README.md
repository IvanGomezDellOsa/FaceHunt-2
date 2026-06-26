[Español](README.md) | [English](README.en.md)

# FaceHunt-2

FaceHunt-2 es una **aplicación de escritorio 100% local** que encuentra todas las
apariciones de una persona dentro de un video a partir de una foto de referencia.
Subís una o varias fotos y un video (archivo local o URL de YouTube) y obtenés los
**rangos de tiempo exactos** en los que aparece esa persona, cada uno con
miniatura, mini-clip animado y un salto directo a ese momento.

> Reescritura completa de [FaceHunt](https://github.com/IvanGomezDellOsa/FaceHunt).
> Sin Tkinter, sin TensorFlow, sin depender de un servidor online.

<p align="center">
  <img src="https://img.shields.io/badge/Python-3.10+-3776AB?logo=python&logoColor=white">
  <img src="https://img.shields.io/badge/Windows-0078D6?logo=windows&logoColor=white">
  <img src="https://img.shields.io/badge/100%25-Local_y_privado-22c55e">
  <img src="https://img.shields.io/badge/GPU-CUDA_/_DirectML-76B900">
</p>

---

## Demo

<p align="center">
  <a href="https://www.youtube.com/watch?v=rJLyYJcEm7c" target="_blank">
    <img
      alt="Ver demo en YouTube"
      src="https://img.shields.io/badge/▶_VER_DEMO_EN_YOUTUBE-FF0000?style=for-the-badge&logo=youtube&logoColor=white"
      height="60"
    >
  </a>
</p>

---

## Características

- **100% local y privado** — Tus fotos y videos (datos biométricos) nunca salen de tu equipo. No hay servidor online ni subida a la nube.

- **Reconocimiento facial de última generación** — Motor InsightFace `antelopev2` (SCRFD-10G + ArcFace ResNet100 @ Glint360K, embeddings de 512-d) sobre ONNXRuntime, con flip-TTA para mayor recall.

- **Aceleración por GPU automática** — Detecta y usa el mejor execution provider disponible (CUDA → DirectML → CPU). Funciona con GPUs NVIDIA, AMD e Intel en Windows vía DirectML.

- **Seguimiento temporal** — Agrupa las caras en tracklets entre frames y compara contra el embedding agregado, recuperando apariciones en cuadros degradados (perfil, oclusión, baja resolución).

- **Resultados detallados** — Rangos de aparición con miniatura de la cara, mini-clip animado del momento y una línea de tiempo clicable de todo el video.

- **Procesamiento asíncrono** — Jobs en segundo plano con progreso en vivo vía SSE (porcentaje, ETA y coincidencias), cancelación incluida.

- **Referencia robusta** — Admite varias fotos de la misma persona y promedia sus embeddings para una identificación más estable.

---

## Cómo usar

1. **Abrí la app** (`FaceHunt2.exe`).
2. **Referencia:** subí una o varias fotos frontales y nítidas de la persona a buscar.
3. **Video:** elegí un archivo local o pegá una URL de YouTube.
4. **Modo:** elegí *Rápido* o *Exhaustivo* (más cuadros por segundo y caras más pequeñas).
5. **Resultados:** mirá el progreso en vivo y, al terminar, recorré los rangos de aparición. Clic en cualquiera (o en la línea de tiempo) para saltar a ese momento.

> En Windows 11 la app se abre en una ventana nativa (WebView2, ya preinstalado). Si no estuviera disponible, abre automáticamente el navegador por defecto.

---

## Descargar

<p align="center">
  <a href="https://github.com/IvanGomezDellOsa/FaceHunt-2/releases" target="_blank">
    <img
      alt="Descargar"
      src="https://img.shields.io/badge/⬇_DESCARGAR_(Releases)-2563eb?style=for-the-badge"
      height="55"
    >
  </a>
</p>

No requiere instalar Python ni nada más.

---

<details>
<summary>Arquitectura y módulos principales</summary>

```
app/
  config.py            Configuración central + resolución de rutas (dev y PyInstaller)
  main.py              Launcher: uvicorn en thread + ventana pywebview (o navegador)
  server.py            FastAPI: rutas, token local, SSE, archivos estáticos
  schemas.py           Modelos Pydantic (request/response)
  jobs.py              JobManager async: estado, progreso, cancelación
  pipeline/
    engine.py          InsightFace/ONNX, auto-provider, detect + embeddings
    reference.py       Foto(s) de referencia -> embedding 512-d normalizado
    video_source.py    Validación y metadatos (local / YouTube)
    downloader.py      Descarga de YouTube con yt-dlp
    frame_reader.py    Muestreo de frames (grab/retrieve) con hilo productor + cola
    recognizer.py      Comparación coseno + tracking + thumbnails (cuadro verde)
    tracker.py         Tracklets (IoU + apariencia) + agregación temporal
    clips.py           Mini-clips WebP animados alrededor del mejor frame
    ranges.py          Agrupado de matches en rangos
  utils/
    timefmt.py         Formato de tiempo + enlaces YouTube con &t
    files.py           Nombres seguros y temporales
    power.py           Evita la suspensión del sistema durante el análisis
web/                   Frontend (HTML/CSS/JS, sin build step)
build/                 fetch_models.py, FaceHunt2.spec, build_windows.ps1
tests/                 Tests de la lógica pura (pytest)
```

**Flujo de una búsqueda**
1. `POST /api/reference` valida la(s) foto(s) y guarda el embedding → `reference_id`.
2. `POST /api/video/validate` valida el video (local → `video_token`; YouTube valida la URL).
3. `POST /api/jobs` crea el job → `job_id` y arranca el procesamiento en un hilo.
4. `GET /api/jobs/{id}/events` (SSE) transmite progreso, ETA y matches en vivo.
5. Al terminar, cada rango trae miniatura, mini-clip y enlace de salto.

</details>

<details>
<summary>FaceHunt v1 → v2</summary>

FaceHunt-2 reescribió el stack completo respecto a la versión anterior:

- **~10x más rápido** en el análisis de video (ONNXRuntime con GPU vs TensorFlow-CPU, pipeline productor-consumidor).
- **Mayor precisión**: ArcFace ResNet100 con embeddings de 512-d entrenado en Glint360K + flip-TTA y tracking temporal (vs FaceNet 128-d).
- **Resultados más completos**: rangos de aparición con miniatura, mini-clip animado y línea de tiempo (vs timestamps sueltos por segundo).
- **Nuevas funcionalidades**: referencia con múltiples fotos promediadas, cancelación de jobs en tiempo real, progreso por SSE, ejecutable de un clic sin instalación.

</details>

---

## Licencia y modelos

Los **pesos de InsightFace** (`antelopev2`, `buffalo_*`) tienen licencia de **investigación / uso no comercial**; para uso comercial se requiere licenciarlos con InsightFace o migrar a pesos permisivos (p. ej. AdaFace, MIT).

---

## Autor

**Iván Gómez Dell'Osa**

- GitHub: https://github.com/IvanGomezDellOsa
- Email: ivangomezdellosa@gmail.com
- Linkedin: https://www.linkedin.com/in/ivangomezdellosa/
---
