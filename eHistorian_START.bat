@echo off
title eHistorian Server
cd /d "%~dp0"

echo ========================================
echo   eHistorian - Setup ^& Start (Python 3.13)
echo ========================================
echo.

:: 1. Zkontrolovat a vytvorit virtualni prostredi pomoci nucene verze 3.13
if not exist ".venv\Scripts\activate.bat" (
    echo [1/3] Vytvarim virtualni prostredi ^(.venv^) pomoci Python 3.13...
    py -3.13 -m venv .venv
    if errorlevel 1 (
        echo [CHYBA] Python 3.13 neni nainstalovan nebo neni v PATH.
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
pip install flask flask-cors requests pandas openpyxl psutil asyncua cryptography -q

:: Instalace pyodbc pro SQL polling
echo [INFO] Instaluji SQL ovladace (pyodbc)...
pip install pyodbc --only-binary :all: -q
if errorlevel 1 (
    echo [WARNING] Standardni pyodbc selhalo, zkousim precompiled-pyodbc...
    pip install precompiled-pyodbc -q
)

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