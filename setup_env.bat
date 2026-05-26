@echo off
echo ========================================
echo   Instalace a priprava prostredi
echo ========================================

if not exist ".venv\Scripts\activate.bat" (
    echo Vytvarim virtualni prostredi - venv...
    python -m venv .venv
)

echo Aktivuji venv...
call .venv\Scripts\activate.bat

echo Instaluji balicky pro Server Flask atd...
pip install flask flask-cors requests -q

if exist "eHistorian.Gateway\requirements.txt" (
    echo Instaluji balicky pro Gateway...
    pip install -r eHistorian.Gateway\requirements.txt -q
)

echo.
echo HOTOVO - prostredi je pripraveno.
echo.
pause
