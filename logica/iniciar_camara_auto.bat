@echo off
title PackIACamara - Modo Automatico de Iluminacion
color 0A

echo =====================================================================
echo                 PACK IA CAMARA - MODO AUTOMATICO
echo =====================================================================
echo.
echo Ajustando brillo y contraste dinamicamente segun el entorno...
echo.

cd /d "%~dp0"

if exist ".venv\Scripts\python.exe" (
    set "PYTHON_EXE=.venv\Scripts\python.exe"
) else if exist "..\.venv\Scripts\python.exe" (
    set "PYTHON_EXE=..\.venv\Scripts\python.exe"
) else (
    set "PYTHON_EXE=python"
)

"%PYTHON_EXE%" auto_camera.py

if %ERRORLEVEL% NEQ 0 (
    echo.
    echo [ERROR] Se produjo un inconveniente al ejecutar la camara.
    pause
)
