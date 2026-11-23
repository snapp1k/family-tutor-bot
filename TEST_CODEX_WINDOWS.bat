@echo off
chcp 65001 >nul
setlocal
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
  echo Run START_WINDOWS_CODEX.bat first.
  pause
  exit /b 1
)
echo Running offline tests...
".venv\Scripts\python.exe" -m unittest discover -s tests -v
if errorlevel 1 goto :fail
echo Running one LIVE Codex test (uses subscription allowance)...
".venv\Scripts\python.exe" smoke_test.py --backend codex
if errorlevel 1 goto :fail
echo All tests passed.
pause
exit /b 0
:fail
echo A test failed; see error above.
pause
exit /b 1
