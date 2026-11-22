"""Safely change BACKEND in the existing .env without touching credentials or codes."""
from __future__ import annotations

import argparse
from pathlib import Path
import re

ENV = Path(__file__).resolve().parent / '.env'


def switch_backend(content: str, backend: str) -> str:
    if backend not in ('codex', 'mock', 'ollama', 'openai_api'):
        raise ValueError('Unsupported backend')
    pattern = re.compile(r'(?mi)^\s*BACKEND\s*=\s*[^\r\n]*')
    matches = list(pattern.finditer(content))
    if len(matches) > 1:
        raise ValueError('Multiple BACKEND entries; edit .env manually.')
    if matches:
        return pattern.sub('BACKEND=' + backend, content, count=1)
    newline = '\r\n' if '\r\n' in content else '\n'
    return content + ('' if not content or content.endswith(('\r', '\n')) else newline) + 'BACKEND=' + backend + newline


def main() -> None:
    parser = argparse.ArgumentParser(description='Change AI engine in existing .env.')
    parser.add_argument('backend', choices=('codex', 'mock', 'ollama', 'openai_api'))
    args = parser.parse_args()
    if not ENV.is_file():
        parser.exit(2, 'ERROR: .env was not found. Run setup_windows.bat first.\n')
    raw = ENV.read_bytes()
    try:
        # utf-8-sig accepts a BOM, if Notepad added one. Nothing else is modified.
        content = raw.decode('utf-8-sig')
        updated = switch_backend(content, args.backend)
    except (UnicodeDecodeError, ValueError) as exc:
        parser.exit(2, f'ERROR: {exc}\n')
    if updated != content:
        ENV.write_bytes((b'\xef\xbb\xbf' if raw.startswith(b'\xef\xbb\xbf') else b'') + updated.encode('utf-8'))
    print('AI backend selected: ' + args.backend)
    print('Existing Telegram token and pair codes were not changed.')


if __name__ == '__main__':
    main()
