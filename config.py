"""Simple environment configuration."""
import os
from pathlib import Path
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent
load_dotenv(ROOT / '.env')


def setting(name, default=''):
    return os.getenv(name, default).strip()


BOT_TOKEN = setting('TELEGRAM_BOT_TOKEN')
PARENT_CODE = setting('PARENT_PAIR_CODE')
STUDENT_CODE = setting('STUDENT_PAIR_CODE')
TESTER_CODE = setting('TESTER_PAIR_CODE')
BACKEND = setting('BACKEND', 'mock').lower()
OPENAI_API_KEY = setting('OPENAI_API_KEY')
API_MODEL = setting('API_MODEL', 'gpt-4.1-mini')
MAX_DAILY_TURNS = int(setting('MAX_DAILY_TURNS', '60'))
MODEL = setting('CODEX_MODEL')
OLLAMA_MODEL = setting('OLLAMA_MODEL', 'gemma3:4b')
DATA_DIR = ROOT / 'data'
UPLOAD_DIR = DATA_DIR / 'uploads'
DB_FILE = DATA_DIR / 'tutor.sqlite3'


def validate():
    if not BOT_TOKEN or ':' not in BOT_TOKEN:
        raise RuntimeError('TELEGRAM_BOT_TOKEN отсутствует: запустите setup.py и вставьте токен от BotFather в .env')
    codes = [PARENT_CODE, STUDENT_CODE, TESTER_CODE]
    if any(len(s) < 16 for s in codes) or len(set(codes)) != 3:
        raise RuntimeError('Коды привязки должны быть уникальными и содержать минимум 16 символов (setup.py).')
    if BACKEND not in ('mock', 'codex', 'ollama', 'openai_api'):
        raise RuntimeError('BACKEND должен быть mock, codex, ollama или openai_api')
    if BACKEND == 'openai_api' and not OPENAI_API_KEY.startswith('sk-'):
        raise RuntimeError('При BACKEND=openai_api установите OPENAI_API_KEY в .env')
    if MAX_DAILY_TURNS < 1 or MAX_DAILY_TURNS > 200:
        raise RuntimeError('MAX_DAILY_TURNS должен быть от 1 до 200')
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
