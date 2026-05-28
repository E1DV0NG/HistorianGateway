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

:: Get active config profile
set PROFILE=default.json
if exist "active_profile.txt" (
    set /p PROFILE=<active_profile.txt
)
set EHG_BOOTSTRAP_CONFIG=%~dp0configs\%PROFILE%

echo [INFO] Vybrany profil: %PROFILE%
echo [INFO] Bootstrap konfigurace: %EHG_BOOTSTRAP_CONFIG%
echo.

:: Run gateway from its folder
cd eHistorian.Gateway
python -m ehistorian_gateway.main

pause
