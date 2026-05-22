@echo off
title Subiendo Claudy V4 a GitHub (Modo Seguro)...
echo ==========================================
echo SUBIENDO PROYECTO CLAUDY V4 A GITHUB (MODO SEGURO)
echo ==========================================
echo.

cd /d "%~dp0"

echo 1. Creando archivo .gitignore para proteger archivos temporales...
(
echo __pycache__/
echo *.pyc
echo config_backup_safe.json
echo .claudy/
echo *.log
echo subir_a_github.bat
) > .gitignore
echo ✓ Archivo .gitignore configurado.

echo.
echo 2. Preparando repositorio y removiendo credenciales privadas temporalmente...
python push_handler.py prepare

echo.
echo 3. Inicializando git...
git init

echo.
echo 4. Configurando repositorio remoto...
git remote remove origin 2>nul
git remote add origin https://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@github.com/kastchile2025-star/Claudy_v4.git

echo.
echo 5. Agregando archivos al repositorio...
git add .

echo.
echo 6. Creando commit de las mejoras...
git commit -m "Upload Claudy V4 desktop pet improvements (Safe Push without keys)"

echo.
echo 7. Subiendo cambios a la rama 'claudy-v4' (evita restricciones de la rama principal protegida)...
git branch -M claudy-v4
git push -u origin claudy-v4 --force

echo.
echo 8. Restaurando tus credenciales y llaves locales originales...
python push_handler.py restore

echo.
echo ==========================================
echo ¡PROCESO DE SUBIDA COMPLETADO CON EXITO!
echo ==========================================
pause
