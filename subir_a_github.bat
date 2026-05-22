@echo off
title Subiendo Claudy V4 a GitHub...
echo ==========================================
echo SUBIENDO PROYECTO CLAUDY V4 A GITHUB
echo ==========================================
echo.

cd /d "%~dp0"

echo 1. Inicializando repositorio git...
git init

echo.
echo 2. Agregando archivos al repositorio...
git add .

echo.
echo 3. Creando commit inicial...
git commit -m "Upload Claudy V4 desktop pet improvements"

echo.
echo 4. Configurando repositorio remoto...
git remote remove origin 2>nul
git remote add origin https://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@github.com/kastchile2025-star/Claudy_v4.git

echo.
echo 5. Cambiando a rama principal (main)...
git branch -M main

echo.
echo 6. Subiendo cambios a GitHub...
git push -u origin main --force

echo.
echo ==========================================
echo ¡PROCESO DE SUBIDA COMPLETADO CON EXITO!
echo ==========================================
pause
