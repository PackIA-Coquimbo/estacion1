@echo off
title PackIACamara - Test de Diagnostico
color 0B

echo =====================================================================
echo                 PACK IA CAMARA - TEST DE DIAGNOSTICO
echo =====================================================================
echo.

cd /d "%~dp0"

if exist ".venv\Scripts\python.exe" (
    set "PYTHON_EXE=.venv\Scripts\python.exe"
) else if exist "..\.venv\Scripts\python.exe" (
    set "PYTHON_EXE=..\.venv\Scripts\python.exe"
) else (
    set "PYTHON_EXE=python"
)

"%PYTHON_EXE%" test_camera.py

echo.
echo Presione cualquier tecla para salir...
pause >nul
