@echo off
setlocal EnableExtensions
cd /d "%~dp0"

if not exist "%~dp0mercadia_bridge_config.bat" (
  echo [ERROR] No existe mercadia_bridge_config.bat.
  echo Ejecuta primero mercadia_bridge_setup.bat.
  exit /b 2
)

call "%~dp0mercadia_bridge_config.bat"

set "PYTHON_EXE="
if exist "%~dp0..\.venv\Scripts\python.exe" set "PYTHON_EXE=%~dp0..\.venv\Scripts\python.exe"
if not defined PYTHON_EXE if exist "%~dp0.venv\Scripts\python.exe" set "PYTHON_EXE=%~dp0.venv\Scripts\python.exe"

if defined PYTHON_EXE (
  echo [%date% %time%] Iniciando Mercadia Bridge...>>"%~dp0mercadia_bridge.log"
  "%PYTHON_EXE%" "%~dp0scripts\mercadia_bridge.py" >>"%~dp0mercadia_bridge.log" 2>&1
  set "EXITCODE=%ERRORLEVEL%"
) else (
  where py >nul 2>&1
  if not errorlevel 1 (
    echo [%date% %time%] Iniciando Mercadia Bridge con py...>>"%~dp0mercadia_bridge.log"
    py -3 "%~dp0scripts\mercadia_bridge.py" >>"%~dp0mercadia_bridge.log" 2>&1
    set "EXITCODE=%ERRORLEVEL%"
  ) else (
    echo [%date% %time%] ERROR: Python no encontrado.>>"%~dp0mercadia_bridge.log"
    exit /b 3
  )
)

exit /b %EXITCODE%
