# Claudy backup script
# Comprime ~/.claudy en un .zip con timestamp.
# Uso:
#   .\backup-claudy.ps1
#   .\backup-claudy.ps1 -OutDir "G:\Mi unidad\Backups"
#   .\backup-claudy.ps1 -IncludeLogs   # incluye *.log (por defecto los excluye)

param(
    [string]$OutDir = "$env:USERPROFILE\Documents\Claudy-Backups",
    [switch]$IncludeLogs
)

$ErrorActionPreference = "Stop"
$src = Join-Path $env:USERPROFILE ".claudy"

if (-not (Test-Path $src)) {
    Write-Host "No existe $src - nada que respaldar." -ForegroundColor Yellow
    exit 1
}

if (-not (Test-Path $OutDir)) {
    New-Item -ItemType Directory -Path $OutDir -Force | Out-Null
}

$ts = Get-Date -Format "yyyyMMdd-HHmmss"
$zipPath = Join-Path $OutDir "claudy-backup-$ts.zip"

# Build temp staging dir to exclude unwanted files
$staging = Join-Path $env:TEMP "claudy-bk-$ts"
New-Item -ItemType Directory -Path $staging -Force | Out-Null

Write-Host "Copiando .claudy a staging..." -ForegroundColor Cyan
$excludeArgs = @("/MIR", "/XJ", "/R:1", "/W:1", "/NFL", "/NDL", "/NJH", "/NJS", "/NC", "/NS", "/NP")
if (-not $IncludeLogs) {
    $excludeArgs += @("/XF", "*.log")
}
# Always exclude transient subdirs
$excludeArgs += @("/XD", "subagents", "batches", "screenshots", "plots", "diagrams", "browser", "webcam")

$null = robocopy $src $staging @excludeArgs
# Robocopy returns 0-7 as success codes; reset $LASTEXITCODE so calling shells don't think it failed
if ($LASTEXITCODE -lt 8) { $global:LASTEXITCODE = 0 }

Write-Host "Comprimiendo a $zipPath..." -ForegroundColor Cyan
Compress-Archive -Path "$staging\*" -DestinationPath $zipPath -CompressionLevel Optimal -Force

Remove-Item -Recurse -Force $staging

$size = (Get-Item $zipPath).Length
$sizeMB = [math]::Round($size / 1MB, 2)
Write-Host "Backup listo:" -ForegroundColor Green
Write-Host "  $zipPath ($sizeMB MB)"

# Conservar solo los ultimos 10 backups
$backups = Get-ChildItem -Path $OutDir -Filter "claudy-backup-*.zip" | Sort-Object LastWriteTime -Descending
if ($backups.Count -gt 10) {
    $backups | Select-Object -Skip 10 | ForEach-Object {
        Remove-Item $_.FullName -Force
        Write-Host "  Limpiando antiguo: $($_.Name)" -ForegroundColor DarkGray
    }
}
