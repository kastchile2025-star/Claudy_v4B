# Claudy restore script
# Restaura un backup .zip a ~/.claudy (renombra el existente como .claudy.old.<ts>)
# Uso:
#   .\restore-claudy.ps1                          # restaura el backup mas reciente
#   .\restore-claudy.ps1 -ZipPath "ruta\al.zip"   # restaura uno especifico
#   .\restore-claudy.ps1 -BackupDir "G:\Backups"  # busca en otra carpeta

param(
    [string]$ZipPath = "",
    [string]$BackupDir = "$env:USERPROFILE\Documents\Claudy-Backups",
    [switch]$Merge
)

$ErrorActionPreference = "Stop"

if (-not $ZipPath) {
    if (-not (Test-Path $BackupDir)) {
        Write-Host "No existe $BackupDir" -ForegroundColor Red
        exit 1
    }
    $latest = Get-ChildItem -Path $BackupDir -Filter "claudy-backup-*.zip" -ErrorAction SilentlyContinue |
              Sort-Object LastWriteTime -Descending | Select-Object -First 1
    if (-not $latest) {
        Write-Host "No hay backups en $BackupDir" -ForegroundColor Red
        exit 1
    }
    $ZipPath = $latest.FullName
}

if (-not (Test-Path $ZipPath)) {
    Write-Host "No existe el zip: $ZipPath" -ForegroundColor Red
    exit 1
}

$dest = Join-Path $env:USERPROFILE ".claudy"
$ts = Get-Date -Format "yyyyMMdd-HHmmss"

Write-Host "Restaurando $ZipPath a $dest" -ForegroundColor Cyan

if (Test-Path $dest) {
    if ($Merge) {
        Write-Host "Modo merge: los archivos del zip sobrescriben los locales con mismo nombre." -ForegroundColor Yellow
    } else {
        $backup = "$dest.old.$ts"
        Write-Host "Renombrando carpeta existente a $backup" -ForegroundColor Yellow
        Rename-Item -Path $dest -NewName ".claudy.old.$ts"
    }
}

if (-not (Test-Path $dest)) {
    New-Item -ItemType Directory -Path $dest -Force | Out-Null
}

Expand-Archive -Path $ZipPath -DestinationPath $dest -Force

Write-Host "Restauracion completa." -ForegroundColor Green
Write-Host "Contenido:" -ForegroundColor Cyan
Get-ChildItem -Path $dest | Select-Object Name, LastWriteTime | Format-Table -AutoSize
