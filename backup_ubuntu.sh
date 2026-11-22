#!/usr/bin/env bash
set -euo pipefail
# Root-run backup; sensitive archive stays on the VM, mode 0600.
APP_DIR=/opt/family-tutor
OUT_DIR=/var/backups/family-tutor
if [[ "${EUID}" -ne 0 ]]; then echo 'Use: sudo bash /opt/family-tutor/backup_ubuntu.sh'; exit 1; fi
mkdir -p "$OUT_DIR"
chmod 700 "$OUT_DIR"
STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
APP_DIR="$APP_DIR" OUT_DIR="$OUT_DIR" STAMP="$STAMP" python3 - <<'PY'
import os, sqlite3
from pathlib import Path
src=Path(os.environ['APP_DIR'])/'data/tutor.sqlite3'
out=Path(os.environ['OUT_DIR'])/('tutor_'+os.environ['STAMP']+'.sqlite3')
if src.exists():
    with sqlite3.connect(src) as db, sqlite3.connect(out) as backup:
        db.backup(backup)
PY
TAR="$OUT_DIR/family-tutor-$STAMP.tar.gz"
tar -czf "$TAR" -C "$APP_DIR" .env data/uploads -C "$OUT_DIR" "tutor_$STAMP.sqlite3" 2>/dev/null || {
  # New installation may have no DB yet. Still backup photos and config.
  tar -czf "$TAR" -C "$APP_DIR" .env data/uploads
}
chmod 600 "$TAR"
rm -f "$OUT_DIR/tutor_$STAMP.sqlite3"
echo "Backup (SECRET): $TAR"
