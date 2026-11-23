"""Windows one-click Codex launcher. Stdlib-only until dependencies have been installed.

The BAT runs this script under the project's .venv. No bot secrets, prompts or
homework content are written to the startup log. Console may show Python
exceptions; redact sensitive strings before sharing screenshots.
"""
from __future__ import annotations

from datetime import datetime
from pathlib import Path
import subprocess
import sys
import traceback

ROOT = Path(__file__).resolve().parent
LOGFILE = ROOT / 'data' / 'logs' / 'windows_startup.log'


def record(stage: str, status: str) -> None:
    """Record only fixed status text; never write credentials or student data."""
    valid_stages = {
        'bootstrap', 'config', 'codex_found', 'codex_login', 'model_smoke',
        'backend_switch', 'bot_run', 'unexpected_error',
    }
    valid_status = {
        'begin', 'ok', 'missing', 'failed', 'starting', 'stopped',
        'stopped_unexpectedly', 'skipped', 'not_configured',
    }
    if stage not in valid_stages or status not in valid_status:
        raise ValueError('Diagnostic status not allowed')
    LOGFILE.parent.mkdir(parents=True, exist_ok=True)
    # Separate each run; no private content in the log.
    with LOGFILE.open('a', encoding='utf-8') as fh:
        fh.write(f'{datetime.now().isoformat(timespec="seconds")} {stage}: {status}\n')


def call_python(*args: str) -> int:
    return subprocess.run([sys.executable, *args], cwd=ROOT, check=False).returncode


def configure() -> bool:
    if not (ROOT / '.env').exists():
        print('[CONFIG] New installation: creating a private .env with random role codes.', flush=True)
        if call_python('setup.py') != 0:
            record('config', 'failed')
            return False
        print('[CONFIG] Paste your BotFather token into TELEGRAM_BOT_TOKEN, then SAVE and close Notepad.', flush=True)
        try:
            subprocess.run(['notepad.exe', str(ROOT / '.env')], check=False)
        except OSError:
            print('Cannot open Notepad. Edit the .env file manually.', flush=True)
    if call_python('windows_preflight.py', '--config') == 0:
        record('config', 'ok')
        return True
    print('\n[CONFIG] Check the .env file in the project folder.', flush=True)
    print('Do not send .env or Telegram tokens to anyone.', flush=True)
    try:
        subprocess.run(['notepad.exe', str(ROOT / '.env')], check=False)
    except OSError:
        print('Notepad could not be opened. Edit .env manually.', flush=True)
    if call_python('windows_preflight.py', '--config') == 0:
        record('config', 'ok')
        return True
    record('config', 'failed')
    return False


def check_codex() -> bool:
    import shutil
    import windows_preflight

    cli = shutil.which('codex') or shutil.which('codex.cmd')
    if not cli:
        record('codex_found', 'missing')
        print('[CODEX] Codex CLI not detected in PATH.', flush=True)
        print('In PowerShell: npm.cmd install -g @openai/codex@latest', flush=True)
        print('Then reopen the launcher so it sees the updated PATH.', flush=True)
        return False
    record('codex_found', 'ok')
    if windows_preflight.check_chatgpt_login():
        record('codex_login', 'ok')
        return True
    print('[CODEX] Starting interactive Codex login. Choose ChatGPT, NOT API key.', flush=True)
    try:
        result = subprocess.run([cli, 'login'], cwd=ROOT, check=False)
        if result.returncode == 0 and windows_preflight.check_chatgpt_login():
            record('codex_login', 'ok')
            return True
    except (OSError, subprocess.SubprocessError):
        pass
    record('codex_login', 'failed')
    print('[CODEX] Could not confirm ChatGPT login. Try codex.cmd login in PowerShell.', flush=True)
    return False


def configure_codex_backend() -> bool:
    import windows_preflight

    if windows_preflight.backend_is_codex():
        record('model_smoke', 'skipped')
        print('[CODEX] BACKEND=codex already set; skipping duplicate model test.', flush=True)
        return True
    print('[CODEX] Sending a one-time tutoring test through Codex CLI.', flush=True)
    print('This uses the existing ChatGPT plan allowance; no API key is used.', flush=True)
    if call_python('smoke_test.py', '--backend', 'codex') != 0:
        record('model_smoke', 'failed')
        print('[CODEX] Model test failed. Configuration was not changed.', flush=True)
        print('Check account limits, network, and Codex version.', flush=True)
        return False
    record('model_smoke', 'ok')
    if call_python('switch_backend.py', 'codex') != 0:
        record('backend_switch', 'failed')
        return False
    record('backend_switch', 'ok')
    return True


def main() -> int:
    print('Project folder:', ROOT, flush=True)
    print('Startup diagnostic log:', LOGFILE, flush=True)
    record('bootstrap', 'begin')
    try:
        if not configure():
            return 2
        if not check_codex():
            return 3
        if not configure_codex_backend():
            return 4
        print('\n[TELEGRAM] Launching tutor with Codex. Keep this window open.', flush=True)
        print('Stop the OLD bot instance, if any; only one copy may poll Telegram.', flush=True)
        record('bot_run', 'starting')
        status = call_python('bot.py')
        record('bot_run', 'stopped' if status == 0 else 'stopped_unexpectedly')
        if status == 0:
            print('[TELEGRAM] Bot stopped normally (it is not running now).', flush=True)
        else:
            print('[TELEGRAM] Bot stopped with error code', status, flush=True)
            print('If the log mentions "Conflict" or "getUpdates", stop other copies.', flush=True)
        return status
    except KeyboardInterrupt:
        print('\n[TELEGRAM] Interrupted by user.', flush=True)
        record('bot_run', 'stopped')
        return 0
    except Exception as exc:
        record('unexpected_error', 'failed')
        print('[ERROR] Unexpected launcher error:', type(exc).__name__, flush=True)
        traceback.print_exc()
        return 9


if __name__ == '__main__':
    raise SystemExit(main())
