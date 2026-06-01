@echo off
chcp 65001 > nul
title OPC UA Simulator Runner
cd /d "%~dp0"

echo ===================================================
echo   Kontrola prostředí a spouštění OPC UA simulátoru  
echo ===================================================
echo.

:: 1. Kontrola virtuálního prostředí
if not exist ".venv\Scripts\activate.bat" (
    echo [CHYBA] Virtuální prostředí nebylo nalezeno!
    echo Spusť nejprve hlavní soubor eHistorian_START.bat, který prostředí vytvoří.
    echo.
    pause
    exit /b 1
)

:: 2. Aktivace virtuálního prostředí
call .venv\Scripts\activate.bat

:: 3. Kontrola, zda existuje složka a skript
if not exist "simulator\opc_mock_server.py" (
    echo [CHYBA] Soubor simulator\opc_mock_server.py nebyl nalezen!
    echo Ujisti se, že tento .bat spouštíš z rootu a složka 'simulator' obsahuje 'opc_mock_server.py'.
    echo.
    pause
    exit /b 1
)

echo.
echo ---------------------------------------------------
echo Spouštím simulator\opc_mock_server.py (venv Python 3.13)...
echo Pro ukončení simulátoru stiskni Ctrl+C nebo zavři toto okno.
echo ---------------------------------------------------
echo.

:: 4. Spuštění skriptu uvnitř aktivovaného venv
python simulator\opc_mock_server.py

pause