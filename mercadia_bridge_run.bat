@echo off
setlocal EnableExtensions
cd /d "%~dp0"
chcp 65001 >nul
set "PYTHONUTF8=1"

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
 echo  FETCHUCCINI - SINCRONIZACION MERCADIA
 echo ===============================================================
 echo.
 echo El progreso se muestra en pantalla y tambien se guarda en:
 echo %LOG_FILE%
 echo.
 echo No cierres esta ventana mientras la sincronizacion esta activa.
 echo.
 echo [%date% %time%] Iniciando sincronizacion completa de Mercadia...>>"%LOG_FILE%"

if defined PYTHON_EXE (
  set "FETCHUCCINI_PY=%PYTHON_EXE%"
  set "FETCHUCCINI_SCRIPT=%SYNC_SCRIPT%"
  set "FETCHUCCINI_LOG=%LOG_FILE%"
  powershell -NoProfile -ExecutionPolicy Bypass -Command "& $env:FETCHUCCINI_PY $env:FETCHUCCINI_SCRIPT 2^>^&1 | Tee-Object -FilePath $env:FETCHUCCINI_LOG -Append; exit $LASTEXITCODE"
  set "EXITCODE=%ERRORLEVEL%"
) else (
  where py >nul 2>&1
  if not errorlevel 1 (
    set "FETCHUCCINI_SCRIPT=%SYNC_SCRIPT%"
    set "FETCHUCCINI_LOG=%LOG_FILE%"
    powershell -NoProfile -ExecutionPolicy Bypass -Command "& py -3 $env:FETCHUCCINI_SCRIPT 2^>^&1 | Tee-Object -FilePath $env:FETCHUCCINI_LOG -Append; exit $LASTEXITCODE"
    set "EXITCODE=%ERRORLEVEL%"
  ) else (
    echo [%date% %time%] ERROR: Python no encontrado.>>"%LOG_FILE%"
    echo [ERROR] Python no encontrado.
    exit /b 3
  )
)

 echo.
if "%EXITCODE%"=="0" (
  echo [OK] Sincronizacion terminada correctamente.
) else (
  echo [ERROR] La sincronizacion termino con codigo %EXITCODE%.
  echo Revisa %LOG_FILE% para mas detalles.
)
 echo.
exit /b %EXITCODE%
