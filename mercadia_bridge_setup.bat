@echo off
setlocal EnableExtensions EnableDelayedExpansion
cd /d "%~dp0"

set "CONFIG=%~dp0mercadia_bridge_config.bat"
set "TASK_NAME=Fetchuccini Mercadia Sync"
set "RUNNER=%~dp0mercadia_bridge_run.bat"

if not exist "%CONFIG%" (
  echo Generando una clave privada para Mercadia Bridge...
  set "BRIDGE_KEY="
  for /f "usebackq delims=" %%K in (`powershell -NoProfile -Command "$b=New-Object byte[] 32; [Security.Cryptography.RandomNumberGenerator]::Create().GetBytes($b); (($b | ForEach-Object { $_.ToString('x2') }) -join '')"`) do set "BRIDGE_KEY=%%K"
  if not defined BRIDGE_KEY (
    echo [ERROR] No se pudo generar la clave.
    pause
    exit /b 2
  )
  >"%CONFIG%" echo @echo off
  >>"%CONFIG%" echo set "FETCHUCCINI_URL=https://fetchuccini-production.up.railway.app"
  >>"%CONFIG%" echo set "MERCADIA_BRIDGE_KEY=!BRIDGE_KEY!"
)

call "%CONFIG%"

echo.
echo ===============================================================
echo  FETCHUCCINI - MERCADIA BRIDGE
echo ===============================================================
echo.
echo URL: %FETCHUCCINI_URL%
echo.
echo IMPORTANTE: agrega en Railway una variable llamada:
echo.
echo     MERCADIA_BRIDGE_KEY
echo.
echo con ESTE valor exacto:
echo.
echo     %MERCADIA_BRIDGE_KEY%
echo.
echo No compartas esta clave ni subas mercadia_bridge_config.bat a GitHub.
echo El archivo ya esta incluido en .gitignore.
echo.

echo Creando tarea de Windows para ejecutarse cada 1 hora...
schtasks /Create /F /SC HOURLY /MO 1 /TN "%TASK_NAME%" /TR "\"%RUNNER%\"" >nul
if errorlevel 1 (
  echo [ERROR] Windows no pudo crear la tarea automaticamente.
  echo Proba ejecutar este archivo como administrador.
  pause
  exit /b 3
)

echo [OK] Tarea creada: %TASK_NAME%
echo [OK] Se ejecutara cada 1 hora.
echo.
echo Despues de agregar la variable en Railway y esperar el redeploy,
echo podes hacer doble click en mercadia_bridge_run.bat para crear/subir el catalogo ya.
echo El historial queda en mercadia_bridge.log.
echo.
pause
