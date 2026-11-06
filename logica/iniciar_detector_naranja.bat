@echo off
title PackIACamara - Estacion 1 Captura
color 0E

echo =====================================================================
echo    PACK IA CAMARA - ESTACION 1: CAPTURA DE NARANJAS
echo =====================================================================
echo.
echo  Guarda una foto nitida por naranja, sin clasificarla.
echo  Las fotos quedan pendientes para Estacion 2 hasta definir su receptor.
echo.

cd /d "%~dp0.."

if exist ".venv\Scripts\python.exe" (
    set "PYTHON_EXE=.venv\Scripts\python.exe"
) else (
    set "PYTHON_EXE=python"
)

"%PYTHON_EXE%" -m src.main

if %ERRORLEVEL% NEQ 0 (
    echo.
    echo [ERROR] Se produjo un inconveniente al ejecutar la inspeccion.
    pause
)
