#!/bin/bash

# Script de instalación rápida para Claudy Web UI
# Uso: bash setup.sh

set -e  # Salir en caso de error

echo "🚀 Instalando Claudy Web UI..."

# Verificar Node.js
if ! command -v node &> /dev/null; then
    echo "❌ Node.js no está instalado"
    exit 1
fi

echo "✓ Node.js $(node --version)"

# Instalar dependencias
echo "📦 Instalando dependencias..."
npm install

# Crear .env si no existe
if [ ! -f .env.local ]; then
    echo "🔧 Creando .env.local..."
    cp .env.example .env.local
fi

echo "✅ Instalación completa!"
echo ""
echo "Próximos pasos:"
echo "1. npm run dev       - Iniciar servidor desarrollo"
echo "2. npm run build     - Compilar producción"
echo ""
echo "Asegúrate que OpenCode esté corriendo en http://localhost:4096"
