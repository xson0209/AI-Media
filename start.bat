@echo off
setlocal EnableExtensions

title AI Media Project - Start Voicebox

set "ROOT=%~dp0"
if "%ROOT:~-1%"=="\" set "ROOT=%ROOT:~0,-1%"

set "APP_DIR=%ROOT%\voice-app"
set "START_SCRIPT=%APP_DIR%\scripts\start-web-e.ps1"
set "FRONTEND_URL=http://127.0.0.1:4000"
set "BACKEND_DOCS=http://127.0.0.1:17493/docs"

if not exist "%APP_DIR%" (
    echo Khong tim thay thu muc voice-app: "%APP_DIR%"
    pause
    exit /b 1
)

if not exist "%START_SCRIPT%" (
    echo Khong tim thay file start: "%START_SCRIPT%"
    pause
    exit /b 1
)

where powershell.exe >nul 2>nul
if errorlevel 1 (
    echo Khong tim thay powershell.exe tren may nay.
    pause
    exit /b 1
)

echo Dang khoi dong Voicebox...
echo Thu muc du an: "%APP_DIR%"
echo Neu la lan dau chay, backend co the mat 1-3 phut de san sang.
echo.

cd /d "%APP_DIR%"
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%START_SCRIPT%"
set "START_EXIT=%ERRORLEVEL%"

if not "%START_EXIT%"=="0" (
    echo.
    echo Khoi dong that bai. Kiem tra log:
    echo   "%APP_DIR%\.logs\backend.err.log"
    echo   "%APP_DIR%\.logs\backend.out.log"
    echo   "%APP_DIR%\.logs\web.err.log"
    echo   "%APP_DIR%\.logs\web.out.log"
    echo.
    pause
    exit /b %START_EXIT%
)

echo.
echo Da khoi dong xong.
echo Frontend:    %FRONTEND_URL%
echo Backend API: %BACKEND_DOCS%
echo.

start "" "%FRONTEND_URL%"
pause
