# Telechargement automatique du binaire yt-dlp portable Windows pour le bundle.
#
# Source : release officielle GitHub yt-dlp/yt-dlp (binaire standalone yt-dlp.exe).
# yt-dlp casse regulierement quand YouTube evolue : on prend systematiquement la
# derniere release ("latest"). Le binaire reste remplacable au runtime sans
# rebuild (variable d'environnement FAHMI2_YTDLP, ou remplacement du yt-dlp.exe
# bundle).
#
# Idempotent : skip si le binaire est deja present dans vendor/yt-dlp/.
#
# Usage : .\packaging\fetch-ytdlp.ps1
#         .\packaging\fetch-ytdlp.ps1 -Force   (force le re-telechargement)

param(
    [switch]$Force
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$projectRoot = (Get-Item -Path $PSScriptRoot).Parent.FullName
$vendorDir = Join-Path $projectRoot "vendor\yt-dlp"
$ytdlpExe = Join-Path $vendorDir "yt-dlp.exe"

if ((Test-Path $ytdlpExe) -and (-not $Force)) {
    Write-Host "==> yt-dlp deja present dans vendor/yt-dlp/. Skip (utiliser -Force pour rafraichir)." -ForegroundColor Green
    exit 0
}

# Derniere release officielle (binaire standalone Windows).
$downloadUrl = "https://github.com/yt-dlp/yt-dlp/releases/latest/download/yt-dlp.exe"

New-Item -ItemType Directory -Path $vendorDir -Force | Out-Null

Write-Host "==> Telechargement de yt-dlp depuis $downloadUrl" -ForegroundColor Cyan
Invoke-WebRequest -Uri $downloadUrl -OutFile $ytdlpExe -UseBasicParsing

if (-not (Test-Path $ytdlpExe)) {
    Write-Error "Echec du telechargement de yt-dlp.exe"
}

# Verification basique : le binaire repond a --version.
Write-Host "==> Verification de yt-dlp --version" -ForegroundColor Cyan
$version = (& $ytdlpExe --version 2>$null)
if (-not $version) {
    Write-Error "Le yt-dlp telecharge ne repond pas a --version (binaire invalide ?)."
}
Write-Host "==> yt-dlp $version pret dans vendor/yt-dlp/" -ForegroundColor Green
Write-Host "    (a bundler a la racine du bundle dans packaging/fahmi2.spec, comme ffmpeg.exe)" -ForegroundColor DarkGray
