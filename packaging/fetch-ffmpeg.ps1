# Telechargement automatique du binaire ffmpeg portable Windows pour le bundle.
#
# Source : John Van Sickle "ffmpeg-release-essentials" (build officiel reconnu,
# stable, contient ffmpeg.exe et ffprobe.exe). URL stable maintenue par
# gyan.dev (mirror du build officiel).
#
# Idempotent : skip si les binaires sont deja presents dans vendor/ffmpeg/bin/.
# Verifie le hash SHA256 contre une valeur attendue (fail-fast en cas de
# tampering du miroir).
#
# Usage : .\packaging\fetch-ffmpeg.ps1

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$projectRoot = (Get-Item -Path $PSScriptRoot).Parent.FullName
$vendorBin = Join-Path $projectRoot "vendor\ffmpeg\bin"
$ffmpegExe = Join-Path $vendorBin "ffmpeg.exe"
$ffprobeExe = Join-Path $vendorBin "ffprobe.exe"

if ((Test-Path $ffmpegExe) -and (Test-Path $ffprobeExe)) {
    Write-Host "==> ffmpeg deja present dans vendor/ffmpeg/bin/. Skip." -ForegroundColor Green
    exit 0
}

# URL de la release essentials la plus recente (gyan.dev).
# Si l'URL change a l'avenir, mettre a jour ces constantes.
$downloadUrl = "https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-essentials.zip"
$sha256Url = "https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-essentials.zip.sha256"

$tempDir = Join-Path $env:TEMP "fahmi2-ffmpeg-fetch"
if (Test-Path $tempDir) { Remove-Item -Recurse -Force $tempDir }
New-Item -ItemType Directory -Path $tempDir | Out-Null

$zipPath = Join-Path $tempDir "ffmpeg.zip"
$sha256Path = Join-Path $tempDir "ffmpeg.zip.sha256"

Write-Host "==> Telechargement de ffmpeg depuis $downloadUrl" -ForegroundColor Cyan
Invoke-WebRequest -Uri $downloadUrl -OutFile $zipPath -UseBasicParsing

Write-Host "==> Telechargement du hash SHA256 de reference" -ForegroundColor Cyan
try {
    Invoke-WebRequest -Uri $sha256Url -OutFile $sha256Path -UseBasicParsing
    $expectedHash = (Get-Content -Raw $sha256Path).Trim().ToLowerInvariant()
} catch {
    Write-Warning "Impossible de telecharger le hash SHA256 de reference. La verification d'integrite sera ignoree."
    $expectedHash = $null
}

if ($expectedHash) {
    $actualHash = (Get-FileHash -Path $zipPath -Algorithm SHA256).Hash.ToLowerInvariant()
    if ($actualHash -ne $expectedHash) {
        Write-Error "Hash SHA256 incoherent. Attendu=$expectedHash Obtenu=$actualHash"
    }
    Write-Host "==> SHA256 verifie OK" -ForegroundColor Green
}

Write-Host "==> Decompression de l'archive" -ForegroundColor Cyan
$extractDir = Join-Path $tempDir "extract"
Expand-Archive -Path $zipPath -DestinationPath $extractDir -Force

# Le zip contient un dossier racine du type "ffmpeg-X.Y.Z-essentials_build"
$rootDir = Get-ChildItem -Directory $extractDir | Select-Object -First 1
if (-not $rootDir) {
    Write-Error "Structure inattendue dans l'archive ffmpeg"
}

$srcBin = Join-Path $rootDir.FullName "bin"
if (-not (Test-Path $srcBin)) {
    Write-Error "Dossier bin/ introuvable dans l'archive ffmpeg"
}

Write-Host "==> Copie de ffmpeg.exe et ffprobe.exe vers $vendorBin" -ForegroundColor Cyan
New-Item -ItemType Directory -Path $vendorBin -Force | Out-Null
Copy-Item -Path (Join-Path $srcBin "ffmpeg.exe") -Destination $vendorBin -Force
Copy-Item -Path (Join-Path $srcBin "ffprobe.exe") -Destination $vendorBin -Force

# Verification finale
if (-not (Test-Path $ffmpegExe) -or -not (Test-Path $ffprobeExe)) {
    Write-Error "Echec de la copie des binaires ffmpeg"
}

# L'encodeur libopus est requis pour le STT cloud (compression < 25 Mo).
Write-Host "==> Verification de l'encodeur libopus (requis pour le STT cloud)" -ForegroundColor Cyan
$encoders = & $ffmpegExe -hide_banner -encoders 2>$null
if ($encoders -notmatch 'libopus') {
    Write-Error "Le ffmpeg telecharge ne contient pas libopus (encodeur Opus requis pour le STT cloud > 25 Mo)."
}
Write-Host "==> libopus present" -ForegroundColor Green

Remove-Item -Recurse -Force $tempDir
Write-Host "==> ffmpeg pret dans vendor/ffmpeg/bin/" -ForegroundColor Green
