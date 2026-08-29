# -*- coding: utf-8 -*-
"""데이터베이스 연결 및 스키마 초기화.

- db(): SQLite 연결 (Row factory 적용)
- init_db(): 초기 스키마/마이그레이션 수행
"""
import sqlite3

from config import DB_PATH
from constants import MODE_SUNDAY


def db():
    """SQLite 연결을 반환한다. Row factory가 적용되며, 호출자가 close 해야 한다.
    """
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    """초기 스키마를 생성하고 기존 DB를 최신 스키마로 마이그레이션한다.

    - attendance / settings / absences 테이블 생성
    - users 테이블 컬럼 마이그레이션(baptism, prev_church, is_chaplain)
    - current_mode 기본값 부여
    - 전역자 정리(prune) 및 새신우 태그 만료 처리
    """
    from models.user import prune_expired_users  # 순환 참조 방지
    from web_report import expire_newbie_notes

    conn = db()
    conn.execute('''CREATE TABLE IF NOT EXISTS attendance (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        name TEXT NOT NULL,
        affiliation TEXT,
        check_date TEXT NOT NULL,
        check_time TEXT NOT NULL,
        mode TEXT DEFAULT 'sunday',
        env TEXT DEFAULT 'commercial'
    )''')
    cols = [r[1] for r in conn.execute('PRAGMA table_info(attendance)')]
    if 'mode' not in cols:
        conn.execute("ALTER TABLE attendance ADD COLUMN mode TEXT DEFAULT 'sunday'")
    if 'env' not in cols:
        conn.execute("ALTER TABLE attendance ADD COLUMN env TEXT DEFAULT 'commercial'")
    conn.execute('''CREATE TABLE IF NOT EXISTS settings (
        key TEXT PRIMARY KEY,
        value TEXT
    )''')
    conn.execute("INSERT OR IGNORE INTO settings (key, value) VALUES ('current_mode', ?)",
                 (MODE_SUNDAY,))
    conn.execute('''CREATE TABLE IF NOT EXISTS absences (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        check_date TEXT NOT NULL,
        reason TEXT,
        mode TEXT DEFAULT 'wednesday',
        env TEXT DEFAULT 'commercial',
        created_at TEXT,
        UNIQUE (user_id, check_date, mode, env)
    )''')
    cols = [r[1] for r in conn.execute('PRAGMA table_info(users)')]
    if 'baptism' not in cols:
        conn.execute('ALTER TABLE users ADD COLUMN baptism TEXT')
    if 'prev_church' not in cols:
        conn.execute("ALTER TABLE users ADD COLUMN prev_church TEXT DEFAULT ''")
        conn.execute("UPDATE users SET prev_church='' WHERE prev_church IS NULL")
    conn.execute('''CREATE TABLE IF NOT EXISTS users_archive (
        id INTEGER PRIMARY KEY,
        name TEXT, baptism TEXT, affiliation TEXT, team TEXT,
        phone TEXT, discharge_date TEXT, birthday TEXT, note TEXT,
        prev_church TEXT,
        archived_at TEXT
    )''')
    cols = [r[1] for r in conn.execute('PRAGMA table_info(users_archive)')]
    if 'prev_church' not in cols:
        conn.execute("ALTER TABLE users_archive ADD COLUMN prev_church TEXT DEFAULT ''")
    if 'is_chaplain' not in cols:
        conn.execute("ALTER TABLE users_archive ADD COLUMN is_chaplain INTEGER DEFAULT 0")

    from models.user import migrate_chaplain
    migrate_chaplain(conn, 'users')
    migrate_chaplain(conn, 'users_archive')
    conn.commit()
    prune_expired_users(conn)
    conn.close()
    try:
        expire_newbie_notes()
    except Exception:
        pass
