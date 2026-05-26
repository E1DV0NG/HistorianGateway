@echo off
REM START_ALL.bat - Spusti vse v nových oknech

cd /d "%~dp0"

echo.
echo ========================================
echo   eHistorian Gateway - AUTOMATIC START
echo ========================================
echo.
echo Spoustim 3 komponenty v samostatných oknech...
echo.

REM 1. Instalace dependencies (pokud chybí)
if not exist ".venv" (
    echo Setup - instaluji dependencies...
    call run_server.bat
)

REM 2. Server v prvním okně
echo Spoustim Server (CMD 1)...
start "eHistorian Server" cmd /k "1_server.bat"
timeout /t 2 /nobreak

REM 3. Gateway v druhém okně
echo Spoustim Gateway (CMD 2)...
start "eHistorian Gateway" cmd /k "2_gateway.bat"
timeout /t 2 /nobreak

REM 4. Test v třetím okně
echo Spoustim Test (CMD 3)...
start "eHistorian Test" cmd /k "3_test.bat"

echo.
echo ========================================
echo Všechny 3 komponenty jsou spuštěny!
echo.
echo Okno 1 = Server (přijímá data)
echo Okno 2 = Gateway (sbírá data)
echo Okno 3 = Test (posílá test data)
echo.
echo Data najdeš v: logs\
echo ========================================
echo.
pause
