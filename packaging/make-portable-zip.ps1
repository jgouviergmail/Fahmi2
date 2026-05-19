# Génère un .zip portable de distribution depuis dist/Fahmi2/.
#
# Usage : .\packaging\make-portable-zip.ps1

$ErrorActionPreference = "Stop"

$projectRoot = (Get-Item -Path $PSScriptRoot).Parent.FullName
Set-Location $projectRoot

if (-not (Test-Path "dist/Fahmi2")) {
  Write-Error "dist/Fahmi2 introuvable. Lance d'abord packaging/build.ps1."
}

# Détecte la version depuis pyproject.toml
$pyproject = Get-Content -Raw "pyproject.toml"
if ($pyproject -match 'version\s*=\s*"([^"]+)"') {
  $version = $Matches[1]
} else {
  $version = "0.0.0.dev"
}

$zipName = "Fahmi2-$version-win64.zip"
$zipPath = Join-Path "dist" $zipName

if (Test-Path $zipPath) { Remove-Item -Force $zipPath }

Write-Host "==> Compression dans $zipPath" -ForegroundColor Cyan
Compress-Archive -Path "dist/Fahmi2/*" -DestinationPath $zipPath -CompressionLevel Optimal

Write-Host "==> Archive prête : $zipPath" -ForegroundColor Green
