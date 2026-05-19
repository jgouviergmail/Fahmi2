# Script de build PyInstaller pour Fahmi2 (Windows).
#
# Pré-requis :
#   - Python 3.12 (ou 3.11) + venv activé avec pip install -e ".[dev]" + pyinstaller
#   - Binaire ffmpeg dans vendor/ffmpeg/bin/ (ffmpeg.exe + ffprobe.exe). Cf.
#     packaging/README.md pour les instructions de téléchargement.
#
# Usage : .\packaging\build.ps1

$ErrorActionPreference = "Stop"

$projectRoot = (Get-Item -Path $PSScriptRoot).Parent.FullName
Set-Location $projectRoot

Write-Host "==> Nettoyage des anciens artefacts" -ForegroundColor Cyan
if (Test-Path "build") { Remove-Item -Recurse -Force "build" }
if (Test-Path "dist") { Remove-Item -Recurse -Force "dist" }

Write-Host "==> Vérification de pyinstaller" -ForegroundColor Cyan
$pyi = (Get-Command pyinstaller -ErrorAction SilentlyContinue)
if (-not $pyi) {
  Write-Error "pyinstaller introuvable dans le PATH. Active le venv ou installe via pip install pyinstaller."
}

Write-Host "==> Lancement de PyInstaller" -ForegroundColor Cyan
pyinstaller packaging/fahmi2.spec --noconfirm --clean

Write-Host "==> Build terminé. Sortie dans dist/Fahmi2/" -ForegroundColor Green
