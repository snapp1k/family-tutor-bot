"""Windows launcher diagnostics. Never prints Telegram or Codex secrets."""
from __future__ import annotations

import argparse
import shutil
import subprocess


def validate_config() -> bool:
    import config
    try:
        original = config.BACKEND
        config.BACKEND = 'codex'
        try:
            config.validate()
        finally:
            config.BACKEND = original
    except (ValueError, RuntimeError, OSError) as exc:
        print('CONFIG ERROR:', exc)
        print('Check your BotFather token and three generated role codes in .env.')
        return False
    print('OK: Bot settings configured. Private values are hidden.')
    return True


def check_chatgpt_login() -> bool:
    from tutor import codex_subprocess_env
    cli = shutil.which('codex')
    if not cli:
        print('CODEX ERROR: Codex CLI not found on PATH.')
        return False
    try:
        result = subprocess.run([cli, 'login', 'status'],
                                capture_output=True, text=True,
                                encoding='utf-8', errors='replace',
                                timeout=20, env=codex_subprocess_env())
    except (OSError, subprocess.TimeoutExpired):
        print('CODEX ERROR: Cannot run codex login status.')
        return False
    output = (result.stdout + '\n' + result.stderr).lower()
    if result.returncode == 0 and 'chatgpt' in output and 'api key' not in output:
        print('OK: Codex CLI is logged in with ChatGPT, not an API key.')
        return True
    print('CODEX ERROR: ChatGPT subscription login was not detected.')
    print('Run: codex login (choose Sign in with ChatGPT).')
    return False


def backend_is_codex() -> bool:
    from dotenv import dotenv_values
    from pathlib import Path
    return dotenv_values(Path(__file__).resolve().parent / '.env', encoding='utf-8-sig').get('BACKEND', '').lower() == 'codex'


def main() -> int:
    parser = argparse.ArgumentParser()
    modes = parser.add_mutually_exclusive_group(required=True)
    modes.add_argument('--config', action='store_true')
    modes.add_argument('--codex-login', action='store_true')
    modes.add_argument('--backend-is-codex', action='store_true')
    args = parser.parse_args()
    if args.config:
        return 0 if validate_config() else 1
    if args.codex_login:
        return 0 if check_chatgpt_login() else 1
    return 0 if backend_is_codex() else 1


if __name__ == '__main__':
    raise SystemExit(main())
