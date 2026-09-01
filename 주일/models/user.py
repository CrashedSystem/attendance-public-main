# -*- coding: utf-8 -*-
"""사용자(users / users_archive) 관련 DB 쿼리.
"""
import datetime
import re

from models.database import db
from constants import USER_FIELDS


def migrate_chaplain(conn, table):
    """users/users_archive에 is_chaplain 컬럼을 추가하고, note의 '군종' 표시를 컬럼으로 이전한다.

    table은 'users' / 'users_archive' 만 허용. 식별자 인젝션 방지를 위해 화이트리스트 검증.
    """
    if table not in ('users', 'users_archive'):
        raise ValueError('unsupported table: %r' % table)
    cols = [r[1] for r in conn.execute('PRAGMA table_info(%s)' % table)]
    if 'is_chaplain' not in cols:
        conn.execute('ALTER TABLE %s ADD COLUMN is_chaplain INTEGER DEFAULT 0' % table)
    rows = conn.execute("SELECT id, note FROM %s WHERE note LIKE '%%군종%%'" % table).fetchall()
    for r in rows:
        note = re.sub(r'군종병|\s*군종\s*', ' ', r['note'] or '')
        note = re.sub(r'[ \t,;·/.]+', ' ', note).strip(' ,;·/.')
        conn.execute('UPDATE %s SET is_chaplain=1, note=? WHERE id=?' % table, (note, r['id']))


def ensure_users_archive(conn):
    """users_archive 테이블을 생성하고 스키마를 최신화한다."""
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
    migrate_chaplain(conn, 'users_archive')


def archive_user(conn, r):
    """users 행을 users_archive로 백업한다. (이미 아카이브된 id면 기존 기록 유지)"""
    ensure_users_archive(conn)
    conn.execute(
        'INSERT OR IGNORE INTO users_archive '
        '(id, name, baptism, affiliation, team, phone, discharge_date, birthday, note, prev_church, is_chaplain, archived_at) '
        'VALUES (?,?,?,?,?,?,?,?,?,?,?,?)',
        (r['id'], r['name'], r['baptism'], r['affiliation'], r['team'],
         r['phone'], r['discharge_date'], r['birthday'], r['note'],
         (r['prev_church'] if 'prev_church' in r.keys() else '') or '',
         (r['is_chaplain'] if 'is_chaplain' in r.keys() else 0) or 0,
         datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')))


def prune_expired_users(conn=None):
    """전역일이 지난 사용자를 DB에서 제거한다. (전역일 당일까지는 유지)

    삭제 전에 users_archive 테이블로 원본을 백업한다. 제거된 인원 수를 반환한다.
    매 호출마다 전체 실행하지 않도록 설정(settings 'last_prune')으로 1시간 이내 재실행을 건너뛴다.
    """
    import datetime
    own = conn is None
    if own:
        conn = db()
    last = None
    now = datetime.datetime.now()
    try:
        last = conn.execute(
            "SELECT value FROM settings WHERE key='last_prune'").fetchone()
        try:
            last_dt = datetime.datetime.strptime(last['value'], '%Y-%m-%d %H:%M:%S') if last else None
        except (ValueError, TypeError):
            last_dt = None
        if last_dt is not None and (now - last_dt).total_seconds() < 3600:
            return 0
        today = datetime.date.today().isoformat()
        ensure_users_archive(conn)
        expired = conn.execute(
            "SELECT * FROM users WHERE discharge_date IS NOT NULL AND discharge_date != '' AND discharge_date < ?",
            (today,)).fetchall()
        for r in expired:
            archive_user(conn, r)
        cur = conn.execute(
            "DELETE FROM users WHERE discharge_date IS NOT NULL AND discharge_date != '' AND discharge_date < ?",
            (today,))
        removed = cur.rowcount
        conn.execute(
            "INSERT INTO settings (key, value) VALUES ('last_prune', ?) "
            "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
            (now.strftime('%Y-%m-%d %H:%M:%S'),))
        conn.commit()
        return removed
    finally:
        if own:
            conn.close()


def get_user(conn, uid):
    """id로 사용자 한 명을 조회한다."""
    return conn.execute('SELECT * FROM users WHERE id=?', (uid,)).fetchone()


def find_users_by_name(conn, name):
    """이름으로 사용자 후보 목록을 조회한다. (동명이인 판별용, 소속·id 정렬)"""
    return [dict(r) for r in conn.execute(
        'SELECT id, name, affiliation, team, birthday, note FROM users WHERE name=? ORDER BY affiliation, id',
        (name,)).fetchall()]

def get_chaplains(conn):
    """군종병(is_chaplain=1) 사용자 목록을 소속·id 정렬로 조회한다."""
    return conn.execute(
        'SELECT id, name, affiliation, team FROM users WHERE is_chaplain=1 ORDER BY affiliation, id').fetchall()


def get_user_by_id_with_archive(conn, uid):
    """users_archive에서 id로 사용자 복원 대상 행을 조회한다."""
    return conn.execute('SELECT * FROM users_archive WHERE id=?', (uid,)).fetchone()


def get_all_users(conn=None):
    """모든 사용자를 정렬 없이 원본 순서로 조회한다. (SELECT * FROM users ORDER BY id)"""
    own = conn is None
    if own:
        conn = db()
    try:
        rows = conn.execute('SELECT * FROM users ORDER BY id').fetchall()
    finally:
        if own:
            conn.close()
    return [dict(r) for r in rows]


def search_all_users(conn):
    """검색용 사용자 목록(부분 컬럼)을 조회한다."""
    return [dict(r) for r in conn.execute(
        'SELECT id, name, affiliation, team, phone, birthday, note, prev_church FROM users')]


def create_user(conn, data):
    """사용자를 생성하고 새 id를 반환한다."""
    name = (data.get('name') or '').strip()
    cur = conn.execute(
        'INSERT INTO users (name, baptism, affiliation, team, phone, discharge_date, birthday, note, is_chaplain) '
        'VALUES (?,?,?,?,?,?,?,?,?)',
        (name, data.get('baptism', ''), data.get('affiliation', ''), data.get('team', ''),
         data.get('phone', ''), data.get('discharge_date', ''), data.get('birthday', ''),
         data.get('note', ''), data.get('is_chaplain', 0)))
    return cur.lastrowid


def update_user(conn, uid, data):
    """사용자 정보를 USER_FIELDS 기준으로 갱신한다."""
    sets = ', '.join('%s=?' % f for f in USER_FIELDS)
    vals = [data.get(f, '') for f in USER_FIELDS]
    conn.execute('UPDATE users SET %s WHERE id=?' % sets, vals + [uid])


def delete_user(conn, uid):
    """사용자를 명단에서 삭제한다."""
    conn.execute('DELETE FROM users WHERE id=?', (uid,))


def get_archived_users(conn=None):
    """아카이브된 사용자 목록 조회."""
    own = conn is None
    if own:
        conn = db()
    try:
        rows = conn.execute('SELECT * FROM users_archive ORDER BY archived_at DESC, id').fetchall()
    finally:
        if own:
            conn.close()
    return [dict(r) for r in rows]


def restore_user(conn, uid):
    """아카이브된 사용자를 명단으로 복원한다. 복원된 행을 반환한다."""
    row = get_user_by_id_with_archive(conn, uid)
    if not row:
        return None
    conn.execute('DELETE FROM users_archive WHERE id=?', (uid,))
    conn.execute(
        'INSERT INTO users (id, name, baptism, affiliation, team, phone, discharge_date, birthday, note, prev_church, is_chaplain) '
        'VALUES (?,?,?,?,?,?,?,?,?,?,?)',
        (row['id'], row['name'], row['baptism'], row['affiliation'], row['team'],
         row['phone'], row['discharge_date'], row['birthday'], row['note'], row['prev_church'] or '',
         (row['is_chaplain'] if 'is_chaplain' in row.keys() else 0) or 0))
    conn.commit()
    return row
