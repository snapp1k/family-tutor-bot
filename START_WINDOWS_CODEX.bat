@echo off
setlocal EnableExtensions DisableDelayedExpansion
rem Open a persistent cmd shell so double-clicking never loses the error message.
rem The /K shell remains even if the bot or the launcher exits unexpectedly.
if /I "%~1"=="--inside" goto :inside
"%ComSpec%" /D /K ""%~f0" --inside"
exit /b

:inside
cd /d "%~dp0"
title Family Tutor - Codex on Windows - diagnostic console
chcp 65001 >nul 2>&1
echo ========================================================
echo  FAMILY TUTOR - WINDOWS / CODEX CHATGPT
 echo  This window stays open, even if something goes wrong.
echo ========================================================
echo.
if not exist "bot.py" goto :not_extracted
if not exist "requirements.txt" goto :not_extracted
if not exist "windows_launcher.py" goto :not_extracted

set "BOOTSTRAP=py -3"
%BOOTSTRAP% -c "import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)" >nul 2>&1
if not errorlevel 1 goto :python_ok
set "BOOTSTRAP=python"
%BOOTSTRAP% -c "import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)" >nul 2>&1
if errorlevel 1 goto :no_python

:python_ok
if not exist ".venv\Scripts\python.exe" (
    echo [1/3] Creating local Python environment...
    %BOOTSTRAP% -m venv .venv
    if errorlevel 1 goto :venv_failed
)
if not exist ".venv\Scripts\python.exe" goto :venv_failed

rem Reinstall missing packages if the venv was copied from another PC.
echo [2/3] Checking Python packages...
".venv\Scripts\python.exe" -c "import telegram, dotenv, PIL" >nul 2>&1
if errorlevel 1 (
    echo Installing project dependencies. This does not buy a subscription.
    ".venv\Scripts\python.exe" -m pip install -r requirements.txt
    if errorlevel 1 goto :packages_failed
)

echo [3/3] Starting configuration checks and Telegram bot...
".venv\Scripts\python.exe" windows_launcher.py
set "RESULT=%errorlevel%"
echo.
if "%RESULT%"=="0" (
    echo [INFO] The bot process finished. It is no longer running.
) else (
    echo [ERROR] The bot did not start or stopped unexpectedly. Exit code: %RESULT%
)
echo The diagnostic log is in data\logs\windows_startup.log
 echo This console will remain open. Type exit to close it.
exit /b %RESULT%

:not_extracted
echo [ERROR] Required files are missing next to START_WINDOWS_CODEX.bat.
echo Extract the WHOLE ZIP into a normal folder, then run the BAT from that folder.
echo Do not double-click the BAT inside a ZIP preview.
goto :end_failure

:no_python
echo [ERROR] Python 3.10 or newer is not on PATH.
echo Install Python from https://www.python.org/downloads/windows/
echo Reopen this folder and run START_WINDOWS_CODEX.bat again.
goto :end_failure

:venv_failed
echo [ERROR] Could not create .venv. Check folder permissions and Python installation.
goto :end_failure

:packages_failed
echo [ERROR] Could not install Python packages. Check pip and Internet access.
goto :end_failure

:end_failure
echo.
echo This window will remain open for diagnosis. Type exit to close it.
exit /b 1
