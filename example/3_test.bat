@echo off
REM 3_test.bat - Posle test request

title eHistorian Test Request
cd /d "%~dp0"

echo.
echo ========================================
echo   Posílám test request...
echo ========================================
echo.
echo Aktivuji venv...
call .venv\Scripts\activate.bat
if errorlevel 1 (
    echo ERROR: Nemuzu aktivovat venv
    echo Zkus spustit: run_server.bat
    pause
    exit /b 1
)

echo Spoustim test...
python test_request.py
if errorlevel 1 (
    echo ERROR pri spusteni testu!
    pause
    exit /b 1
)

echo.
echo HOTOVO - podívej se do CMD 1 (server)
echo.
pause

