# -*- mode: python ; coding: utf-8 -*-
"""Spec de PyInstaller para FaceHunt-2 (modo one-dir).

Construir desde la raíz del proyecto:
    pyinstaller build/FaceHunt2.spec --noconfirm

Genera dist/FaceHunt2/FaceHunt2.exe (doble clic, sin instalar Python).
"""

import os
from PyInstaller.utils.hooks import collect_all

ROOT = os.path.dirname(os.path.abspath(SPECPATH))  # carpeta FaceHunt-2

datas = [
    (os.path.join(ROOT, "web"), "web"),
    (os.path.join(ROOT, "app", "models"), os.path.join("app", "models")),
]
binaries = []
hiddenimports = []

# Paquetes que PyInstaller no rastrea bien por sí solo: los recolectamos enteros.
for pkg in [
    "insightface",
    "onnxruntime",
    "cv2",
    "skimage",
    "scipy",
    "yt_dlp",
    "uvicorn",
    "webview",
    "fastapi",
    "pydantic",
]:
    try:
        d, b, h = collect_all(pkg)
        datas += d
        binaries += b
        hiddenimports += h
    except Exception as exc:  # un paquete opcional puede faltar (p. ej. webview)
        print(f"[spec] aviso: no pude recolectar {pkg}: {exc}")

a = Analysis(
    [os.path.join(ROOT, "run.py")],
    pathex=[ROOT],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    runtime_hooks=[],
    excludes=["tensorflow", "torch", "matplotlib", "tkinter"],
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="FaceHunt2",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,  # app de ventana: sin consola
    icon=os.path.join(ROOT, "web", "assets", "icon.ico"),
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="FaceHunt2",
)
