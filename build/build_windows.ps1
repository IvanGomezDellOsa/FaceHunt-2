# ===========================================================================
# Construye FaceHunt-2 para Windows.
# Uso (desde la raíz del proyecto FaceHunt-2):
#     .\build\build_windows.ps1
# Resultados:
#   dist\FaceHunt2\FaceHunt2.exe   (one-dir, doble clic sin instalar nada)
#   dist\FaceHunt2-Setup.exe       (instalador, si Inno Setup está disponible)
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

# --- Instalador opcional (Inno Setup) --------------------------------------
# Si ISCC.exe (el compilador de Inno Setup) está en el PATH o en su ruta
# habitual, genera además dist\FaceHunt2-Setup.exe.
$iscc = (Get-Command iscc.exe -ErrorAction SilentlyContinue).Source
if (-not $iscc) {
    foreach ($p in @(
        "${env:ProgramFiles(x86)}\Inno Setup 6\ISCC.exe",
        "${env:ProgramFiles}\Inno Setup 6\ISCC.exe"
    )) {
        if (Test-Path $p) { $iscc = $p; break }
    }
}

if ($iscc) {
    Write-Host "==> Construyendo instalador con Inno Setup" -ForegroundColor Cyan
    & $iscc build\installer.iss
    Write-Host ""
    Write-Host "Listo. Instalador en: dist\FaceHunt2-Setup.exe" -ForegroundColor Green
} else {
    Write-Host ""
    Write-Host "Inno Setup no encontrado: omito el instalador." -ForegroundColor Yellow
    Write-Host "Instalalo desde https://jrsoftware.org/isdl.php y re-ejecutá," -ForegroundColor Yellow
    Write-Host "o compilá a mano:  iscc build\installer.iss" -ForegroundColor Yellow
}
