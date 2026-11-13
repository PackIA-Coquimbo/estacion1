@echo off
setlocal
cd /d "%~dp0"
set /p "LOTE=ID del lote (ej. Prueba_001): "
if "%LOTE%"=="" set "LOTE=Prueba_001"
set /p "CAMARA1=Indice primera camara (Enter para 0): "
if "%CAMARA1%"=="" set "CAMARA1=0"
set /p "CAMARA2=Indice segunda camara (Enter para 1): "
if "%CAMARA2%"=="" set "CAMARA2=1"
set /p "MODOAUTO=Captura automatica al pasar la fruta? (S/N): "
if exist ".venv\Scripts\python.exe" (
  set "PYTHON_EXE=.venv\Scripts\python.exe"
) else (
  set "PYTHON_EXE=python"
)
if /I "%MODOAUTO%"=="S" (
  "%PYTHON_EXE%" -m src.paired_capture --lot "%LOTE%" --camera "%CAMARA1%" --camera-2 "%CAMARA2%" --auto
) else (
  "%PYTHON_EXE%" -m src.paired_capture --lot "%LOTE%" --camera "%CAMARA1%" --camera-2 "%CAMARA2%"
)
if errorlevel 1 pause
endlocal
