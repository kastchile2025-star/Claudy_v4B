# Script de instalación para Claudy Web UI (Windows/PowerShell)
# Uso: .\setup.ps1

Write-Host "🚀 Instalando Claudy Web UI..." -ForegroundColor Cyan

# Verificar Node.js
$nodeVersion = node --version 2>$null
if ($LASTEXITCODE -ne 0) {
    Write-Host "❌ Node.js no está instalado" -ForegroundColor Red
    exit 1
}

Write-Host "✓ Node.js $nodeVersion" -ForegroundColor Green

# Instalar dependencias
Write-Host "📦 Instalando dependencias..." -ForegroundColor Yellow
npm install

# Crear .env.local si no existe
if (-not (Test-Path ".env.local")) {
    Write-Host "🔧 Creando .env.local..." -ForegroundColor Yellow
    Copy-Item ".env.example" -Destination ".env.local"
}

Write-Host "✅ Instalación completa!" -ForegroundColor Green
Write-Host ""
Write-Host "Próximos pasos:" -ForegroundColor Cyan
Write-Host "1. npm run dev       - Iniciar servidor desarrollo"
Write-Host "2. npm run build     - Compilar producción"
Write-Host ""
Write-Host "Asegúrate que OpenCode esté corriendo en http://localhost:4096" -ForegroundColor Magenta
