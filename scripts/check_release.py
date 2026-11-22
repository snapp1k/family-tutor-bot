"""Small pre-publish guard, not a substitute for dedicated secrets scanning."""
from __future__ import annotations

import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
result = subprocess.run(
    ['git', 'ls-files', '-z'],
    cwd=ROOT, check=True, capture_output=True,
)
paths = [p.decode('utf-8') for p in result.stdout.split(b'\0') if p]

for rel in paths:
    p = Path(rel)
    name = p.name.lower()
    if (
        rel == '.env'
        or (rel.startswith('.env.') and rel != '.env.example')
        or rel.startswith('data/')
        or rel.startswith('backups/')
        or '.codex' in p.parts
        or name in {'auth.json'}
        or p.suffix.lower() in {'.sqlite3', '.db', '.pem', '.p12', '.key'}
    ):
        raise SystemExit(f'ОШИБКА: приватный путь в git index: {rel}')

    if p.suffix.lower() not in {'.py', '.md', '.txt', '.ini', '.toml', '.yml', '.yaml', '.sh', '.bat', '.ps1', '.example', '.service', ''}:
        continue
    try:
        content = (ROOT / p).read_text(encoding='utf-8', errors='ignore')
    except FileNotFoundError:
        continue
    # Token formats are intentionally conservative; review staged files manually too.
    telegram = re.search(r'\b\d{8,12}:[A-Za-z0-9_-]{30,}\b', content)
    openai = re.search(r'\bsk-(?:proj-)?[A-Za-z0-9_-]{25,}\b', content)
    if telegram or openai:
        raise SystemExit(f'ОШИБКА: возможный настоящий токен в файле {rel}')

print(f'OK: {len(paths)} отслеживаемых файлов; типовые секреты и приватные пути не обнаружены.')
