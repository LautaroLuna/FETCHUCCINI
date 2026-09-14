@echo off
chcp 65001 >nul
setlocal EnableExtensions
cd /d "%~dp0"
title Fetchuccini - Mercadia Bridge
cls

echo ===============================================================
echo   FETCHUCCINI - MERCADIA BRIDGE MANUAL
echo ===============================================================
echo.
echo Esta ventana mostrara el progreso en vivo y NO se cerrara sola.
echo El proceso puede tardar bastante dependiendo de Mercadia.
echo.

call "%~dp0mercadia_bridge_run.bat" --interactive
set "EXITCODE=%ERRORLEVEL%"

echo.
echo ===============================================================
if "%EXITCODE%"=="0" (
  echo   [OK] El bridge termino correctamente.
) else (
  echo   [ERROR] El bridge termino con codigo %EXITCODE%.
  echo   Revisa el mensaje de arriba antes de cerrar esta ventana.
)
echo ===============================================================
echo.
pause
exit /b %EXITCODE%
