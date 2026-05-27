@echo off
title eHistorian Server
cd /d "%~dp0"

echo ========================================
echo   eHistorian - Setup ^& Start
echo ========================================
echo.

:: 1. Zkontrolovat a vytvorit virtualni prostredi
if not exist ".venv\Scripts\activate.bat" (
    echo [1/3] Vytvarim virtualni prostredi ^(.venv^)...
    python -m venv .venv
    if errorlevel 1 (
        echo [CHYBA] Python neni nainstalovan nebo neni v PATH.
        pause
        exit /b 1
    )
) else (
    echo [1/3] Virtualni prostredi jiz existuje.
)

:: 2. Aktivovat prostredi
call .venv\Scripts\activate.bat
if errorlevel 1 (
    echo [CHYBA] Nepodarilo se aktivovat virtualni prostredi.
    pause
    exit /b 1
)

:: 3. Nainstalovat vsechny balicky (pip)
echo [2/3] Instaluji a aktualizuji balicky...
python -m pip install --upgrade pip -q
pip install flask flask-cors requests pandas openpyxl -q
pip install --only-binary :all: pyodbc -q

if exist "eHistorian.Gateway\requirements.txt" (
    pip install -r eHistorian.Gateway\requirements.txt -q
)

echo.
echo [3/3] Startuji Server a UI...
echo ========================================
echo.
echo   Otevri prohlizec a prejdi na:
echo   http://localhost:5000
echo.
echo   Z teto stranky muzes zapnout Gateway a spravovat konfiguraci.
echo.
echo [Pro vypnuti serveru stiskni CTRL+C nebo zavri toto okno]
echo.
python server.py

pause
