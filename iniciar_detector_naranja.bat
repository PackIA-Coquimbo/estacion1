@echo off
title PackIACamara - Detector de Naranjas con Auto-Captura
color 0E

echo =====================================================================
echo           PACK IA CAMARA - DETECTOR DE NARANJAS (IA + VISION)
echo =====================================================================
echo.
echo 1. Ajuste automatico de iluminacion activado.
echo 2. Deteccion de naranja activa.
echo 3. Tomara una foto y reproducira un sonido al identificarla.
echo.
echo Guardando fotos en: captures\naranjas\
echo.

cd /d "%~dp0"

if exist ".venv\Scripts\python.exe" (
    set "PYTHON_EXE=.venv\Scripts\python.exe"
) else (
    set "PYTHON_EXE=python"
)

"%PYTHON_EXE%" detect_orange.py

if %ERRORLEVEL% NEQ 0 (
    echo.
    echo [ERROR] Se produjo un inconveniente al ejecutar el detector.
    pause
)
