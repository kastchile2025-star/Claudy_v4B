@echo off
title Iniciando Claudy v4...
color 0b
echo ==================================================
echo   Iniciando Claudy v4 - Asistente IA Personal
echo ==================================================
echo.

:: Obtener la ruta del directorio del script
cd /d "%~dp0"

:: 1. Intentar iniciar OpenCode en segundo plano
echo [*] Iniciando servidor OpenCode en el puerto 4096...
start /min "OpenCode Server" cmd /c "opencode serve --port 4096 --hostname 127.0.0.1"

:: Esperar un par de segundos
timeout /t 2 /nobreak >nul

:: 2. Iniciar Desktop Pet (Mascota)
echo [*] Lanzando Claudy Desktop Pet (con tus nuevas animaciones)...
start "Claudy Pet" cmd /k "python src/desktop/pet.py"

echo.
echo ==================================================
echo   ¡Claudy ha sido iniciado!
echo   Ya deberias ver a tu mascota en el escritorio.
echo   Esta ventana se cerrara en 4 segundos...
echo ==================================================
timeout /t 4 >nul
exit
