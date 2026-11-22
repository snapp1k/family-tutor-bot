#!/usr/bin/env bash
set -euo pipefail
# Root-owned application, dedicated non-login-to-your-personal-account Unix user.
APP_DIR=/opt/family-tutor
SRC="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
if [[ "${EUID}" -ne 0 ]]; then echo 'Запуск: sudo bash install_ubuntu.sh'; exit 1; fi
if [[ ! -e /usr/bin/apt-get ]]; then echo 'Нужен Ubuntu/Debian с apt'; exit 1; fi
apt-get update
DEBIAN_FRONTEND=noninteractive apt-get install -y python3 python3-venv python3-pip ca-certificates
if ! id tutorbot &>/dev/null; then useradd --create-home --shell /bin/bash tutorbot; fi
mkdir -p "$APP_DIR" "$APP_DIR/data/uploads"
# Ship updates without overwriting role codes, token, and SQLite history.
if [[ "$SRC" != "$APP_DIR" ]]; then
  for f in bot.py config.py tutor.py storage.py setup.py smoke_test.py requirements.txt doctor.py run_ubuntu.sh backup_ubuntu.sh; do
    cp -f "$SRC/$f" "$APP_DIR/$f"
  done
fi
if [[ ! -f "$APP_DIR/.env" && -f "$SRC/.env" ]]; then cp "$SRC/.env" "$APP_DIR/.env"; fi
if [[ ! -f "$APP_DIR/data/tutor.sqlite3" && -f "$SRC/data/tutor.sqlite3" ]]; then
  cp -a "$SRC/data/." "$APP_DIR/data/"
fi
python3 -m venv "$APP_DIR/.venv"
"$APP_DIR/.venv/bin/python" -m pip install --disable-pip-version-check -r "$APP_DIR/requirements.txt"
if [[ ! -f "$APP_DIR/.env" ]]; then "$APP_DIR/.venv/bin/python" "$APP_DIR/setup.py"; fi
chown root:root "$APP_DIR"
chmod 755 "$APP_DIR"
chown -R tutorbot:tutorbot "$APP_DIR/data"
chmod 700 "$APP_DIR/data" "$APP_DIR/data/uploads"
chown tutorbot:tutorbot "$APP_DIR/.env"
chmod 600 "$APP_DIR/.env"
install -m 0644 "$SRC/deploy/family-tutor.service" /etc/systemd/system/family-tutor.service
systemctl daemon-reload
systemctl enable family-tutor.service
cat <<EOF

Установка кода завершена, служба пока НЕ запущена.
1. sudo nano $APP_DIR/.env   # токен Telegram, BACKEND=codex или openai_api
2. Если codex: sudo npm install -g @openai/codex@latest
   затем sudo -u tutorbot -H codex login --device-auth
3. sudo systemctl start family-tutor
4. sudo journalctl -u family-tutor -n 80 --no-pager
5. sudo -u tutorbot -H $APP_DIR/.venv/bin/python $APP_DIR/doctor.py
ВНИМАНИЕ: Не запускайте второй экземпляр с тем же BotFather-токеном на Windows.
EOF
