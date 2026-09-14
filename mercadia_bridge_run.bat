@echo off
setlocal EnableExtensions
cd /d "%~dp0"
title Fetchuccini - Mercadia Bridge

if not exist "%~dp0mercadia_bridge_config.bat" (
  echo [ERROR] No existe mercadia_bridge_config.bat.
  echo Ejecuta primero mercadia_bridge_setup.bat.
  exit /b 2
)

call "%~dp0mercadia_bridge_config.bat"

set "PYTHON_EXE="
if exist "%~dp0..\.venv\Scripts\python.exe" set "PYTHON_EXE=%~dp0..\.venv\Scripts\python.exe"
if not defined PYTHON_EXE if exist "%~dp0.venv\Scripts\python.exe" set "PYTHON_EXE=%~dp0.venv\Scripts\python.exe"

set "SYNC_SCRIPT=%~dp0scripts\mercadia_catalog_sync.py"
set "LOG_FILE=%~dp0mercadia_bridge.log"

echo.
echo ===============================================================
echo  FETCHUCCINI - MERCADIA BRIDGE
 echo ===============================================================
echo  Progreso en vivo + registro: mercadia_bridge.log
echo ===============================================================
echo.
echo [%date% %time%] Iniciando sincronizacion completa de Mercadia...>>"%LOG_FILE%"

if defined PYTHON_EXE (
  powershell -NoProfile -ExecutionPolicy Bypass -Command "& '%PYTHON_EXE%' -u '%SYNC_SCRIPT%' 2^>^&1 ^| Tee-Object -FilePath '%LOG_FILE%' -Append; exit $LASTEXITCODE"
  set "EXITCODE=%ERRORLEVEL%"
) else (
  where py >nul 2>&1
  if not errorlevel 1 (
    powershell -NoProfile -ExecutionPolicy Bypass -Command "& py -3 -u '%SYNC_SCRIPT%' 2^>^&1 ^| Tee-Object -FilePath '%LOG_FILE%' -Append; exit $LASTEXITCODE"
    set "EXITCODE=%ERRORLEVEL%"
  ) else (
    echo [ERROR] Python no encontrado.
    echo [%date% %time%] ERROR: Python no encontrado.>>"%LOG_FILE%"
    exit /b 3
  )
)

echo.
if "%EXITCODE%"=="0" (
  echo [OK] Bridge finalizado correctamente.
) else (
  echo [ERROR] Bridge termino con codigo %EXITCODE%.
)
echo.
exit /b %EXITCODE%
