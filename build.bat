@echo off
setlocal
cd /d "%~dp0"
if not exist .venv (
  py -3.11 -m venv .venv
)
call .venv\Scripts\activate
python -m pip install --upgrade pip
pip install -r requirements.txt
pyinstaller --noconfirm --clean --onefile --windowed --name AstraComputerAgent --collect-all pyautogui --collect-all PIL app.py
echo.
echo Build complete. EXE: dist\AstraComputerAgent.exe
echo Keep your .env file beside the EXE. Do not share it.
pause
