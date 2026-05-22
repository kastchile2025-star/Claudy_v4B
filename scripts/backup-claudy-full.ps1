# Claudy FULL backup script
# Respalda el proyecto completo + ~/.claudy a Google Drive (G:) o donde se le indique.
# Uso:
#   .\backup-claudy-full.ps1
#   .\backup-claudy-full.ps1 -OutDir "G:\Mi unidad\Claudy-Backups"
#   .\backup-claudy-full.ps1 -Quiet           # silencioso (para hooks/scheduled tasks)
#   .\backup-claudy-full.ps1 -KeepLast 5      # solo guarda los ultimos 5 backups

param(
    [string]$OutDir = "G:\Mi unidad\Claudy-Backups",
    [string]$ProjectDir = "",
    [int]$KeepLast = 7,
    [switch]$Quiet,
    [switch]$IncludeNodeModules
)

$ErrorActionPreference = "Stop"

function Log($msg, $color = "Cyan") {
    if (-not $Quiet) { Write-Host $msg -ForegroundColor $color }
}

# Auto-detect project dir (parent of /scripts)
if (-not $ProjectDir) {
    $ProjectDir = Split-Path -Parent $PSScriptRoot
}

if (-not (Test-Path $ProjectDir)) {
    Log "No existe el proyecto: $ProjectDir" "Red"
    exit 1
}

# Validate destination (G: drive must be mounted)
$root = Split-Path -Qualifier $OutDir
if (-not (Test-Path $root)) {
    Log "La unidad $root no esta disponible. Conecta Google Drive o usa otro -OutDir." "Red"
    exit 2
}

if (-not (Test-Path $OutDir)) {
    New-Item -ItemType Directory -Path $OutDir -Force | Out-Null
}

$ts = Get-Date -Format "yyyyMMdd-HHmmss"
$zipPath = Join-Path $OutDir "claudy-full-$ts.zip"
$staging = Join-Path $env:TEMP "claudy-full-bk-$ts"
New-Item -ItemType Directory -Path $staging -Force | Out-Null

# --- 1. Copiar el proyecto (sin node_modules, dist, etc por defecto) ---
Log "Copiando proyecto: $ProjectDir"
$projDst = Join-Path $staging "project"
New-Item -ItemType Directory -Path $projDst -Force | Out-Null

$xd = @("/XD",
    "$ProjectDir\.git",
    "$ProjectDir\dist",
    "$ProjectDir\.next",
    "$ProjectDir\.cache",
    "$ProjectDir\__pycache__",
    "$ProjectDir\.venv",
    "$ProjectDir\venv"
)
if (-not $IncludeNodeModules) {
    $xd += "$ProjectDir\node_modules"
}
$xf = @("/XF", "*.log", "*.pyc")

$null = robocopy $ProjectDir $projDst /MIR /XJ /R:1 /W:1 /NFL /NDL /NJH /NJS /NC /NS /NP @xd @xf
if ($LASTEXITCODE -lt 8) { $global:LASTEXITCODE = 0 } else {
    Log "robocopy fallo con codigo $LASTEXITCODE" "Red"
    Remove-Item -Recurse -Force $staging
    exit 3
}

# --- 2. Copiar ~/.claudy (memorias, app_index, skills, screenshots opcional) ---
$claudyHome = Join-Path $env:USERPROFILE ".claudy"
if (Test-Path $claudyHome) {
    Log "Copiando datos personales: $claudyHome"
    $homeDst = Join-Path $staging "user_claudy"
    New-Item -ItemType Directory -Path $homeDst -Force | Out-Null
    $null = robocopy $claudyHome $homeDst /MIR /XJ /R:1 /W:1 /NFL /NDL /NJH /NJS /NC /NS /NP `
        /XD "$claudyHome\subagents" "$claudyHome\batches" "$claudyHome\screenshots" `
            "$claudyHome\plots" "$claudyHome\diagrams" "$claudyHome\browser" "$claudyHome\webcam" `
        /XF "*.log"
    if ($LASTEXITCODE -lt 8) { $global:LASTEXITCODE = 0 }
}

# --- 3. Copiar ~/.claude (configuracion global de Claude Code) si existe ---
$claudeGlobal = Join-Path $env:USERPROFILE ".claude"
if (Test-Path $claudeGlobal) {
    Log "Copiando ~/.claude (config global)"
    $gDst = Join-Path $staging "user_claude"
    New-Item -ItemType Directory -Path $gDst -Force | Out-Null
    # Solo lo esencial: settings, memorias, skills configuradas
    $null = robocopy $claudeGlobal $gDst /E /XJ /R:1 /W:1 /NFL /NDL /NJH /NJS /NC /NS /NP `
        /XD "$claudeGlobal\projects" "$claudeGlobal\sessions" "$claudeGlobal\statsig" `
            "$claudeGlobal\todos" "$claudeGlobal\ide" "$claudeGlobal\cache" "$claudeGlobal\shell-snapshots" `
        /XF "*.log" "*.jsonl"
    if ($LASTEXITCODE -lt 8) { $global:LASTEXITCODE = 0 }
}

# --- 4. Manifest con info del backup ---
$manifest = @{
    timestamp = $ts
    machine = $env:COMPUTERNAME
    user = $env:USERNAME
    project_path = $ProjectDir
    includes_node_modules = [bool]$IncludeNodeModules
    items = @(
        @{ name = "project"; size_mb = [math]::Round(((Get-ChildItem $projDst -Recurse -ErrorAction SilentlyContinue | Measure-Object -Property Length -Sum).Sum / 1MB), 2) }
    )
} | ConvertTo-Json -Depth 4
Set-Content -Path (Join-Path $staging "MANIFEST.json") -Value $manifest -Encoding UTF8

# --- 5. Comprimir ---
Log "Comprimiendo a $zipPath"
Compress-Archive -Path "$staging\*" -DestinationPath $zipPath -CompressionLevel Optimal -Force
Remove-Item -Recurse -Force $staging

$size = (Get-Item $zipPath).Length
$sizeMB = [math]::Round($size / 1MB, 2)
Log "Backup listo: $zipPath ($sizeMB MB)" "Green"

# --- 6. Rotacion: dejar solo $KeepLast backups ---
$backups = Get-ChildItem -Path $OutDir -Filter "claudy-full-*.zip" | Sort-Object LastWriteTime -Descending
if ($backups.Count -gt $KeepLast) {
    $backups | Select-Object -Skip $KeepLast | ForEach-Object {
        Remove-Item $_.FullName -Force
        Log "  Limpiando antiguo: $($_.Name)" "DarkGray"
    }
}

exit 0
