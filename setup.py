"""Generate local config and unique secure role codes. Never print Telegram token."""
from pathlib import Path
import secrets

path = Path(__file__).resolve().parent / '.env'
if path.exists():
    print('Конфиг .env уже существует, ничего не перезаписано.')
else:
    items = [
        '# НЕ выкладывайте этот файл и не отправляйте никому!\n',
        'TELEGRAM_BOT_TOKEN=PASTE_TOKEN_HERE\n',
        'BACKEND=codex\n',
        'OPENAI_API_KEY=\n',
        'API_MODEL=gpt-4.1-mini\n',
        'MAX_DAILY_TURNS=60\n',
        'CODEX_MODEL=\n',
        'OLLAMA_MODEL=gemma3:4b\n',
        *[f'{role}_PAIR_CODE={secrets.token_urlsafe(24)}\n' for role in ('PARENT', 'STUDENT', 'TESTER')],
    ]
    path.write_text(''.join(items), encoding='utf-8')
    try:
        path.chmod(0o600)
    except OSError:
        pass
    print('Создан .env. Вставьте токен BotFather и установите BACKEND=mock, codex, openai_api или ollama.')
    print('Коды активации находятся в .env; не публикуйте их.')
