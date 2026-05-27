@echo off
REM create_venv.bat - vytvori Python venv a nainstaluje pyodbc

cd /d "%~dp0"

if exist ".venv\Scripts\python.exe" (
    echo .venv jiz existuje.
    goto install_deps
)

echo Vytvarim .venv...
python -m venv .venv

if errorlevel 1 (
    echo ERROR: Nepodarilo se vytvorit .venv
    pause
    exit /b 1
)

:install_deps
echo.
echo Aktualizuji pip na nejnovejsi verzi (prevence chyb s pyodbc)...
.venv\Scripts\python.exe -m pip install --upgrade pip

echo.
echo Instaluji pyodbc a asyncua (pro tvuj kod)...
REM Zde instalujeme pyodbc a asyncua, ktere tvuj gateway projekt potrebuje
.venv\Scripts\python.exe -m pip install pyodbc asyncua fastapi uvicorn

if errorlevel 1 (
    echo.
    echo [ERROR] Instalace pyodbc selhala. 
    echo Pravdepodobne ti na Windows chybi Microsoft C++ Build Tools.
    echo Zkus rucne stahnout predkompilovany balicek (.whl) nebo nainstalovat:
    echo https://visualstudio.microsoft.com/visual-cpp-build-tools/
    pause
    exit /b 1
)

echo.
echo HOTOVO - .venv je pripraveno a balicky jsou nainstalovany.
echo Aktivuj pomoci: call .venv\Scripts\activate.bat
pause