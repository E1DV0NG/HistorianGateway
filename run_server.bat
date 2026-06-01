@echo off
title eHistorian Central Server & UI
cd /d "%~dp0"

echo ==================================================
echo   eHistorian Central Server ^& UI (Control Panel)
echo ==================================================
echo.

:: Check virtual environment
if not exist ".venv\Scripts\activate.bat" (
    echo [CHYBA] Virtualni prostredi nebylo nalezeno. Spustte nejprve eHistorian_START.bat.
    pause
    exit /b 1
)

:: Activate virtual environment
call .venv\Scripts\activate.bat

echo [INFO] Spoustim Flask server na http://localhost:5000
echo.
python server.py

pause