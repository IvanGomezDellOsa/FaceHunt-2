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

# ¿Hay una build acelerada de onnxruntime (DirectML/CUDA) ya instalada? Hay que
# preservarla: requirements.txt fija la de CPU y, como son excluyentes, la pisaría.
$accel = python -m pip list 2>$null |
    Select-String -Pattern "^onnxruntime-(directml|gpu)\s" |
    ForEach-Object { ($_ -split "\s+")[0] } |
    Select-Object -First 1

Write-Host "==> Instalando dependencias + PyInstaller" -ForegroundColor Cyan
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python -m pip install pyinstaller

if ($accel) {
    Write-Host "==> Restaurando build acelerada de onnxruntime: $accel" -ForegroundColor Cyan
    python -m pip uninstall -y onnxruntime onnxruntime-directml onnxruntime-gpu
    python -m pip install $accel
}

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
    # Busca cualquier versión instalada (Inno Setup 6, 7, ...) en ambos Program Files.
    $iscc = Get-ChildItem -Path @(${env:ProgramFiles}, ${env:ProgramFiles(x86)}) `
        -Filter "ISCC.exe" -Recurse -ErrorAction SilentlyContinue |
        Where-Object { $_.DirectoryName -like "*Inno Setup*" } |
        Select-Object -First 1 -ExpandProperty FullName
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
