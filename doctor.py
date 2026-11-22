"""Read-only diagnostics; never print tokens, API keys, credentials, or student messages."""
import os
import shutil
import sqlite3
import subprocess
import sys
from pathlib import Path
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent
load_dotenv(ROOT/'.env')
backend = os.getenv('BACKEND','mock')
token = os.getenv('TELEGRAM_BOT_TOKEN','')
print('Family Tutor diagnostics')
print('Python:', sys.version.split()[0])
print('Backend:', backend)
print('BotFather token configured:', bool(':' in token and 'PASTE' not in token))
print('Data folder writable:', os.access(ROOT/'data', os.W_OK))
print('SQLite file exists:', (ROOT/'data'/'tutor.sqlite3').exists())
if (ROOT/'data'/'tutor.sqlite3').exists():
    with sqlite3.connect(ROOT/'data'/'tutor.sqlite3') as db:
        print('SQLite quick check:',db.execute('PRAGMA quick_check').fetchone()[0])
if backend == 'codex':
    found = shutil.which('codex')
    print('Codex found on service PATH:',bool(found),found or '')
    if found:
        allow = {'PATH','HOME','USER','LOGNAME','LANG','LC_ALL','CODEX_HOME','XDG_CONFIG_HOME'}
        env = {key: value for key, value in os.environ.items() if key in allow}
        try:
            r=subprocess.run([found,'login','status'],capture_output=True,text=True,timeout=12,env=env)
            print('ChatGPT login valid:',r.returncode==0 and 'chatgpt' in (r.stdout+r.stderr).lower())
        except (OSError,subprocess.TimeoutExpired):
            print('ChatGPT login valid: unavailable')
if backend == 'openai_api':
    print('API key configured:', bool(os.getenv('OPENAI_API_KEY','').startswith('sk-')))
    print('Model:',os.getenv('API_MODEL','gpt-4.1-mini'))
print('To verify the live model run smoke_test.py. It may consume subscription allowance or API credits.')
