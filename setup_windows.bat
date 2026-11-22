@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo [1/4] Creating Python environment...
if not exist ".venv\Scripts\python.exe" (
    py -3.12 -m venv .venv
    if errorlevel 1 py -3 -m venv .venv
    if errorlevel 1 (
      echo Python 3.12+ required. Install Python and enable the py launcher.
      pause
      exit /b 1
    )
)
echo [2/4] Installing packages...
".venv\Scripts\python.exe" -m pip install --upgrade pip
if errorlevel 1 goto fail
".venv\Scripts\python.exe" -m pip install -r requirements.txt
if errorlevel 1 goto fail
echo [3/4] Generating role secrets...
".venv\Scripts\python.exe" setup.py
if errorlevel 1 goto fail
echo [4/4] Open the .env file in Notepad. Set TELEGRAM_BOT_TOKEN and BACKEND.
notepad .env
echo Setup finished. Run run_windows.bat when your config is ready.
pause
exit /b 0
:fail
echo Setup failed. Check your Internet connection and Python version.
pause
exit /b 1
