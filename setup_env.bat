@echo off
echo ========================================
echo   Instalace a priprava prostredi
echo ========================================

REM Zajisti, ze se skript spousti z adresare, kde sam lezi
cd /d "%~dp0"

if not exist ".venv\Scripts\activate.bat" (
    echo Vytvarim virtualni prostredi - venv...
    python -m venv .venv
    if errorlevel 1 (
        echo [ERROR] Nepodarilo se vytvorit .venv. Ujisti se, ze mas nainstalovany Python.
        pause
        exit /b 1
    )
)

echo Aktivuji venv...
call .venv\Scripts\activate.bat

echo Aktualizuji pip na nejnovejsi verzi...
python -m pip install --upgrade pip -q

echo Instaluji balicky pro Server Flask atd...
pip install flask flask-cors requests -q

echo Instaluji pyodbc (predkompilovany balicek pro jistotu)...
pip install --only-binary :all: pyodbc -q

if exist "eHistorian.Gateway\requirements.txt" (
    echo Instaluji balicky pro Gateway ze souboru requirements.txt...
    pip install -r eHistorian.Gateway\requirements.txt -q
)

echo.
echo HOTOVO - prostredi je pripraveno.
echo.
pause