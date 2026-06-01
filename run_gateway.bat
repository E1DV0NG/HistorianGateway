@echo off
title eHistorian Gateway (Edge Client)
cd /d "%~dp0"

echo ==================================================
echo   eHistorian Gateway (Edge Client)
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

:: Get config
set EHG_BOOTSTRAP_CONFIG=%~dp0configs\default.json

echo [INFO] Bootstrap konfigurace: %EHG_BOOTSTRAP_CONFIG%
echo.

:: Run gateway from its folder
cd eHistorian.Gateway
python -m ehistorian_gateway.main

if not defined EHG_NO_PAUSE pause