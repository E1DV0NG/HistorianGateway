@echo off
title eHistorian Fake Data Generator (Simulator)
cd /d "%~dp0"

echo ==================================================
echo   eHistorian Fake Data Generator (Simulator)
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

set FAKEGEN_CONFIG=%~dp0simulator\fakegen_config.json

echo [INFO] Pouzivam konfiguraci: %FAKEGEN_CONFIG%
echo.

python simulator\fake_data_generator.py

if not defined EHG_NO_PAUSE pause