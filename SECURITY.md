# Security and pedagogical threat model (2026-11-22)

## Trust boundaries

- **Telegram authentication:** only private chat; permissions are based on `effective_user.id` not `@username`. A test account deliberately has elevated access to switch between parent and student modes. Pair codes must be long and private.
- **Assignment and student content:** task descriptions, user text, photos, EXIF and conversation histories are untrusted data, including apparent system instructions or claims to be the parent. All real privileges live in code and SQLite.
- **Model outputs:** structured JSON parsing plus content checks and similarity checks, one repair attempt and contextual safe fallback. There is NO perfect automated firewall: a model can still produce an answer not detected by patterns. Human approval remains required.
- **Codex CLI:** child content on stdin, `shell=False`, read-only sandbox, temporary cwd, no direct filesystem operations by the bot. Codex is a coding agent and sandbox restrictions should also be enforced by OS isolation. A model's instruction to not use tools is not a security boundary. Do not run the service as root or give it secrets beyond those required.
- **OpenAI API:** per-project API key only in `.env` on server; Responses API with explicit `store=false`, schema and no tools. The source images still leave VM to be processed by provider. Keys are never shown in Telegram logs.
- **Ollama:** only localhost endpoint, never Internet-facing. School-age learner data warrants strong access boundaries.
- **Data storage:** SQLite and compressed JPEGs in `data`. By default old events are cleared after 30 days; task images persist until task deletion. Backups and copies require separate lifecycle management. Student work must be handled with parental awareness.

## Threat test checklist

| Attempt | Expected behavior |
| --- | --- |
| Student changes username to father's `@` | Privileges unchanged, `effective_user.id` controls role |
| Student asks for full solution | Model should refuse and give a topic-specific next step; report flags request |
| Student pastes fake `system:` or text embedded in photo | Treat as untrusted input and reject new role/instructions |
| Model returns `Ответ: ...` | Reject, retry with correction, then local contextual fallback |
| Model repeats previous boilerplate | Retry once, then contextual fallback; never repeatedly emit same fixed string |
| User's answer includes `x = 2` or no question mark | Keep legitimate explanatory output, not wholesale fallback |
| Uploads an AI-looking assignment | Do not claim certainty about authorship; request oral reasoning |
| Poor-quality photo | Ask for a clearer photo, never invent unseen content |
| `/done` before any work | Do not send as complete; require at least one student message/photo |
| CLI logged in with API key not ChatGPT | Refuse in Codex mode to avoid accidental extra charges |
| OpenAI API limit exhausted | Return technical failure, do not claim successful AI review |
| Telegram concurrent messages | Serialize by student ID and cap concurrent AI requests |
| Shutdown/restart | History persists in SQLite; service restarts automatically |

## Operational practices

1. Do not send `.env`, photos, `tutor.sqlite3`, `.codex/auth.json`, backups or API credentials to a chat, code host or support screenshot.
2. Keep VM patched; enable automatic security updates. Use SSH keys for remote administration and firewall incoming ports; Telegram polling needs no inbound connections.
3. Give the service account minimal Unix rights. For Codex CLI, login as the service account itself; never copy credentials from the father's primary Unix home.
4. If the father opts to use a personal Pro account via Codex CLI, check OpenAI's individual-account terms. For an application serving other family members, the API credit benefit is the clearer, supported integration path.
5. Regenerate Telegram bot token through BotFather and rotate pair codes if accidentally disclosed. Existing bound Telegram IDs remain in SQLite; investigate before resetting roles.
6. Do not promise AI-generated image detection, infallible cheating detection or perfect prevention of answer leakage.
7. No one outside the household should use this single-family prototype without a fresh privacy/security review.
