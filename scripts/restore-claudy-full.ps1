# Claudy FULL restore script
# Restaura un backup completo (proyecto + ~/.claudy + ~/.claude opcional).
# Uso:
#   .\restore-claudy-full.ps1                              # restaura el mas reciente desde G:
#   .\restore-claudy-full.ps1 -ZipPath "ruta\al.zip"
#   .\restore-claudy-full.ps1 -ProjectDest "C:\NuevoClaudy"
#   .\restore-claudy-full.ps1 -SkipProject                # solo restaura datos personales
#   .\restore-claudy-full.ps1 -SkipUserData               # solo restaura el proyecto

param(
    [string]$ZipPath = "",
    [string]$BackupDir = "G:\Mi unidad\Claudy-Backups",
    [string]$ProjectDest = "",
    [switch]$SkipProject,
    [switch]$SkipUserData,
    [switch]$SkipClaudeGlobal
)

$ErrorActionPreference = "Stop"

function Log($msg, $color = "Cyan") { Write-Host $msg -ForegroundColor $color }

if (-not $ZipPath) {
    if (-not (Test-Path $BackupDir)) {
        Log "No existe $BackupDir" "Red"; exit 1
    }
    $latest = Get-ChildItem -Path $BackupDir -Filter "claudy-full-*.zip" -ErrorAction SilentlyContinue |
              Sort-Object LastWriteTime -Descending | Select-Object -First 1
    if (-not $latest) {
        Log "No hay backups en $BackupDir" "Red"; exit 1
    }
    $ZipPath = $latest.FullName
}
if (-not (Test-Path $ZipPath)) { Log "No existe el zip: $ZipPath" "Red"; exit 1 }

$ts = Get-Date -Format "yyyyMMdd-HHmmss"
$staging = Join-Path $env:TEMP "claudy-restore-$ts"
New-Item -ItemType Directory -Path $staging -Force | Out-Null

Log "Extrayendo $ZipPath..."
Expand-Archive -Path $ZipPath -DestinationPath $staging -Force

$manifestPath = Join-Path $staging "MANIFEST.json"
if (Test-Path $manifestPath) {
    $manifest = Get-Content $manifestPath -Raw | ConvertFrom-Json
    Log "Backup info:" "DarkCyan"
    Log "  Timestamp: $($manifest.timestamp)"
    Log "  Maquina origen: $($manifest.machine) ($($manifest.user))"
    Log "  Ruta original: $($manifest.project_path)"
    if (-not $ProjectDest) { $ProjectDest = $manifest.project_path }
}
if (-not $ProjectDest) {
    $ProjectDest = "$env:USERPROFILE\Claudy"
}

# --- 1. Proyecto ---
$projSrc = Join-Path $staging "project"
if ((-not $SkipProject) -and (Test-Path $projSrc)) {
    if (Test-Path $ProjectDest) {
        $old = "$ProjectDest.old.$ts"
        Log "Renombrando proyecto existente a $old" "Yellow"
        Rename-Item -Path $ProjectDest -NewName (Split-Path -Leaf $old)
    }
    New-Item -ItemType Directory -Path $ProjectDest -Force | Out-Null
    Log "Restaurando proyecto a $ProjectDest"
    $null = robocopy $projSrc $ProjectDest /MIR /XJ /R:1 /W:1 /NFL /NDL /NJH /NJS /NC /NS /NP
    if ($LASTEXITCODE -lt 8) { $global:LASTEXITCODE = 0 }
}

# --- 2. ~/.claudy ---
$homeSrc = Join-Path $staging "user_claudy"
if ((-not $SkipUserData) -and (Test-Path $homeSrc)) {
    $homeDst = Join-Path $env:USERPROFILE ".claudy"
    if (Test-Path $homeDst) {
        Rename-Item -Path $homeDst -NewName ".claudy.old.$ts"
        Log "Renombrado .claudy existente a .claudy.old.$ts" "Yellow"
    }
    New-Item -ItemType Directory -Path $homeDst -Force | Out-Null
    Log "Restaurando ~/.claudy"
    $null = robocopy $homeSrc $homeDst /MIR /XJ /R:1 /W:1 /NFL /NDL /NJH /NJS /NC /NS /NP
    if ($LASTEXITCODE -lt 8) { $global:LASTEXITCODE = 0 }
}

# --- 3. ~/.claude ---
$claudeSrc = Join-Path $staging "user_claude"
if ((-not $SkipClaudeGlobal) -and (Test-Path $claudeSrc)) {
    $claudeDst = Join-Path $env:USERPROFILE ".claude"
    if (Test-Path $claudeDst) {
        Log "Mergeando en ~/.claude existente (no sobrescribe destructivamente)" "Yellow"
        $null = robocopy $claudeSrc $claudeDst /E /XJ /R:1 /W:1 /NFL /NDL /NJH /NJS /NC /NS /NP
    } else {
        New-Item -ItemType Directory -Path $claudeDst -Force | Out-Null
        $null = robocopy $claudeSrc $claudeDst /E /XJ /R:1 /W:1 /NFL /NDL /NJH /NJS /NC /NS /NP
    }
    if ($LASTEXITCODE -lt 8) { $global:LASTEXITCODE = 0 }
}

Remove-Item -Recurse -Force $staging

Log "" "Cyan"
Log "Restauracion completa." "Green"
Log "  Proyecto: $ProjectDest"
Log ""
Log "Siguientes pasos:" "Cyan"
Log "  1. cd `"$ProjectDest`""
Log "  2. npm install   (reinstala node_modules)"
Log "  3. pip install -r requirements.txt"
Log "  4. .\iniciar_claudy.bat"
