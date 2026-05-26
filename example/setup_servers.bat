@echo off
REM setup_servers.bat - nastaví Python venv a nainstaluje dependencies pro všechny komponenty

cd /d "%~dp0"

setlocal

if not exist ".venv\Scripts\python.exe" (
    echo Vytvarim venv...
    python -m venv .venv
    if errorlevel 1 (
        echo ERROR: Nepodarilo se vytvorit venv
        pause
        exit /b 1
    )
)

call .venv\Scripts\activate.bat
if errorlevel 1 (
    echo ERROR: Nepodarilo se aktivovat venv
    pause
    exit /b 1
)

echo Aktualizuji pip...
python -m pip install --upgrade pip

if errorlevel 1 (
    echo ERROR: Nepodarilo se aktualizovat pip
    pause
    exit /b 1
)

echo Instalace dependencies pro mock server...
python -m pip install flask requests
if errorlevel 1 (
    echo ERROR: Nepodarilo se nainstalovat dependencies pro mock server
    pause
    exit /b 1
)

echo Instalace dependencies pro gateway...
python -m pip install -r eHistorian.Gateway\requirements.txt
if errorlevel 1 (
    echo ERROR: Nepodarilo se nainstalovat dependencies pro gateway
    pause
    exit /b 1
)

echo.
echo HOTOVO - venv je pripraveno.
echo.
echo Spustit vse: START_ALL.bat
pause
endlocal
