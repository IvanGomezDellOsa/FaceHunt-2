# ===========================================================================
# Construye el ejecutable de FaceHunt-2 para Windows (one-dir).
# Uso (desde la raíz del proyecto FaceHunt-2):
#     .\build\build_windows.ps1
# Resultado: dist\FaceHunt2\FaceHunt2.exe  (doble clic, sin instalar nada)
# ===========================================================================
$ErrorActionPreference = "Stop"

# Ubicarse en la raíz del proyecto (carpeta padre de \build)
Set-Location (Split-Path $PSScriptRoot -Parent)

Write-Host "==> Instalando dependencias + PyInstaller" -ForegroundColor Cyan
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python -m pip install pyinstaller

Write-Host "==> Descargando modelo InsightFace (offline)" -ForegroundColor Cyan
python build\fetch_models.py

Write-Host "==> Empaquetando con PyInstaller" -ForegroundColor Cyan
pyinstaller build\FaceHunt2.spec --noconfirm --distpath dist --workpath build\work

Write-Host ""
Write-Host "Listo. Ejecutable en: dist\FaceHunt2\FaceHunt2.exe" -ForegroundColor Green
