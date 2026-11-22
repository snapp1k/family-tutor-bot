@echo off
chcp 65001 >nul
setlocal
cd /d "%~dp0"
echo ==========================================
echo  FAMILY TUTOR - CODEX WINDOWS CONNECTION
 echo ==========================================
if not exist ".venv\Scripts\python.exe" (
  echo [ERROR] First run setup_windows.bat.
  goto :fail
)
where codex >nul 2>&1
if errorlevel 1 (
  echo [ERROR] Codex CLI not found.
  echo Install Node.js LTS, then run this in a NEW PowerShell window:
  echo   npm.cmd install -g @openai/codex@latest
  echo Then run connect_codex_windows.bat again.
  goto :fail
)
echo [1/3] Checking ChatGPT login...
call codex login status
if errorlevel 1 (
  echo No active Codex login. Opening the ChatGPT login...
  call codex login
  if errorlevel 1 goto :fail
)
echo [2/3] Running a safe tutor test before switching the bot...
".venv\Scripts\python.exe" smoke_test.py --backend codex
if errorlevel 1 (
  echo [ERROR] Codex test did not pass. The bot backend was NOT changed.
  echo Check codex login status and your usage limits.
  goto :fail
)
echo [3/3] Updating .env without changing secrets...
".venv\Scripts\python.exe" switch_backend.py codex
if errorlevel 1 goto :fail
echo.
echo [OK] Codex tutor test passed and BACKEND=codex is configured.
echo Stop old run_windows.bat with Ctrl+C and start it again.
pause
exit /b 0
:fail
echo.
echo Could not connect Codex. See the error above.
pause
exit /b 1
