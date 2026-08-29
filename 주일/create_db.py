# -*- coding: utf-8 -*-
import os
import re
import sqlite3
import sys

from dummy_data import DUMMY_ROWS, ARCHIVE_ROWS, ABSENCE_SAMPLE, build_attendance

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, sys.argv[1] if len(sys.argv) > 1 else '군종.db')


def norm_date(s):
    s = (s or '').strip().replace(' ', '').replace(',', '.')
    if not s:
        return ''
    m = re.match(r'^(\d{4})\.(\d{1,2})\.(\d{1,2})$', s)
    if m:
        y, mo, d = m.groups()
        return '%s-%02d-%02d' % (y, int(mo), int(d))
    m = re.match(r'^(\d{2})\.(\d{1,2})\.(\d{1,2})$', s)
    if m:
        y, mo, d = m.groups()
        year = '20' + y if int(y) < 50 else '19' + y
        return '%s-%02d-%02d' % (year, int(mo), int(d))
    return (s or '').strip()


def norm_birthday(s):
    s = (s or '').strip()
    if not s:
        return ''
    if re.match(r'^\d{4}$', s):
        return s
    m = re.match(r'^(\d{4})[-.](\d{1,2})[-.](\d{1,2})$', s)
    if m:
        return '%02d%02d' % (int(m.group(2)), int(m.group(3)))
    m = re.match(r'^(\d{1,2})\s*월\s*(\d{1,2})\s*일?$', s)
    if m:
        return '%02d%02d' % (int(m.group(1)), int(m.group(2)))
    return s


def _add_column(conn, table, column, decl):
    cols = [r[1] for r in conn.execute('PRAGMA table_info("%s")' % table)]
    if column not in cols:
        conn.execute('ALTER TABLE "%s" ADD COLUMN %s %s' % (table, column, decl))


def ensure_schema(conn):
    conn.execute('''CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        baptism TEXT,
        affiliation TEXT,
        team TEXT,
        phone TEXT,
        discharge_date TEXT,
        birthday TEXT,
        note TEXT,
        prev_church TEXT DEFAULT '',
        is_chaplain INTEGER DEFAULT 0
    )''')
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
    conn.execute('''CREATE TABLE IF NOT EXISTS users_archive (
        id INTEGER PRIMARY KEY,
        name TEXT, baptism TEXT, affiliation TEXT, team TEXT,
        phone TEXT, discharge_date TEXT, birthday TEXT, note TEXT,
        archived_at TEXT,
        prev_church TEXT DEFAULT '',
        is_chaplain INTEGER DEFAULT 0
    )''')
    conn.execute('''CREATE TABLE IF NOT EXISTS settings (
        key TEXT PRIMARY KEY,
        value TEXT
    )''')
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
    _add_column(conn, 'users', 'prev_church', "TEXT DEFAULT ''")
    _add_column(conn, 'users', 'is_chaplain', 'INTEGER DEFAULT 0')
    _add_column(conn, 'users_archive', 'prev_church', "TEXT DEFAULT ''")
    _add_column(conn, 'users_archive', 'is_chaplain', 'INTEGER DEFAULT 0')
    _add_column(conn, 'attendance', 'mode', "TEXT DEFAULT 'sunday'")
    _add_column(conn, 'attendance', 'env', "TEXT DEFAULT 'commercial'")


def seed(conn, rows, archive_rows, absences):
    conn.execute('DELETE FROM users')
    conn.execute('DELETE FROM users_archive')
    conn.execute('DELETE FROM attendance')
    conn.execute('DELETE FROM absences')
    for seq in ('users', 'attendance', 'users_archive', 'absences'):
        conn.execute('DELETE FROM sqlite_sequence WHERE name=?', (seq,))

    uid_by_name = {}
    for row in rows:
        name, team, affiliation, phone, discharge, birthday, baptism, note = row
        is_chaplain = 1 if '군종' in (note or '') else 0
        note = re.sub(r'군종병|\s*군종\s*', ' ', note or '')
        note = re.sub(r'[ \t,;·/.]+', ' ', note).strip(' ,;·/.')
        cur = conn.execute(
            'INSERT INTO users (name, baptism, affiliation, team, phone, discharge_date, birthday, note, is_chaplain) '
            'VALUES (?,?,?,?,?,?,?,?,?)',
            (name, baptism, affiliation, team, phone, norm_date(discharge), norm_birthday(birthday), note, is_chaplain))
        uid_by_name[name] = cur.lastrowid

    for name, baptism, affiliation, team, phone, discharge, birthday, note in archive_rows:
        conn.execute(
            'INSERT INTO users_archive (name, baptism, affiliation, team, phone, discharge_date, birthday, note, is_chaplain) '
            'VALUES (?,?,?,?,?,?,?,?,?)',
            (name, baptism, affiliation, team, phone, norm_date(discharge), norm_birthday(birthday), note, 0))

    for name, affiliation, date, time, mode in build_attendance(rows):
        conn.execute(
            'INSERT INTO attendance (user_id, name, affiliation, check_date, check_time, mode) '
            'VALUES (?,?,?,?,?,?)',
            (uid_by_name[name], name, affiliation, date, time, mode))

    for uid, date, reason in absences:
        conn.execute(
            'INSERT INTO absences (user_id, check_date, reason, mode, env, created_at) '
            'VALUES (?,?,?,?,?,?)',
            (uid, date, reason, 'wednesday', 'commercial', '2026-08-26 09:00:00'))

    conn.commit()


def main():
    conn = sqlite3.connect(DB_PATH)
    try:
        ensure_schema(conn)
        seed(conn, DUMMY_ROWS, ARCHIVE_ROWS, ABSENCE_SAMPLE)
        counts = {
            t: conn.execute('SELECT COUNT(*) FROM "%s"' % t).fetchone()[0]
            for t in ('users', 'attendance', 'users_archive', 'absences')
        }
        print(DB_PATH, counts)
    finally:
        conn.close()


if __name__ == '__main__':
    main()