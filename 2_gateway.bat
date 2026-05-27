@echo off
REM 2_gateway.bat - Spusti eHistorian Gateway

title eHistorian Gateway
cd /d "%~dp0"

echo.
echo ========================================
echo   eHistorian Gateway
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

echo Nastavuji config...
set EHG_BOOTSTRAP_CONFIG=%cd%\test.config.json

echo Prejdu do eHistorian.Gateway...
cd eHistorian.Gateway

echo Spoustim gateway...
python -m ehistorian_gateway.main
if errorlevel 1 (
    echo ERROR pri spusteni gateway!
    pause
    exit /b 1
)

