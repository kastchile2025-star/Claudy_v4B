@echo off
title Backup Claudy a Google Drive
color 0a
echo ==================================================
echo   Respaldando Claudy a G:\Mi unidad\Claudy-Backups
echo ==================================================
echo.

cd /d "%~dp0"

powershell -NoProfile -ExecutionPolicy Bypass -File "scripts\backup-claudy-full.ps1"

if %ERRORLEVEL% NEQ 0 (
    color 0c
    echo.
    echo ==================================================
    echo   ERROR: el backup fallo. Revisa el mensaje arriba.
    echo ==================================================
    pause
    exit /b %ERRORLEVEL%
)

echo.
echo ==================================================
echo   Backup completado. Esta ventana se cerrara en 5s.
echo ==================================================
timeout /t 5 >nul
exit
