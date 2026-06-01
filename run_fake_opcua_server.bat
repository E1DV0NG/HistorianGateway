@echo off
title eHistorian Fake OPC UA Server (Simulator)
cd /d "%~dp0"

echo ==================================================
echo   eHistorian Fake OPC UA Server (Simulator)
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

python simulator\fake_opcua_server.py

if not defined EHG_NO_PAUSE pause
