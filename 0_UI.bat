@echo off
title eHistorian Control Panel
cd /d "%~dp0"

echo.
echo ========================================
echo   eHistorian Gateway Control Panel
echo ========================================
echo.

:: Zkontroluj jestli existuje venv
if not exist ".venv\Scripts\activate.bat" (
    echo [ERROR] Venv nenalezen. Vytvarim...
    python -m venv .venv
    if errorlevel 1 (
        echo [ERROR] Python nenalezen nebo selhal. Zkontroluj instalaci.
        pause
        exit /b 1
    )
    echo [OK] Venv vytvoren.
)

echo Aktivuji venv...
call .venv\Scripts\activate.bat

echo Instaluji potrebne balicky...
pip install flask flask-cors requests -q

:: Zkontroluj jestli existuje slozka ui/
if not exist "ui\index.html" (
    echo.
    echo [ERROR] Slozka ui\ nebo ui\index.html nenalezena.
    echo         Ujisti se ze struktura vypada takto:
    echo.
    echo         projekt\
    echo           ui_server.py
    echo           start.bat
    echo           ui\
    echo             index.html
    echo             styles.css
    echo             app.js
    echo.
    pause
    exit /b 1
)

echo.
echo Spoustim UI server...
echo.
echo   Otevri: http://localhost:5001
echo.
echo   Zavreni: Ctrl+C nebo zavri toto okno
echo.

python ui_server.py

pause