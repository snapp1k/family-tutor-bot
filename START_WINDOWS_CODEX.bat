@echo off
chcp 65001 >nul
setlocal EnableExtensions
cd /d "%~dp0"
title Family Tutor - Codex on Windows

echo ====================================================
echo     FAMILY TUTOR - WINDOWS / CHATGPT CODEX MODE
echo ====================================================
echo.
echo This starter uses your existing Codex CLI ChatGPT login.
echo No API key or new paid subscription is required.
echo.

if not exist ".venv\Scripts\python.exe" (
    echo [1/6] Installing Python dependencies on first run...
    call "%~dp0setup_windows.bat"
    if errorlevel 1 goto :fail
)
if not exist ".env" (
    echo [1/6] Creating private configuration...
    ".venv\Scripts\python.exe" setup.py
    if errorlevel 1 goto :fail
    notepad ".env"
)

echo [2/6] Checking bot settings...
".venv\Scripts\python.exe" windows_preflight.py --config
if errorlevel 1 (
    echo Fix .env in Notepad, then close it to retry.
    notepad ".env"
    ".venv\Scripts\python.exe" windows_preflight.py --config
    if errorlevel 1 goto :fail
)

echo [3/6] Checking Codex installation...
where codex >nul 2>&1
if errorlevel 1 (
    echo Codex CLI is missing. Install Node.js LTS then run:
    echo npm.cmd install -g @openai/codex@latest
    echo Open a new terminal and retry.
    goto :fail
)

echo [4/6] Checking ChatGPT login...
".venv\Scripts\python.exe" windows_preflight.py --codex-login
if errorlevel 1 (
    call codex login
    if errorlevel 1 goto :fail
    ".venv\Scripts\python.exe" windows_preflight.py --codex-login
    if errorlevel 1 goto :fail
)

echo [5/6] Testing AI and enabling Codex...
".venv\Scripts\python.exe" windows_preflight.py --backend-is-codex
if errorlevel 1 (
    echo Sending one real test request to Codex...
    ".venv\Scripts\python.exe" smoke_test.py --backend codex
    if errorlevel 1 goto :fail
    ".venv\Scripts\python.exe" switch_backend.py codex
    if errorlevel 1 goto :fail
) else (
    echo Codex already configured; no extra model test on restart.
)

echo [6/6] Starting Telegram bot...
".venv\Scripts\python.exe" windows_preflight.py --config
if errorlevel 1 goto :fail
echo Keep this window open. Ctrl+C stops the bot.
echo Stop any Ubuntu/other Windows copy using the same BotFather token!
".venv\Scripts\python.exe" bot.py
if errorlevel 1 goto :fail
exit /b 0

:fail
echo.
echo [ERROR] Cannot finish startup. Read the first error above.
pause
exit /b 1
