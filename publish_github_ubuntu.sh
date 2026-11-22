#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")"
TARGET=snapp1k/family-tutor-bot
for cmd in git gh python3; do
  if ! command -v "$cmd" >/dev/null 2>&1; then
    echo "Не найдена команда '$cmd'. Установите её и повторите."
    exit 1
  fi
done
if ! gh auth status >/dev/null 2>&1; then
  echo 'Авторизуйтесь сначала: gh auth login'
  exit 1
fi
LOGIN="$(gh api user --jq .login)"
if [[ "${LOGIN,,}" != 'snapp1k' ]]; then
  echo "GitHub вошёл как '$LOGIN', а нужен snapp1k. Публикация остановлена."
  exit 1
fi
if gh repo view "$TARGET" >/dev/null 2>&1; then
  echo "Репозиторий $TARGET уже существует. Скрипт не перезаписывает существующий репозиторий."
  exit 1
fi
if [[ ! -d .git ]]; then git init -b main; fi
git config --local user.name "$LOGIN"
GITHUB_ID="$(gh api user --jq .id)"
git config --local user.email "${GITHUB_ID}+${LOGIN}@users.noreply.github.com"
git add .
python3 scripts/check_release.py
if ! git diff --cached --quiet; then git commit -m 'Initial Family Tutor Bot release'; fi
echo 'Создаём ПУБЛИЧНЫЙ репозиторий и загружаем код...'
gh repo create "$TARGET" --public --source=. --remote=origin --push --description 'Telegram family tutor with parent oversight and Ubuntu deployment'
echo "Готово: https://github.com/$TARGET"
