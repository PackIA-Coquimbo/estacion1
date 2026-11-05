@echo off
title PackIACamara - Inspeccion de Calidad y Ciclo de Vida de Naranjas
color 0E

echo =====================================================================
echo    PACK IA CAMARA - INSPECCION DE CALIDAD DE NARANJAS (IA + VISION)
echo =====================================================================
echo.
echo  1. Iluminacion adaptativa continua en video (30 FPS).
echo  2. Clasificacion de calidad:
echo     - VERDE   : BUEN ESTADO (Optima)
echo     - AMARILLO: DEFECTO LEVE (Golpes / Manchas leves)
echo     - ROJO    : PODRIDA / MAL ESTADO (Moho / Necrosis)
echo.
echo  3. Memoria Inteligente: 1 sola foto por naranja.
echo     (Puedes moverla o rotarla sin que saque fotos repetidas).
echo.
echo  4. Retirala de la camara durante 2 segundos para rearmar.
echo  5. Guarda fotos clasificadas en carpetas y genera reporte CSV.
echo.

cd /d "%~dp0"

if exist ".venv\Scripts\python.exe" (
    set "PYTHON_EXE=.venv\Scripts\python.exe"
) else if exist "..\.venv\Scripts\python.exe" (
    set "PYTHON_EXE=..\.venv\Scripts\python.exe"
) else (
    set "PYTHON_EXE=python"
)

"%PYTHON_EXE%" detect_orange.py

if %ERRORLEVEL% NEQ 0 (
    echo.
    echo [ERROR] Se produjo un inconveniente al ejecutar la inspeccion.
    pause
)
