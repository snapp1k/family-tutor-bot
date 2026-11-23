## 2026-11-23 — Windows Codex launcher

- Единый `START_WINDOWS_CODEX.bat`: сохраняет `.env`/`data`, подключает Codex после пробного запроса.
- Исправлено окружение Windows: `USERPROFILE`, `APPDATA`, `LOCALAPPDATA`, `SYSTEMROOT`, `PATHEXT` теперь доступны процессу Codex.
- Telegram-токены, API-ключи и секретные коды по-прежнему не передаются процессу Codex.
- Повторный запуск не расходует лимит на лишний пробный запрос. `TEST_CODEX_WINDOWS.bat` запускает проверку по запросу.
- Проверка конфигурации и CLI: `windows_preflight.py`. Smoke-test прекращает установку при небезопасном fallback.

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
