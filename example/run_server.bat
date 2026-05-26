@echo off
echo Aktivuji venv a instaluji dependencies...
call .venv\Scripts\activate.bat
pip install flask requests -q
echo.
echo HOTOVO - dependencies instalovany
echo.
python server.py
