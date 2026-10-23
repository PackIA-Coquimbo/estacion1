@echo off
title PackIACamara - Detector Inteligente de Naranjas (1 Foto por Objeto)
color 0E

echo =====================================================================
echo    PACK IA CAMARA - DETECTOR INTELIGENTE POR CICLO DE VIDA
echo =====================================================================
echo.
echo  1. Ajuste automatico de iluminacion activado.
echo  2. Coloca una naranja  -^> Toma 1 sola foto y la bloquea.
echo  3. Mientras este ahi   -^> NO saca mas fotos.
echo  4. Retirala            -^> Detecta la salida y se rearma.
echo  5. Coloca otra naranja -^> Detecta la nueva y le saca foto.
echo.
echo Guardando fotos en: captures\ (y captures\naranjas\)
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
