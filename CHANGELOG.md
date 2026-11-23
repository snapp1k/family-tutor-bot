## 2026-11-23 — Windows Codex launcher

- Новый единый `START_WINDOWS_CODEX.bat` для Windows, сохраняющий `.env`/`data` и включающий Codex только после реального пробного запроса; при первой настройке `.env` создаётся с `BACKEND=mock` и переключается после теста.
- Исправлена проблема потери ChatGPT-авторизации на Windows из-за очистки переменных `USERPROFILE`, `APPDATA`, `LOCALAPPDATA`, `SYSTEMROOT`, `PATHEXT` при вызове дочернего процесса.
- Секреты BotFather и коды привязки по-прежнему не передаются в Codex.
- Повторный запуск избегает лишнего тестового расхода лимита Codex. Для принудительного теста добавлен `TEST_CODEX_WINDOWS.bat`.
- Предпроверка `.env` и CLI — `windows_preflight.py`; дымовой тест теперь сообщает ошибку, если модель вернула лишь безопасную запасную фразу.

# Changes 2026-11-22 — FamilyTutor Final

- Investigated source of the repeated message: `enforce_decision()` returned identical boilerplate for most outputs lacking `?`, exceeding a fixed size or containing `x = number`.
- Replaced canned output with strict validation, optional single retry after repetition/unsafe result, and context-sensitive local fallback.
- Added exact recent assistant reply similarity check, natural language policy for continuing the student's current step, and bounded history per assignment.
- Reworked direct answer requests: keep safe flag for parent's report while sending model a topic-specific request for a hint rather than always returning the same refusal.
- Added official OpenAI Responses API backend with vision, JSON schema, stateless generation, `store=false`, and higher-priority developer instructions; includes optional Pro subscription API-credit path.
- Kept experimental Codex CLI backend, hardened subprocess environment to pass only an explicit allowlist, verify ChatGPT login rather than API key, use no shell and read-only sandbox.
- Added Ubuntu dedicated service user `tutorbot`, hardened systemd unit, non-destructive upgrade path, smoke tests, diagnostics, local backups, parent `/health` command.
- Added 34 automated offline tests (storage, ID auth, anti-loop, explicit answer gate, API construction, Codex isolation, Telegram role flows).

**Validation scope:** local static compilation, Shell syntax checks, tests and demo smoke test. Live Telegram, father's ChatGPT subscription and Ubuntu service/network cannot be validated without credentials and access to his VM.

## 2026-11-23 — Windows launcher diagnostic hotfix

- Исправлено мгновенное закрытие окна `START_WINDOWS_CODEX.bat`: запуск выполняется через постоянную оболочку `cmd /K` и оставляет видимым любое сообщение об ошибке.
- Добавлены проверки полного извлечения ZIP, Python 3.10+, состояния виртуального окружения и зависимостей.
- Добавлен `windows_launcher.py`: проверка `.env` отдельным процессом (без устаревшего состояния конфигурации), Codex login, одноразовый тест и запуск Telegram.
- Секреты, переписка и фото не записываются в `data/logs/windows_startup.log`; сохраняются только этапы и статусы.
- При ошибке или штатной остановке окно остаётся открытым; запуск не обещает, что модель или Telegram доступны без проверки на конкретном ПК.
