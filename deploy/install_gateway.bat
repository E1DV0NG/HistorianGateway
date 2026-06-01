@echo off
echo ========================================
echo   eHistorian Gateway - Setup
echo ========================================
echo.
echo [1/2] Vytvarim virtualni prostredi (.venv)...
python -m venv .venv
call .venv\Scripts\activate.bat

echo [2/2] Instaluji zavislosti...
python -m pip install --upgrade pip -q
pip install --only-binary :all: pyodbc -q
if exist "eHistorian.Gateway\requirements.txt" (
    pip install -r eHistorian.Gateway\requirements.txt -q
)

echo.
echo ========================================
echo Hotovo! Nyni muzete spustit run_gateway.bat
echo ========================================
pause
