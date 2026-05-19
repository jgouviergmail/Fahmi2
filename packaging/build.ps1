# Script de build PyInstaller pour Fahmi2 (Windows).
#
# Build entierement automatise : telecharge ffmpeg si absent puis lance
# PyInstaller. L'utilisateur final n'a aucune action manuelle a faire.
#
# Pre-requis (developpeur uniquement) :
#   - Python 3.11 ou 3.12 + venv active avec pip install -e ".[dev]" + pyinstaller
#
# Usage : .\packaging\build.ps1

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$projectRoot = (Get-Item -Path $PSScriptRoot).Parent.FullName
Set-Location $projectRoot

Write-Host "==> Etape 1/4 : Recuperation de ffmpeg (idempotent)" -ForegroundColor Cyan
& (Join-Path $PSScriptRoot "fetch-ffmpeg.ps1")

Write-Host "==> Etape 2/4 : Nettoyage des anciens artefacts" -ForegroundColor Cyan
if (Test-Path "build") { Remove-Item -Recurse -Force "build" }
if (Test-Path "dist") { Remove-Item -Recurse -Force "dist" }

Write-Host "==> Etape 3/4 : Verification de pyinstaller" -ForegroundColor Cyan
$pyi = (Get-Command pyinstaller -ErrorAction SilentlyContinue)
if (-not $pyi) {
    Write-Error "pyinstaller introuvable dans le PATH. Active le venv ou installe via 'pip install pyinstaller'."
}

Write-Host "==> Etape 4/4 : Lancement de PyInstaller" -ForegroundColor Cyan
pyinstaller packaging/fahmi2.spec --noconfirm --clean

Write-Host "==> Build termine. Sortie dans dist/Fahmi2/" -ForegroundColor Green
Write-Host "==> Pour generer le .zip de distribution : .\packaging\make-portable-zip.ps1" -ForegroundColor Yellow
