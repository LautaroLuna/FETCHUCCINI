@echo off
setlocal EnableExtensions
cd /d "%~dp0"
title Fetchuccini - Mercadia Bridge Manual

cls
echo ===============================================================
echo  FETCHUCCINI - MERCADIA BRIDGE MANUAL
echo ===============================================================
echo.
echo El progreso se mostrara en UNA sola barra en esta ventana.
echo La tarea automatica cada 6 horas sigue usando mercadia_bridge_run.bat.
echo.

if not exist "%~dp0mercadia_bridge_config.bat" (
  echo [ERROR] No existe mercadia_bridge_config.bat.
  echo Ejecuta primero mercadia_bridge_setup.bat.
  echo.
  pause
  exit /b 2
)

call "%~dp0mercadia_bridge_config.bat"
set "MERCADIA_BRIDGE_INTERACTIVE=1"

set "PYTHON_EXE="
if exist "%~dp0..\.venv\Scripts\python.exe" set "PYTHON_EXE=%~dp0..\.venv\Scripts\python.exe"
if not defined PYTHON_EXE if exist "%~dp0.venv\Scripts\python.exe" set "PYTHON_EXE=%~dp0.venv\Scripts\python.exe"

if defined PYTHON_EXE (
  "%PYTHON_EXE%" -u "%~dp0scripts\mercadia_catalog_sync.py"
  set "EXITCODE=%ERRORLEVEL%"
) else (
  where py >nul 2>&1
  if not errorlevel 1 (
    py -3 -u "%~dp0scripts\mercadia_catalog_sync.py"
    set "EXITCODE=%ERRORLEVEL%"
  ) else (
    echo [ERROR] Python no encontrado.
    echo.
    pause
    exit /b 3
  )
)

echo.
if "%EXITCODE%"=="0" (
  echo [OK] Bridge finalizado correctamente.
) else (
  echo [ERROR] El bridge termino con codigo %EXITCODE%.
)
echo.
pause
exit /b %EXITCODE%
