@echo off
setlocal EnableExtensions
cd /d "%~dp0"

set "INTERACTIVE=0"
if /I "%~1"=="--interactive" set "INTERACTIVE=1"

if not exist "%~dp0mercadia_bridge_config.bat" (
  echo [ERROR] No existe mercadia_bridge_config.bat.
  echo Ejecuta primero mercadia_bridge_setup.bat.
  exit /b 2
)

call "%~dp0mercadia_bridge_config.bat"

set "PYTHON_EXE="
if exist "%~dp0..\.venv\Scripts\python.exe" set "PYTHON_EXE=%~dp0..\.venv\Scripts\python.exe"
if not defined PYTHON_EXE if exist "%~dp0.venv\Scripts\python.exe" set "PYTHON_EXE=%~dp0.venv\Scripts\python.exe"

set "PYTHONUNBUFFERED=1"

if defined PYTHON_EXE (
  echo [%date% %time%] Iniciando sincronizacion completa de Mercadia...>>"%~dp0mercadia_bridge.log"
  if "%INTERACTIVE%"=="1" (
    "%PYTHON_EXE%" "%~dp0scripts\mercadia_catalog_sync.py"
  ) else (
    "%PYTHON_EXE%" "%~dp0scripts\mercadia_catalog_sync.py" >>"%~dp0mercadia_bridge.log" 2>&1
  )
  set "EXITCODE=%ERRORLEVEL%"
) else (
  where py >nul 2>&1
  if not errorlevel 1 (
    echo [%date% %time%] Iniciando sincronizacion completa de Mercadia con py...>>"%~dp0mercadia_bridge.log"
    if "%INTERACTIVE%"=="1" (
      py -3 "%~dp0scripts\mercadia_catalog_sync.py"
    ) else (
      py -3 "%~dp0scripts\mercadia_catalog_sync.py" >>"%~dp0mercadia_bridge.log" 2>&1
    )
    set "EXITCODE=%ERRORLEVEL%"
  ) else (
    echo [%date% %time%] ERROR: Python no encontrado.>>"%~dp0mercadia_bridge.log"
    echo [ERROR] Python no encontrado.
    exit /b 3
  )
)

echo [%date% %time%] Sincronizacion finalizada con codigo %EXITCODE%.>>"%~dp0mercadia_bridge.log"
exit /b %EXITCODE%
