"""SQLite data access. All permissions are determined by immutable Telegram user IDs."""
from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone, timedelta
from pathlib import Path


def utcnow() -> str:
    return datetime.now(timezone.utc).isoformat(timespec='seconds')


class Storage:
    def __init__(self, db_file: str | Path):
        self.db_file = str(Path(db_file).resolve())
        Path(self.db_file).parent.mkdir(parents=True, exist_ok=True)
        self.init()

    @contextmanager
    def conn(self):
        con = sqlite3.connect(self.db_file, timeout=15)
        con.row_factory = sqlite3.Row
        con.execute('PRAGMA foreign_keys=ON')
        con.execute('PRAGMA busy_timeout=15000')
        try:
            yield con
            con.commit()
        except Exception:
            con.rollback()
            raise
        finally:
            con.close()

    def init(self):
        with self.conn() as c:
            c.executescript('''
                PRAGMA journal_mode=WAL;
                CREATE TABLE IF NOT EXISTS users (
                    user_id INTEGER PRIMARY KEY,
                    username TEXT NOT NULL DEFAULT '',
                    role TEXT NOT NULL CHECK(role IN ('parent','student','tester')),
                    test_mode TEXT NOT NULL DEFAULT 'student',
                    selected_task INTEGER,
                    created_at TEXT NOT NULL
                );
                CREATE UNIQUE INDEX IF NOT EXISTS one_person_per_role
                    ON users(role) WHERE role IN ('parent','student','tester');
                CREATE TABLE IF NOT EXISTS tasks (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    title TEXT NOT NULL,
                    parent_id INTEGER NOT NULL,
                    state TEXT NOT NULL CHECK(state IN ('draft','published','archived')),
                    created_at TEXT NOT NULL,
                    published_at TEXT
                );
                CREATE TABLE IF NOT EXISTS task_images (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    task_id INTEGER NOT NULL REFERENCES tasks(id) ON DELETE CASCADE,
                    path TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS progress (
                    task_id INTEGER NOT NULL REFERENCES tasks(id),
                    student_id INTEGER NOT NULL,
                    status TEXT NOT NULL DEFAULT 'working' CHECK(status IN ('working','pending','approved','retry')),
                    updated_at TEXT NOT NULL,
                    PRIMARY KEY(task_id, student_id)
                );
                CREATE TABLE IF NOT EXISTS events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    task_id INTEGER NOT NULL REFERENCES tasks(id),
                    student_id INTEGER NOT NULL,
                    source TEXT NOT NULL CHECK(source IN ('student','bot')),
                    kind TEXT NOT NULL CHECK(kind IN ('text','photo','notice')),
                    content TEXT NOT NULL DEFAULT '',
                    photo_path TEXT,
                    flag TEXT NOT NULL DEFAULT 'none',
                    flag_reason TEXT NOT NULL DEFAULT '',
                    mastery TEXT NOT NULL DEFAULT 'working',
                    parent_note TEXT NOT NULL DEFAULT '',
                    created_at TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS events_recent ON events(task_id,student_id,id);
            ''')
            columns = {r['name'] for r in c.execute('PRAGMA table_info(events)')}
            if 'parent_note' not in columns:
                c.execute("ALTER TABLE events ADD COLUMN parent_note TEXT NOT NULL DEFAULT ''")

    def register(self, user_id: int, username: str, role: str) -> tuple[bool, str]:
        if role not in ('parent', 'student', 'tester'):
            return False, 'Недопустимая роль.'
        with self.conn() as c:
            user = c.execute('SELECT role FROM users WHERE user_id=?', (user_id,)).fetchone()
            if user:
                if user['role'] == role:
                    c.execute('UPDATE users SET username=? WHERE user_id=?', (username, user_id))
                    return True, 'Эта роль уже закреплена за вашим Telegram ID.'
                return False, 'Этот Telegram ID уже привязан к другой роли.'
            if c.execute('SELECT 1 FROM users WHERE role=?', (role,)).fetchone():
                return False, f'Роль {role} уже занята другим Telegram ID. Обратитесь к администратору сервера.'
            c.execute('INSERT INTO users (user_id,username,role,created_at) VALUES (?,?,?,?)',
                      (user_id, username, role, utcnow()))
            return True, 'Роль закреплена за вашим числовым Telegram ID. Смена @ника ничего не изменит.'

    def user(self, user_id: int):
        with self.conn() as c:
            r = c.execute('SELECT * FROM users WHERE user_id=?', (user_id,)).fetchone()
            return dict(r) if r else None

    def set_mode(self, user_id: int, mode: str) -> bool:
        if mode not in ('parent', 'student'):
            return False
        with self.conn() as c:
            cur = c.execute('UPDATE users SET test_mode=? WHERE user_id=? AND role=?',
                            (mode, user_id, 'tester'))
            return cur.rowcount == 1

    def remember_username(self, user_id: int, username: str):
        with self.conn() as c:
            c.execute('UPDATE users SET username=? WHERE user_id=?', (username, user_id))

    def mode(self, user_id: int) -> str | None:
        u = self.user(user_id)
        if not u:
            return None
        return u['test_mode'] if u['role'] == 'tester' else u['role']

    def role_id(self, role: str):
        with self.conn() as c:
            r = c.execute('SELECT user_id FROM users WHERE role=?', (role,)).fetchone()
            return r['user_id'] if r else None

    def draft(self, user_id: int):
        with self.conn() as c:
            r = c.execute('SELECT * FROM tasks WHERE parent_id=? AND state=? ORDER BY id DESC LIMIT 1',
                          (user_id, 'draft')).fetchone()
            return dict(r) if r else None

    def new_draft(self, user_id: int, title: str) -> int:
        with self.conn() as c:
            c.execute('UPDATE tasks SET state=? WHERE parent_id=? AND state=?', ('archived', user_id, 'draft'))
            cur = c.execute('INSERT INTO tasks(title,parent_id,state,created_at) VALUES (?,?,?,?)',
                            (title[:3000], user_id, 'draft', utcnow()))
            return cur.lastrowid

    def append_draft_text(self, user_id: int, text: str) -> bool:
        d = self.draft(user_id)
        if not d:
            return False
        with self.conn() as c:
            c.execute('UPDATE tasks SET title=? WHERE id=?', ((d['title'] + '\n' + text)[:5000], d['id']))
        return True

    def add_draft_photo(self, user_id: int, path: str) -> bool:
        d = self.draft(user_id)
        if not d:
            return False
        with self.conn() as c:
            count = c.execute('SELECT COUNT(*) AS n FROM task_images WHERE task_id=?', (d['id'],)).fetchone()['n']
            if count >= 5:
                return False
            c.execute('INSERT INTO task_images(task_id,path) VALUES (?,?)', (d['id'], path))
            return True

    def publish(self, user_id: int) -> int | None:
        d = self.draft(user_id)
        if not d or not d['title'].strip():
            return None
        with self.conn() as c:
            c.execute('UPDATE tasks SET state=?, published_at=? WHERE id=?', ('published', utcnow(), d['id']))
        return d['id']

    def task(self, task_id: int):
        with self.conn() as c:
            r = c.execute('SELECT * FROM tasks WHERE id=?', (task_id,)).fetchone()
            return dict(r) if r else None

    def task_images(self, task_id: int) -> list[str]:
        with self.conn() as c:
            return [r['path'] for r in c.execute('SELECT path FROM task_images WHERE task_id=?', (task_id,))]

    def tasks(self, include_drafts: bool = False) -> list[dict]:
        with self.conn() as c:
            sql = 'SELECT * FROM tasks WHERE state IN (\'published\',\'draft\')' if include_drafts else "SELECT * FROM tasks WHERE state='published'"
            return [dict(r) for r in c.execute(sql + ' ORDER BY id DESC LIMIT 30')]

    def select(self, student_id: int, task_id: int) -> bool:
        t = self.task(task_id)
        if not t or t['state'] != 'published':
            return False
        with self.conn() as c:
            c.execute('UPDATE users SET selected_task=? WHERE user_id=?', (task_id, student_id))
            c.execute('INSERT OR IGNORE INTO progress(task_id,student_id,status,updated_at) VALUES (?,?,?,?)',
                      (task_id, student_id, 'working', utcnow()))
        return True

    def selected(self, student_id: int):
        u = self.user(student_id)
        return self.task(u['selected_task']) if u and u['selected_task'] else None

    def log(self, task_id: int, student_id: int, source: str, kind: str, content: str = '',
            photo_path: str | None = None, flag: str = 'none', flag_reason: str = '',
            mastery: str = 'working', parent_note: str = ''):
        with self.conn() as c:
            c.execute('''INSERT INTO events(task_id,student_id,source,kind,content,photo_path,flag,flag_reason,mastery,parent_note,created_at)
                         VALUES (?,?,?,?,?,?,?,?,?,?,?)''',
                      (task_id, student_id, source, kind, content[:3000], photo_path,
                       flag, flag_reason[:250], mastery, parent_note[:350], utcnow()))

    def recent(self, task_id: int, student_id: int, limit: int = 10):
        with self.conn() as c:
            rows = c.execute('''SELECT source,kind,content,flag,mastery FROM events
                                WHERE task_id=? AND student_id=? ORDER BY id DESC LIMIT ?''',
                             (task_id, student_id, limit)).fetchall()
            return [dict(r) for r in reversed(rows)]

    def summary(self, task_id: int, student_id: int):
        with self.conn() as c:
            p = c.execute('SELECT status,updated_at FROM progress WHERE task_id=? AND student_id=?',
                          (task_id, student_id)).fetchone()
            counts = c.execute('''SELECT COUNT(*) AS n, SUM(CASE WHEN source='student' AND kind='text' THEN 1 ELSE 0 END) AS texts,
                                SUM(CASE WHEN source='student' AND kind='photo' THEN 1 ELSE 0 END) AS photos,
                                SUM(CASE WHEN flag!='none' THEN 1 ELSE 0 END) AS flags
                                FROM events WHERE task_id=? AND student_id=?''', (task_id, student_id)).fetchone()
            flagged = [dict(r) for r in c.execute('''SELECT flag,flag_reason FROM events
                 WHERE task_id=? AND student_id=? AND flag!='none' ORDER BY id DESC LIMIT 3''', (task_id,student_id))]
            parent_notes = [r['parent_note'] for r in c.execute('''SELECT parent_note FROM events WHERE task_id=? AND student_id=?
                     AND source='bot' AND parent_note!='' ORDER BY id DESC LIMIT 3''', (task_id,student_id))]
            latest = c.execute('''SELECT mastery FROM events WHERE task_id=? AND student_id=?
                        AND source='bot' ORDER BY id DESC LIMIT 1''', (task_id,student_id)).fetchone()
        return {'status': p['status'] if p else 'not_started',
                'text_count': counts['texts'] or 0, 'photo_count': counts['photos'] or 0,
                'flag_count': counts['flags'] or 0, 'flags': flagged,
                'mastery': latest['mastery'] if latest else 'not_started',
                'parent_notes': parent_notes}

    def set_status(self, task_id: int, student_id: int, status: str) -> bool:
        if status not in ('working','pending','approved','retry'):
            return False
        if not self.task(task_id):
            return False
        with self.conn() as c:
            c.execute('INSERT INTO progress(task_id,student_id,status,updated_at) VALUES (?,?,?,?) '
                      'ON CONFLICT(task_id,student_id) DO UPDATE SET status=excluded.status,updated_at=excluded.updated_at',
                      (task_id,student_id,status,utcnow()))
        return True

    def recent_photos(self, task_id: int, student_id: int, count=3) -> list[str]:
        with self.conn() as c:
            return [r['photo_path'] for r in c.execute('''SELECT photo_path FROM events
                WHERE task_id=? AND student_id=? AND source='student' AND photo_path IS NOT NULL
                ORDER BY id DESC LIMIT ?''', (task_id, student_id, count))]

    def purge_old_events(self, days: int = 30) -> tuple[int,list[str]]:
        cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat(timespec='seconds')
        with self.conn() as c:
            paths = [r['photo_path'] for r in c.execute(
                'SELECT photo_path FROM events WHERE created_at<? AND photo_path IS NOT NULL',(cutoff,))]
            cur = c.execute('DELETE FROM events WHERE created_at<?', (cutoff,))
            return cur.rowcount, paths

    def delete_task(self, task_id: int) -> list[str] | None:
        if not self.task(task_id):
            return None
        with self.conn() as c:
            paths = [r['path'] for r in c.execute('SELECT path FROM task_images WHERE task_id=?', (task_id,))]
            paths += [r['photo_path'] for r in c.execute(
                'SELECT photo_path FROM events WHERE task_id=? AND photo_path IS NOT NULL', (task_id,))]
            c.execute('UPDATE users SET selected_task=NULL WHERE selected_task=?', (task_id,))
            c.execute('DELETE FROM events WHERE task_id=?', (task_id,))
            c.execute('DELETE FROM progress WHERE task_id=?', (task_id,))
            c.execute('DELETE FROM task_images WHERE task_id=?', (task_id,))
            c.execute('DELETE FROM tasks WHERE id=?', (task_id,))
            return paths

    def daily_tutor_turns(self, student_id: int) -> int:
        midnight = datetime.now(timezone.utc).strftime('%Y-%m-%dT00:00:00+00:00')
        with self.conn() as c:
            return c.execute('''SELECT COUNT(*) AS n FROM events
                      WHERE student_id=? AND source='bot' AND created_at>=?''',
                      (student_id,midnight)).fetchone()['n']
