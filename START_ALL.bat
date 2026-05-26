@echo off
cd /d "%~dp0"

echo ========================================
echo   eHistorian - Startovaci Skript
echo ========================================

if not exist ".venv\Scripts\activate.bat" (
    call setup_env.bat
)

echo Spoustim eHistorian Server...
echo Otevri prohlizec na: http://localhost:5000
echo (Z UI muzes zapnout Gateway a spravovat konfiguraci)
echo.

call 1_server.bat
