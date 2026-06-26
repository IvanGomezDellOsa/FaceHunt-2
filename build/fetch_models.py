"""Descarga el modelo InsightFace a ``app/models/`` para uso offline.

Por defecto baja ``antelopev2`` (ResNet100). Ejecutar UNA vez antes de
empaquetar (o antes del primer uso sin internet):

    python build/fetch_models.py

Maneja el bug conocido de algunos packs (antelopev2) cuyo zip se descomprime
con una carpeta anidada ``<name>/<name>/*.onnx``: lo aplana automáticamente.
"""

from __future__ import annotations

import sys
from pathlib import Path

# Permite importar el paquete `app` al correr el script directamente.
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from app.config import settings  # noqa: E402
from app.pipeline.engine import flatten_model_dir  # noqa: E402


def _has_onnx(model_dir: Path) -> bool:
    return model_dir.is_dir() and any(model_dir.glob("*.onnx"))


def main() -> int:
    settings.insightface_root.mkdir(parents=True, exist_ok=True)
    model_dir = settings.models_dir / settings.model_name
    print(f"Preparando '{settings.model_name}' en {settings.models_dir} …")

    from insightface.app import FaceAnalysis

    # 1) Disparar la descarga (si hace falta). Algunos packs descomprimen mal y
    #    el constructor falla con AssertionError: lo toleramos y aplanamos.
    if not _has_onnx(model_dir):
        try:
            FaceAnalysis(name=settings.model_name, root=str(settings.insightface_root))
        except AssertionError:
            print("Descarga con carpeta anidada detectada; reorganizando…")
        except Exception:
            raise

    # 2) Aplanar la posible carpeta anidada.
    flatten_model_dir(model_dir)

    if not _has_onnx(model_dir):
        print(
            f"ERROR: no se encontraron archivos .onnx en {model_dir}.",
            file=sys.stderr,
        )
        return 1

    # 3) Verificar que carga de verdad.
    fa = FaceAnalysis(name=settings.model_name, root=str(settings.insightface_root))
    fa.prepare(ctx_id=-1, det_size=(settings.det_size, settings.det_size))

    print(f"Listo. Modelo disponible y verificado en {model_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
