#!/bin/bash
set -e

echo "========================================="
echo "  Instalando dependencias de Claudy..."
echo "========================================="

echo "[1/3] FFmpeg..."
if ! command -v ffmpeg >/dev/null 2>&1; then
  sudo apt-get update
  sudo apt-get install -y ffmpeg
fi

# Instalar dependencias del backend
echo "[2/3] Backend..."
cd backend
bun install
cd ..

# Instalar dependencias del frontend
echo "[3/3] Frontend..."
cd frontend
bun install
cd ..

echo ""
echo "Dependencias instaladas correctamente!"
echo ""
