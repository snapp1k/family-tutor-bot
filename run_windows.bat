@echo off
chcp 65001 >nul
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
   echo Please run setup_windows.bat first.
   pause
   exit /b 1
)
".venv\Scripts\python.exe" windows_preflight.py --config
if errorlevel 1 (
  pause
  exit /b 1
)
".venv\Scripts\python.exe" bot.py
if errorlevel 1 (
  echo Bot stopped with an error. Review .env, Codex login status or Ollama.
  pause
)
