@echo off
REM 1_server.bat - Spusti mock API server

title eHistorian Mock Server
cd /d "%~dp0"

echo.
echo ========================================
echo   Mock eHistorian Server (port 5000)
echo ========================================
echo.
if not exist ".venv\Scripts\activate.bat" (
    call setup_env.bat
)
echo Aktivuji venv...
call .venv\Scripts\activate.bat
if errorlevel 1 (
    echo ERROR: Nemuzu aktivovat venv
    pause
    exit /b 1
)

echo Spoustim server...
python server.py
if errorlevel 1 (
    echo ERROR pri spusteni serveru!
    pause
    exit /b 1
)

