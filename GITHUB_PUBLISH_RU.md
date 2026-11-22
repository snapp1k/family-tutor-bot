# Публичная публикация Family Tutor Bot: snapp1k

Подготовленные исходники не включают Telegram-токен, реальные ключи API, авторизацию Codex и базу заданий. Все настоящие секреты хранятся только в локальном `.env` или на сервере Ubuntu. Никогда не публикуйте реальные учебные переписки и фотографии ребёнка.

**Цель:** https://github.com/snapp1k/family-tutor-bot (**Public**).

## Вариант A — публикация из ChatGPT

В GitHub вручную создайте пустой публичный репозиторий `family-tutor-bot` в аккаунте `snapp1k` на https://github.com/new. **Не** добавляйте README, .gitignore или лицензию на этапе создания. Затем напишите ChatGPT: «репозиторий создан». Подключение ChatGPT может загрузить файлы в уже созданный репозиторий, если предоставлены соответствующие права.

## Вариант B — самостоятельно одной командой на Windows

Установите Git, GitHub CLI (`gh`) и Python, выполните `gh auth login` под **snapp1k**. В PowerShell откройте папку проекта и запустите:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\publish_github_windows.ps1
```

Скрипт проверит аккаунт, отсканирует подготовленные для Git файлы, создаст репозиторий **Public** и отправит их. Если репозиторий уже существует, скрипт остановится без перезаписи.

## Вариант C — Ubuntu

Установите Git, GitHub CLI и Python 3. Выполните `gh auth login` от **snapp1k**, затем из папки проекта:

```bash
bash publish_github_ubuntu.sh
```

После публикации откройте GitHub Actions → `Python tests`. Запуск Telegram-бота на Ubuntu описан в `README.md` и `QUICKSTART_RU.txt`.

**Перед публикацией:** проверьте `git status` / `git diff --cached --name-only` и не включайте `.env`, базы, фото, логи, а также резервные копии. Скрипт проверки предотвращает лишь типовые утечки, а не все возможные.
