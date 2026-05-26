@echo off
REM create_venv.bat - vytvoři Python venv pro example/ slozku

cd /d "%~dp0"

if exist ".venv\Scripts\python.exe" (
    echo .venv jiz existuje.
    pause
    exit /b 0
)

echo Vytvarim .venv...
python -m venv .venv

if errorlevel 1 (
    echo ERROR: Nepodarilo se vytvorit .venv
    pause
    exit /b 1
)

echo.
echo HOTOVO - .venv je pripraveno.
echo Spustit: call .venv\Scripts\activate.bat
pause
