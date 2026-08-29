import os
import re
import sys
import json
import socket
import struct
import sqlite3
import datetime
import threading
import time

from flask import Flask, request, jsonify, send_from_directory

from web_report import refresh_web_report, expire_newbie_notes, render_reports_to_png

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, '군종.db')
ADMIN_PIN = '1717'

# 서버 실행 모드: 'commercial'(상업/운영) | 'dev'(개발/테스트)
# 환경변수 SERVER_ENV 또는 실행인자(dev/commercial)로 결정, 기본 commercial
SERVER_ENV = os.environ.get('SERVER_ENV', 'commercial')
for _a in sys.argv[1:]:
    if _a in ('dev', 'commercial'):
        SERVER_ENV = _a

app = Flask(__name__, static_folder='static', static_url_path='/static')

USER_FIELDS = ['name', 'baptism', 'affiliation', 'team', 'phone', 'discharge_date', 'birthday', 'note', 'prev_church', 'is_chaplain']


def db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def _migrate_chaplain(conn, table):
    """users/users_archive에 is_chaplain 컬럼을 추가하고, note의 '군종' 표시를 컬럼으로 이전한다."""
    cols = [r[1] for r in conn.execute('PRAGMA table_info(%s)' % table)]
    if 'is_chaplain' not in cols:
        conn.execute('ALTER TABLE %s ADD COLUMN is_chaplain INTEGER DEFAULT 0' % table)
    rows = conn.execute("SELECT id, note FROM %s WHERE note LIKE '%%군종%%'" % table).fetchall()
    for r in rows:
        note = re.sub(r'군종병|\s*군종\s*', ' ', r['note'] or '')
        note = re.sub(r'[ \t,;·/.]+', ' ', note).strip(' ,;·/.')
        conn.execute('UPDATE %s SET is_chaplain=1, note=? WHERE id=?' % table, (note, r['id']))


def _ensure_users_archive(conn):
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
    _migrate_chaplain(conn, 'users_archive')


def _archive_user(conn, r):
    """users 행을 users_archive로 백업한다."""
    _ensure_users_archive(conn)
    conn.execute(
        'INSERT OR REPLACE INTO users_archive '
        '(id, name, baptism, affiliation, team, phone, discharge_date, birthday, note, prev_church, is_chaplain, archived_at) '
        'VALUES (?,?,?,?,?,?,?,?,?,?,?,?)',
        (r['id'], r['name'], r['baptism'], r['affiliation'], r['team'],
         r['phone'], r['discharge_date'], r['birthday'], r['note'],
         (r['prev_church'] if 'prev_church' in r.keys() else '') or '',
         (r['is_chaplain'] if 'is_chaplain' in r.keys() else 0) or 0,
         datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')))


def prune_expired_users(conn=None):
    """전역일이 지난 사용자를 DB에서 제거한다. (전역일 당일까지는 유지)

    삭제 전에 users_archive 테이블로 원본을 백업한다.
    """
    own = conn is None
    if own:
        conn = db()
    today = datetime.date.today().isoformat()
    _ensure_users_archive(conn)
    expired = conn.execute(
        "SELECT * FROM users WHERE discharge_date IS NOT NULL AND discharge_date != '' AND discharge_date < ?",
        (today,)).fetchall()
    for r in expired:
        _archive_user(conn, r)
    cur = conn.execute(
        "DELETE FROM users WHERE discharge_date IS NOT NULL AND discharge_date != '' AND discharge_date < ?",
        (today,))
    removed = cur.rowcount
    conn.commit()
    if own:
        conn.close()
    return removed


def _normalize_newbie_note(note):
    """비고에 '새신우'가 있으면 등록 날짜를 자동 부여한다. -> 새신우(YYYY-MM-DD)

    이미 날짜가 붙은 태그는 그대로 둔다. (web_report.expire_newbie_notes가 30일 후 자동 삭제)
    """
    s = (note or '').strip()
    if not s:
        return s
    return re.sub(r'새신우(?!\(\d{4}-\d{2}-\d{2}\))',
                  '새신우(%s)' % datetime.date.today().isoformat(), s)


def norm_birthday(b):
    """생일을 네 자리 숫자(MMDD)로 통일한다. -> '0102' (1월 2일)

    지원 입력: 'MM월 DD일', 'M월 D일', 'YYYY-MM-DD', 'YYYY.MM.DD', 'MMDD'
    변환 실패 시 원본을 그대로 반환한다.
    """
    s = (b or '').strip()
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


def init_db():
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
    conn.execute("INSERT OR IGNORE INTO settings (key, value) VALUES ('current_mode', 'sunday')")
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
    _migrate_chaplain(conn, 'users')
    conn.commit()
    prune_expired_users(conn)
    conn.close()
    try:
        expire_newbie_notes()
    except Exception:
        pass


def get_mode(conn=None):
    own = conn is None
    if own:
        conn = db()
    row = conn.execute("SELECT value FROM settings WHERE key='current_mode'").fetchone()
    mode = row['value'] if row else 'sunday'
    if own:
        conn.close()
    return mode


def set_mode(conn, mode):
    conn.execute("INSERT OR REPLACE INTO settings (key, value) VALUES ('current_mode', ?)", (mode,))
    conn.commit()


@app.route('/')
def index():
    return send_from_directory('static', 'index.html')


@app.route('/api/mode')
def api_get_mode():
    conn = db()
    mode = get_mode(conn)
    conn.close()
    return jsonify({'mode': mode, 'env': SERVER_ENV})


@app.route('/api/admin/mode', methods=['POST'])
def api_set_mode():
    data = request.get_json(silent=True) or {}
    mode = data.get('mode') or ''
    if mode not in ('sunday', 'wednesday'):
        return jsonify({'ok': False, 'msg': '모드가 올바르지 않습니다.'}), 400
    conn = db()
    set_mode(conn, mode)
    conn.close()
    try:
        refresh_web_report(mode, env=SERVER_ENV)
    except Exception as e:
        pass
    return jsonify({'ok': True, 'mode': mode})


@app.route('/api/users/search')
def search_users():
    q = (request.args.get('q', '') or '').strip()
    mode = request.args.get('mode', '') or ''
    conn = db()
    prune_expired_users(conn)
    if mode not in ('sunday', 'wednesday'):
        mode = get_mode(conn)
    users = [dict(r) for r in conn.execute(
        'SELECT id, name, affiliation, team, phone, birthday, note, prev_church FROM users')]
    conn.close()

    if not q:
        users.sort(key=lambda u: (u['affiliation'] or '', u['id']))
        return jsonify(users)

    # 1) 숫자 검색: id 또는 이름에 포함
    if q.isdigit():
        results = [u for u in users if str(u['id']) == q or q in (u['name'] or '')]
        return jsonify(results)

    # 2) 초성 검색: 모든 문자(공백 제외)가 한글 초성(ㄱ~ㅎ)이면 이름·소속·팀의 초성으로 매칭
    if _is_chosung_query(q):
        qc = _to_chosung(q).replace(' ', '')
        scored = []
        for u in users:
            name_c = _to_chosung(u['name'] or '')
            if qc in name_c:
                scored.append((1, name_c.index(qc), u))
                continue
            aff_c = _to_chosung(u['affiliation'] or '')
            if qc in aff_c:
                scored.append((2, aff_c.index(qc), u))
                continue
            team_c = _to_chosung(u['team'] or '')
            if qc in team_c:
                scored.append((3, team_c.index(qc), u))
        scored.sort(key=lambda t: (t[0], t[1], t[2]['id']))
        return jsonify([u for _, _, u in scored])

    # 3) 일반 텍스트 검색: 이름 우선(정확일치·접두·포함), 이어서 소속·팀
    scored = []
    for u in users:
        name = u['name'] or ''
        aff = u['affiliation'] or ''
        team = u['team'] or ''
        rank = None
        if name == q:
            rank = (0, 0, 0)          # 정확 일치
        elif name.startswith(q):
            rank = (0, 1, len(name))  # 이름 접두
        elif q in name:
            rank = (0, 2, name.index(q))  # 이름 포함
        elif q in aff:
            rank = (1, 0, 0)
        elif q in team:
            rank = (2, 0, 0)
        if rank is not None:
            scored.append((rank, u))
    scored.sort(key=lambda t: (t[0][0], t[0][1], t[0][2], t[1]['id']))
    return jsonify([u for _, u in scored])


CHOSUNG = 'ㄱㄲㄴㄷㄸㄹㅁㅂㅃㅅㅆㅇㅈㅉㅊㅋㅌㅍㅎ'
CHOSUNG_SET = set(CHOSUNG)


def _to_chosung(s):
    """문자열의 한글 음절을 초성으로 치환한 문자열을 반환한다."""
    out = []
    for ch in s:
        o = ord(ch)
        if 0xAC00 <= o <= 0xD7A3:
            out.append(CHOSUNG[(o - 0xAC00) // 588])
        else:
            out.append(ch)
    return ''.join(out)


def _is_chosung_query(q):
    """공백 제외 전 문자가 한글 초성(ㄱ~ㅎ)이면 True. (초성 검색 판별)"""
    return all(ch in CHOSUNG_SET or ch.isspace() for ch in q)


@app.route('/api/checkin', methods=['POST'])
def checkin():
    data = request.get_json(silent=True) or {}
    uid = data.get('user_id')
    if not uid:
        return jsonify({'ok': False, 'msg': '사용자를 선택해주세요.'}), 400
    conn = db()
    user = conn.execute('SELECT * FROM users WHERE id=?', (uid,)).fetchone()
    if not user:
        conn.close()
        return jsonify({'ok': False, 'msg': '존재하지 않는 사용자입니다.'}), 404
    today = datetime.date.today().isoformat()
    now = datetime.datetime.now().strftime('%H:%M:%S')
    mode = get_mode(conn)
    dup = conn.execute('SELECT * FROM attendance WHERE user_id=? AND check_date=? AND mode=? AND env=?',
                       (uid, today, mode, SERVER_ENV)).fetchone()
    if dup:
        conn.close()
        return jsonify({'ok': False, 'msg': '%s님은 이미 출석하셨습니다. (%s)' % (user['name'], dup['check_time'])})
    conn.execute(
        'INSERT INTO attendance (user_id, name, affiliation, check_date, check_time, mode, env) VALUES (?,?,?,?,?,?,?)',
        (uid, user['name'], user['affiliation'], today, now, mode, SERVER_ENV))
    weeks = conn.execute(
        'SELECT COUNT(DISTINCT check_date) FROM attendance WHERE user_id=? AND mode=? AND check_date<=? AND env=?',
        (uid, mode, today, SERVER_ENV)).fetchone()[0]
    conn.commit()
    conn.close()
    try:
        refresh_web_report(mode, env=SERVER_ENV)
    except Exception as e:
        pass
    return jsonify({'ok': True, 'name': user['name'], 'affiliation': user['affiliation'],
                    'time': now, 'weeks': weeks})


@app.route('/api/attendance/today')
def attendance_today():
    conn = db()
    today = datetime.date.today().isoformat()
    rows = conn.execute('SELECT * FROM attendance WHERE check_date=? AND env=? ORDER BY check_time',
                        (today, SERVER_ENV)).fetchall()
    conn.close()
    return jsonify([dict(r) for r in rows])


@app.route('/api/attendance/history')
def attendance_history():
    conn = db()
    rows = conn.execute('SELECT * FROM attendance WHERE env=? ORDER BY check_date DESC, check_time DESC LIMIT 500',
                        (SERVER_ENV,)).fetchall()
    conn.close()
    return jsonify([dict(r) for r in rows])


def _mark_user_attendance(conn, uid, name, today, now, mode):
    """단일 사용자 출석 기록. 중복/존재여부를 검사한다. (commit은 호출자 책임)"""
    user = conn.execute('SELECT * FROM users WHERE id=?', (uid,)).fetchone()
    if not user:
        return {'name': name, 'user_id': uid, 'ok': False, 'msg': '사용자 없음'}
    dup = conn.execute('SELECT * FROM attendance WHERE user_id=? AND check_date=? AND mode=? AND env=?',
                       (uid, today, mode, SERVER_ENV)).fetchone()
    if dup:
        return {'name': user['name'], 'user_id': uid, 'ok': False, 'msg': '이미 출석'}
    conn.execute(
        'INSERT INTO attendance (user_id, name, affiliation, check_date, check_time, mode, env) VALUES (?,?,?,?,?,?,?)',
        (uid, user['name'], user['affiliation'], today, now, mode, SERVER_ENV))
    return {'name': user['name'], 'user_id': uid, 'ok': True, 'msg': '완료'}


def _finalize_bulk(mode):
    try:
        refresh_web_report(mode, env=SERVER_ENV)
    except Exception:
        pass


@app.route('/api/attendance/bulk', methods=['POST'])
def bulk_checkin():
    """이름 목록을 받아 일괄 출석 처리한다.

    1차 호출(names만): 이름이 유일하면 바로 출석, 중복(동명이인)이면 후보 목록을 반환해
    사용자가 직접 올바른 사람을 선택하게 한다. 이름이 없으면 미발견으로 표시.
    2차 호출(names + choices{인덱스: user_id}): 선택된 동명이인만 출석 처리한다.
    """
    data = request.get_json(silent=True) or {}
    raw_names = data.get('names') or []
    choices = data.get('choices') or {}
    names = []
    for n in raw_names:
        n = (n or '').strip()
        if n:
            names.append(n)
    conn = db()
    mode = get_mode(conn)
    today = datetime.date.today().isoformat()
    now = datetime.datetime.now().strftime('%H:%M:%S')

    # 2차: 사용자가 선택한 동명이인 출석 처리
    if choices:
        marked = []
        for idx_str, uid in choices.items():
            try:
                idx = int(idx_str)
                uid = int(uid)
            except (TypeError, ValueError):
                continue
            if 0 <= idx < len(names):
                marked.append(_mark_user_attendance(conn, uid, names[idx], today, now, mode))
        conn.commit()
        conn.close()
        _finalize_bulk(mode)
        return jsonify({'ok': True, 'done': True, 'marked': marked})

    # 1차: 분류
    ambiguous = []
    marked = []
    not_found = []
    for i, nm in enumerate(names):
        users = [dict(r) for r in conn.execute(
            'SELECT id, name, affiliation, team, birthday, note FROM users WHERE name=? ORDER BY affiliation, id',
            (nm,)).fetchall()]
        if not users:
            not_found.append({'index': i, 'name': nm})
        elif len(users) == 1:
            marked.append(_mark_user_attendance(conn, users[0]['id'], nm, today, now, mode))
        else:
            ambiguous.append({'index': i, 'name': nm, 'candidates': users})
    conn.commit()
    conn.close()
    _finalize_bulk(mode)
    return jsonify({
        'ok': True,
        'need_resolution': bool(ambiguous),
        'count': len(names),
        'marked': marked,
        'ambiguous': ambiguous,
        'not_found': not_found,
    })


@app.route('/api/attendance/<int:aid>', methods=['DELETE'])
def admin_cancel_attendance(aid):
    """관리자가 출석 기록을 강제 취소한다. DB에서 제거."""
    conn = db()
    row = conn.execute('SELECT * FROM attendance WHERE id=? AND env=?', (aid, SERVER_ENV)).fetchone()
    if not row:
        conn.close()
        return jsonify({'ok': False, 'msg': '해당 출석 기록이 없습니다.'}), 404
    conn.execute('DELETE FROM attendance WHERE id=?', (aid,))
    conn.commit()
    conn.close()
    try:
        refresh_web_report(row['mode'] or 'sunday', env=row['env'] or SERVER_ENV)
    except Exception as e:
        pass
    return jsonify({'ok': True, 'name': row['name']})


@app.route('/api/admin/attendance', methods=['POST'])
def admin_add_attendance():
    """관리자가 임의 날짜·시각의 출석 기록을 추가한다.

    1차 호출(pattern: name 전달) - 이름으로 선택:
      - 이름이 유일하면 바로 출석 처리
      - 동명이인이면 후보 목록(need_resolution=True)을 반환해 선택 유도
      - 명단에 없으면 not_found 응답
    2차 호출(pattern: user_id 전달) - 동명이인 중 특정 사용자 지정 출석 처리
    모드는 날짜의 요일로 자동 판별(일요일/수요일)하며, 지정 시 해당 모드를 사용한다.
    """
    data = request.get_json(silent=True) or {}
    user_id = data.get('user_id')
    name = (data.get('name') or '').strip()
    date = (data.get('date') or '').strip()
    time_str = (data.get('time') or '').strip()
    mode = (data.get('mode') or '').strip()
    try:
        datetime.date.fromisoformat(date)
    except ValueError:
        return jsonify({'ok': False, 'msg': '날짜를 올바르게 입력하세요. (YYYY-MM-DD)'}), 400
    if not re.match(r'^([01]\d|2[0-3]):[0-5]\d$', time_str):
        return jsonify({'ok': False, 'msg': '시각을 HH:MM 형식으로 입력하세요. (예: 10:30)'}), 400
    if not user_id and not name:
        return jsonify({'ok': False, 'msg': '추가할 이름을 입력하세요.'}), 400

    conn = db()
    if mode not in ('sunday', 'wednesday'):
        mode = _mode_for_date(date) or get_mode(conn)

    # 1차: 이름으로 해석 (동명이인 확인)
    if not user_id:
        users = [dict(r) for r in conn.execute(
            'SELECT id, name, affiliation, team, birthday, note FROM users WHERE name=? ORDER BY affiliation, id',
            (name,)).fetchall()]
        if not users:
            conn.close()
            return jsonify({'ok': False, 'msg': "'%s'은(는) 명단에 없는 이름입니다." % name}), 404
        if len(users) > 1:
            conn.close()
            return jsonify({'ok': True, 'need_resolution': True, 'name': name, 'ambiguous': users})
        user_id = users[0]['id']

    user = conn.execute('SELECT * FROM users WHERE id=?', (user_id,)).fetchone()
    if not user:
        conn.close()
        return jsonify({'ok': False, 'msg': '존재하지 않는 사용자입니다.'}), 404
    dup = conn.execute('SELECT * FROM attendance WHERE user_id=? AND check_date=? AND mode=? AND env=?',
                       (user_id, date, mode, SERVER_ENV)).fetchone()
    if dup:
        conn.close()
        return jsonify({'ok': False, 'msg': '%s님은 해당 날짜에 이미 출석 기록이 있습니다. (%s)' % (user['name'], dup['check_time'])})
    check_time = time_str + ':00'
    conn.execute(
        'INSERT INTO attendance (user_id, name, affiliation, check_date, check_time, mode, env) VALUES (?,?,?,?,?,?,?)',
        (user_id, user['name'], user['affiliation'], date, check_time, mode, SERVER_ENV))
    conn.commit()
    conn.close()
    try:
        refresh_web_report(mode, env=SERVER_ENV, date_str=date)
    except Exception:
        pass
    return jsonify({'ok': True, 'name': user['name'], 'date': date, 'time': time_str,
                    'mode': mode})


@app.route('/api/admin/attendance/<int:aid>', methods=['DELETE'])
def admin_delete_attendance(aid):
    """관리자가 임의 추가한 출석 기록(어떤 날짜든)을 삭제한다."""
    conn = db()
    row = conn.execute('SELECT * FROM attendance WHERE id=? AND env=?', (aid, SERVER_ENV)).fetchone()
    if not row:
        conn.close()
        return jsonify({'ok': False, 'msg': '해당 출석 기록이 없습니다.'}), 404
    conn.execute('DELETE FROM attendance WHERE id=?', (aid,))
    conn.commit()
    conn.close()
    try:
        refresh_web_report(row['mode'] or 'sunday', env=row['env'] or SERVER_ENV, date_str=row['check_date'])
    except Exception:
        pass
    return jsonify({'ok': True, 'name': row['name'], 'date': row['check_date']})


@app.route('/api/admin/attendance/list')
def admin_attendance_list():
    """지정 날짜의 출석 기록 목록을 반환한다. (date 파라미터 필수)"""
    date = (request.args.get('date') or '').strip()
    mode = (request.args.get('mode') or '').strip()
    conn = db()
    if mode not in ('sunday', 'wednesday'):
        mode = _mode_for_date(date) or get_mode(conn)
    if date:
        rows = conn.execute('SELECT * FROM attendance WHERE check_date=? AND mode=? AND env=? ORDER BY check_time',
                            (date, mode, SERVER_ENV)).fetchall()
    else:
        rows = conn.execute('SELECT * FROM attendance WHERE mode=? AND env=? ORDER BY check_date DESC, check_time LIMIT 200',
                            (mode, SERVER_ENV)).fetchall()
    conn.close()
    return jsonify([dict(r) for r in rows])


def _ntp_time(host=None, timeout=2.5):
    """NTP 서버에서 현재 UTC 시간(epoch 초)을 얻는다.

    단일 서버가 불안정/차단될 수 있으므로 여러 서버를 순서대로 시도한다.
    """
    if host:
        hosts = [host]
    else:
        hosts = ['time.bora.net', 'time.nist.gov', 'time.windows.com',
                 'kr.pool.ntp.org', 'pool.ntp.org']
    data = b'\x1b' + 47 * b'\0'
    last_err = None
    for h in hosts:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.settimeout(timeout)
        try:
            s.sendto(data, (h, 123))
            resp, _ = s.recvfrom(1024)
            t = struct.unpack('!12I', resp)[10]
            return t - 2208988800
        except Exception as e:
            last_err = e
        finally:
            s.close()
    raise last_err or RuntimeError('NTP 서버에 연결할 수 없습니다.')


def _enable_systemtime_privilege():
    """현재 프로세스 토큰에서 SE_SYSTEMTIME_NAME 권한을 활성화한다. 성공 시 True."""
    import ctypes
    from ctypes import wintypes

    SE_SYSTEMTIME_NAME = 'SeSystemtimePrivilege'
    SE_PRIVILEGE_ENABLED = 0x00000002
    TOKEN_ADJUST_PRIVILEGES = 0x0020
    TOKEN_QUERY = 0x0008

    class LUID(ctypes.Structure):
        _fields_ = [('LowPart', wintypes.DWORD), ('HighPart', ctypes.c_long)]

    class LUID_AND_ATTRIBUTES(ctypes.Structure):
        _fields_ = [('Luid', LUID), ('Attributes', wintypes.DWORD)]

    class TOKEN_PRIVILEGES(ctypes.Structure):
        _fields_ = [('PrivilegeCount', wintypes.DWORD),
                    ('Privileges', LUID_AND_ATTRIBUTES)]

    advapi = ctypes.windll.advapi32
    kernel = ctypes.windll.kernel32

    token = wintypes.HANDLE()
    if not advapi.OpenProcessToken(kernel.GetCurrentProcess(),
                                   TOKEN_ADJUST_PRIVILEGES | TOKEN_QUERY,
                                   ctypes.byref(token)):
        return False
    try:
        luid = LUID()
        if not advapi.LookupPrivilegeValueW(None, SE_SYSTEMTIME_NAME, ctypes.byref(luid)):
            return False
        tp = TOKEN_PRIVILEGES()
        tp.PrivilegeCount = 1
        tp.Privileges[0].Luid = luid
        tp.Privileges[0].Attributes = SE_PRIVILEGE_ENABLED
        return bool(advapi.AdjustTokenPrivileges(token, False, ctypes.byref(tp), 0, None, None))
    finally:
        kernel.CloseHandle(token)


def _set_system_time(dt):
    """시스템 시간(UTC)을 설정한다. 플랫폼별로 처리. 성공 시 True 반환."""
    if os.name == 'posix':
        return _set_system_time_linux(dt)
    return _set_system_time_windows(dt)


def _set_system_time_windows(dt):
    """Windows 시스템 시간(UTC)을 설정한다. 관리자 권한 필요. 성공 시 True 반환."""
    import ctypes
    from ctypes import wintypes
    _enable_systemtime_privilege()

    class SYSTEMTIME(ctypes.Structure):
        _fields_ = [('wYear', wintypes.WORD), ('wMonth', wintypes.WORD),
                    ('wDayOfWeek', wintypes.WORD), ('wDay', wintypes.WORD),
                    ('wHour', wintypes.WORD), ('wMinute', wintypes.WORD),
                    ('wSecond', wintypes.WORD), ('wMilliseconds', wintypes.WORD)]

    st = SYSTEMTIME()
    st.wYear = dt.year
    st.wMonth = dt.month
    st.wDay = dt.day
    st.wHour = dt.hour
    st.wMinute = dt.minute
    st.wSecond = dt.second
    st.wMilliseconds = dt.microsecond // 1000
    return bool(ctypes.windll.kernel32.SetSystemTime(ctypes.byref(st)))


def _set_system_time_linux(dt):
    """Linux(systemd)에서 시스템 시간을 설정한다. root 필요. 성공 시 True 반환.

    timedatectl set-time은 로컬 시간 문자열을 받으므로, UTC로 주어진 dt를 로컬 시간대로 변환한다.
    """
    import subprocess
    aware = dt.replace(tzinfo=datetime.timezone.utc)
    local = aware.astimezone()
    iso = local.strftime('%Y-%m-%d %H:%M:%S')
    try:
        subprocess.run(['timedatectl', 'set-time', iso], check=True,
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=10)
        return True
    except Exception:
        return False


@app.route('/api/admin/time', methods=['GET'])
def admin_get_time():
    """현재 시스템(로컬) 시간과 인터넷(NTP) 시간을 표시한다. (읽기 전용, 시스템 시간 변경 없음)"""
    internet = None
    try:
        internet = datetime.datetime.utcfromtimestamp(_ntp_time())
    except Exception:
        internet = None
    return jsonify({
        'system_local': datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'system_utc': datetime.datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S'),
        'internet_utc': internet.strftime('%Y-%m-%d %H:%M:%S') if internet else None,
    })


@app.route('/api/admin/sync-time', methods=['POST'])
def admin_sync_time():
    """인터넷(NTP) 시간을 받아 컴퓨터 시스템 시간을 동기화한다."""
    try:
        epoch = _ntp_time()
        dt = datetime.datetime.utcfromtimestamp(epoch)
    except Exception as e:
        return jsonify({'ok': False, 'msg': '인터넷 시간을 가져오지 못했습니다. 네트워크를 확인하세요. (%s)' % e}), 500
    try:
        ok = _set_system_time(dt)
    except Exception as e:
        return jsonify({'ok': False, 'msg': '시스템 시간 설정 실패. 관리자 권한으로 실행해야 합니다. (%s)' % e}), 500
    if not ok:
        return jsonify({'ok': False, 'msg': '시스템 시간 설정 실패. 관리자 권한으로 실행해야 합니다.'}), 500
    return jsonify({'ok': True, 'set_utc': dt.strftime('%Y-%m-%d %H:%M:%S'),
                    'local_now': datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')})


@app.route('/api/admin/report')
def admin_report_date():
    """지정 날짜(mode) 기준 출석 보고서를 생성해 화면에 띄운다."""
    date_str = (request.args.get('date') or '').strip()
    mode = (request.args.get('mode') or '').strip()
    conn = db()
    if mode not in ('sunday', 'wednesday'):
        mode = _mode_for_date(date_str) or get_mode(conn)
    conn.close()
    try:
        main_path = refresh_web_report(mode, env=SERVER_ENV, date_str=date_str if date_str else None)
    except Exception as e:
        return jsonify({'ok': False, 'msg': '보고서 생성 실패: %s' % e}), 500
    return send_from_directory(BASE_DIR, os.path.basename(main_path))


@app.route('/api/admin/login', methods=['POST'])
def admin_login():
    data = request.get_json(silent=True) or {}
    if data.get('pin') == ADMIN_PIN:
        return jsonify({'ok': True})
    return jsonify({'ok': False, 'msg': 'PIN이 올바르지 않습니다.'}), 401


def _mode_weekday(mode):
    """모드별 서비스 요일. sunday=일요일(6), wednesday=수요일(2). None이면 요일 무관."""
    return {'sunday': 6, 'wednesday': 2}.get(mode)


def _mode_for_date(date_str):
    """날짜의 요일로 모드 자동 판별. 일요일→sunday, 수요일→wednesday, 그 외엔 None."""
    try:
        wd = datetime.date.fromisoformat(date_str).weekday()
    except (ValueError, TypeError):
        return None
    if wd == 6:
        return 'sunday'
    if wd == 2:
        return 'wednesday'
    return None


def _is_service_date(date_str, mode):
    wd = _mode_weekday(mode)
    if wd is None:
        return True
    try:
        return datetime.date.fromisoformat(date_str).weekday() == wd
    except ValueError:
        return False


def _load_report_data(date_str, mode=None):
    """출석 보고서용 데이터를 DB에서 읽는다. (users, attendance, last_attendance, absent_weeks)

    mode='sunday'|'wednesday'면 해당 모드 출석만 필터링한다.
    연속 미출석 주수는 모드별 서비스 요일(일요일/수요일)에 해당하는 실제 이벤트 날짜만
    사용해 계산하므로, 다른 요일에 기록된 데이터는 통계에 영향 주지 않는다.
    absent_weeks: {user_id: 보고일 기준 연속 미출석 주수}
    """
    conn = db()
    users = [dict(r) for r in conn.execute(
        'SELECT id, name, affiliation, team, birthday, note FROM users ORDER BY affiliation, id')]
    if mode in ('sunday', 'wednesday'):
        att_rows = conn.execute(
            'SELECT user_id, check_time, check_date FROM attendance WHERE check_date=? AND mode=?',
            (date_str, mode)).fetchall()
        last_rows = conn.execute(
            'SELECT user_id, MAX(check_date) AS last_date FROM attendance WHERE mode=? GROUP BY user_id',
            (mode,)).fetchall()
        event_rows = conn.execute(
            'SELECT DISTINCT check_date FROM attendance WHERE mode=? ORDER BY check_date', (mode,)).fetchall()
        user_event_rows = conn.execute(
            'SELECT user_id, check_date FROM attendance WHERE mode=?', (mode,)).fetchall()
    else:
        att_rows = conn.execute(
            'SELECT user_id, check_time, check_date FROM attendance WHERE check_date=?', (date_str,)).fetchall()
        last_rows = conn.execute(
            'SELECT user_id, MAX(check_date) AS last_date FROM attendance GROUP BY user_id').fetchall()
        event_rows = conn.execute(
            'SELECT DISTINCT check_date FROM attendance ORDER BY check_date').fetchall()
        user_event_rows = conn.execute(
            'SELECT user_id, check_date FROM attendance').fetchall()
    conn.close()
    attendance = {r['user_id']: r['check_time'] for r in att_rows}
    if mode in ('sunday', 'wednesday') and not _is_service_date(date_str, mode):
        attendance = {}
    last_attendance = {r['user_id']: r['last_date'] for r in last_rows}
    if mode in ('sunday', 'wednesday'):
        last_attendance = {uid: d for uid, d in last_attendance.items() if _is_service_date(d, mode)}

    event_dates = sorted(d for d in {r[0] for r in event_rows} if _is_service_date(d, mode))
    if _is_service_date(date_str, mode) and date_str not in event_dates:
        event_dates.append(date_str)
    attended_dates = {}
    for r in user_event_rows:
        if _is_service_date(r['check_date'], mode):
            attended_dates.setdefault(r['user_id'], set()).add(r['check_date'])
    absent_weeks = {}
    for u in users:
        uid = u['id']
        seen = attended_dates.get(uid, set())
        weeks = 0
        for d in reversed(event_dates):
            if d > date_str:
                continue
            if d in seen:
                break
            weeks += 1
        absent_weeks[uid] = weeks
    return users, attendance, last_attendance, absent_weeks


def _report_mode():
    m = (request.args.get('mode') or '').strip()
    if m in ('sunday', 'wednesday'):
        return m
    conn = db()
    mode = get_mode(conn)
    conn.close()
    return mode


@app.route('/api/report')
def download_report():
    """웹 보고서(출석_그래프.html)를 DB 기준으로 갱신하고 화면에 띄운다.

    date/mode 파라미터는 호환용으로 받되, 모드별 최신 서비스일 기준으로 갱신한다.
    """
    date_str = (request.args.get('date') or '').strip()
    try:
        datetime.date.fromisoformat(date_str)
    except ValueError:
        date_str = None
    mode = _report_mode()
    try:
        refresh_web_report(mode, env=SERVER_ENV)
    except Exception as e:
        return jsonify({'ok': False, 'msg': '보고서 생성 실패: %s' % e}), 500
    return send_from_directory(BASE_DIR, '출석_그래프_%s.html' % SERVER_ENV)


@app.route('/api/report/a4')
def download_a4_report():
    """웹 보고서를 갱신 후 띄운다."""
    mode = _report_mode()
    try:
        refresh_web_report(mode, env=SERVER_ENV)
    except Exception as e:
        return jsonify({'ok': False, 'msg': '보고서 생성 실패: %s' % e}), 500
    return send_from_directory(BASE_DIR, '출석_그래프_%s.html' % SERVER_ENV)


@app.route('/api/admin/export-teams', methods=['POST'])
def admin_export_teams():
    """팀별 상세 보고서 HTML 파일들을 수동으로 생성/내보내기 한다."""
    mode = _report_mode()
    try:
        refresh_web_report(mode, env=SERVER_ENV)
        render_reports_to_png(mode, env=SERVER_ENV)
        archive_dir = os.path.join(BASE_DIR, 'data', '통계_%s' % SERVER_ENV, 'teams')
        return jsonify({'ok': True, 'dir': archive_dir})
    except Exception as e:
        return jsonify({'ok': False, 'msg': '팀별 보고서 내보내기 실패: %s' % e}), 500


@app.route('/api/admin/shutdown', methods=['POST'])
def admin_shutdown():
    """웹 보고서를 갱신한 뒤 서버를 종료한다. (현재 모드 기준)"""
    conn = db()
    mode = get_mode(conn)
    conn.close()
    report = os.path.join(BASE_DIR, '출석_그래프_%s.html' % SERVER_ENV)
    try:
        refresh_web_report(mode, env=SERVER_ENV)
    except Exception as e:
        return jsonify({'ok': False, 'msg': '보고서 생성 실패: %s' % e}), 500

    # 배포용 PNG 생성(최선 노력) 후 종료
    def _finish():
        try:
            render_reports_to_png(mode, env=SERVER_ENV)
        except Exception:
            pass
        time.sleep(1.5)
        os._exit(0)
    threading.Thread(target=_finish, daemon=True).start()
    return jsonify({'ok': True, 'report': report, 'mode': mode, 'env': SERVER_ENV})


@app.route('/api/admin/teams-affiliations')
def admin_teams_affiliations():
    """소속→팀 매핑. 원칙: 같은 소속은 반드시 같은 팀.

    혹시 이질 데이터가 섞여도 가장 많은(다수결) 팀을 대표값으로 사용한다.
    custom_teams(아직 인원이 없는 새 팀)와 custom_affiliations(임시 소속)도 목록에 포함한다.
    """
    conn = db()
    rows = conn.execute(
        'SELECT affiliation, team, COUNT(*) c FROM users '
        'WHERE affiliation IS NOT NULL AND affiliation != "" AND team IS NOT NULL AND team != "" '
        'GROUP BY affiliation, team').fetchall()
    custom = _get_custom_teams(conn)
    custom_affs = _get_custom_affiliations(conn)
    conn.close()
    counts = {}
    for r in rows:
        counts.setdefault(r['affiliation'], []).append((r['c'], r['team']))
    mapping = {aff: max(lst)[1] for aff, lst in counts.items()}
    teams = sorted(set(mapping.values()) | set(custom))
    affiliations = sorted(set(mapping.keys()) | set(custom_affs) | {TEMP_AFFIL})
    return jsonify({'teams': teams, 'affiliations': affiliations, 'mapping': mapping})


def _get_custom_teams(conn):
    """settings에 저장된, 아직 인원이 없는 신규 팀 목록."""
    row = conn.execute("SELECT value FROM settings WHERE key='custom_teams'").fetchone()
    if not row or not row['value']:
        return []
    try:
        return json.loads(row['value'])
    except Exception:
        return []


def _set_custom_teams(conn, teams):
    conn.execute("INSERT OR REPLACE INTO settings (key, value) VALUES ('custom_teams', ?)",
                 (json.dumps(teams, ensure_ascii=False),))


TEMP_AFFIL = '임시'


def _get_custom_affiliations(conn):
    """settings에 저장된, 아직 인원이 없는 임시 소속 목록."""
    row = conn.execute("SELECT value FROM settings WHERE key='custom_affiliations'").fetchone()
    if not row or not row['value']:
        return []
    try:
        return json.loads(row['value'])
    except Exception:
        return []


def _set_custom_affiliations(conn, affs):
    conn.execute("INSERT OR REPLACE INTO settings (key, value) VALUES ('custom_affiliations', ?)",
                 (json.dumps(affs, ensure_ascii=False),))


@app.route('/api/admin/affiliations/create', methods=['POST'])
def admin_create_affiliation():
    """임시 소속을 추가한다. (아직 인원이 없는 소속)

    기본적으로 '임시' 소속을 만들며, 이름을 지정하면 그 이름으로 생성한다.
    """
    d = request.get_json(silent=True) or {}
    name = (d.get('name') or '').strip() or TEMP_AFFIL
    conn = db()
    existing = conn.execute('SELECT COUNT(*) FROM users WHERE affiliation=?', (name,)).fetchone()[0]
    custom = _get_custom_affiliations(conn)
    if existing or name in custom:
        conn.close()
        return jsonify({'ok': False, 'msg': "'%s' 소속이 이미 존재합니다." % name}), 400
    custom.append(name)
    _set_custom_affiliations(conn, custom)
    conn.commit()
    conn.close()
    try:
        refresh_web_report(env=SERVER_ENV)
    except Exception:
        pass
    return jsonify({'ok': True, 'name': name, 'temp': name == TEMP_AFFIL})


@app.route('/api/admin/affiliations/rename', methods=['POST'])
def admin_rename_affiliation():
    """소속 이름을 변경한다. 소속된 모든 사용자에게 즉시 반영.

    임시 소속('임시')을 다른 이름으로 바꾸면 빈 '임시' 소속이 다시 생긴다.
    """
    d = request.get_json(silent=True) or {}
    old = (d.get('old_name') or '').strip()
    new = (d.get('new_name') or '').strip()
    if not old or not new:
        return jsonify({'ok': False, 'msg': '변경할 소속과 새 이름을 모두 입력하세요.'}), 400
    if old == new:
        return jsonify({'ok': False, 'msg': '새 이름이 기존 이름과 같습니다.'}), 400
    conn = db()
    exists = conn.execute('SELECT COUNT(*) FROM users WHERE affiliation=?', (new,)).fetchone()[0]
    custom = _get_custom_affiliations(conn)
    if exists or new in custom:
        conn.close()
        return jsonify({'ok': False, 'msg': "'%s' 소속이 이미 존재합니다." % new}), 400
    cur = conn.execute('UPDATE users SET affiliation=? WHERE affiliation=?', (new, old))
    renamed = cur.rowcount
    if old in custom:
        custom = [new if a == old else a for a in custom]
        _set_custom_affiliations(conn, custom)
    if old == TEMP_AFFIL and TEMP_AFFIL not in custom:
        custom.append(TEMP_AFFIL)
        _set_custom_affiliations(conn, custom)
    conn.commit()
    conn.close()
    try:
        refresh_web_report(env=SERVER_ENV)
    except Exception:
        pass
    return jsonify({'ok': True, 'renamed': renamed, 'old_name': old, 'new_name': new})


@app.route('/api/admin/teams/bulk-move', methods=['POST'])
def admin_bulk_move_team():
    """특정 소속의 모든 사용자를 특정 팀으로 일괄 이동. 통계에 즉시 반영."""
    d = request.get_json(silent=True) or {}
    aff = (d.get('affiliation') or '').strip()
    team = (d.get('team') or '').strip()
    if not aff or not team:
        return jsonify({'ok': False, 'msg': '소속과 이동할 팀을 모두 선택하세요.'}), 400
    conn = db()
    cur = conn.execute('UPDATE users SET team=? WHERE affiliation=?', (team, aff))
    moved = cur.rowcount
    custom = _get_custom_teams(conn)
    if team in custom:
        custom.remove(team)
        _set_custom_teams(conn, custom)
    conn.commit()
    conn.close()
    try:
        refresh_web_report(env=SERVER_ENV)
    except Exception:
        pass
    return jsonify({'ok': True, 'moved': moved, 'affiliation': aff, 'team': team})


@app.route('/api/admin/teams/rename', methods=['POST'])
def admin_rename_team():
    """기존 팀의 이름을 변경한다. 소속된 모든 사용자와 통계에 즉시 반영."""
    d = request.get_json(silent=True) or {}
    old = (d.get('old_name') or '').strip()
    new = (d.get('new_name') or '').strip()
    if not old or not new:
        return jsonify({'ok': False, 'msg': '변경할 팀과 새 이름을 모두 입력하세요.'}), 400
    if old == new:
        return jsonify({'ok': False, 'msg': '새 이름이 기존 이름과 같습니다.'}), 400
    conn = db()
    dup = conn.execute('SELECT COUNT(*) FROM users WHERE team=?', (new,)).fetchone()[0]
    custom = _get_custom_teams(conn)
    if dup or new in custom:
        conn.close()
        return jsonify({'ok': False, 'msg': "'%s' 팀이 이미 존재합니다." % new}), 400
    cur = conn.execute('UPDATE users SET team=? WHERE team=?', (new, old))
    renamed = cur.rowcount
    if old in custom:
        custom = [new if t == old else t for t in custom]
        _set_custom_teams(conn, custom)
    conn.commit()
    conn.close()
    try:
        refresh_web_report(env=SERVER_ENV)
    except Exception:
        pass
    return jsonify({'ok': True, 'renamed': renamed, 'old_name': old, 'new_name': new})


@app.route('/api/admin/newbie-days', methods=['GET'])
def api_get_newbie_days():
    """새신우 유지 기간(일) 조회. 기본 30."""
    conn = db()
    row = conn.execute("SELECT value FROM settings WHERE key='newbie_days'").fetchone()
    conn.close()
    try:
        v = int(row['value']) if row and row['value'] else 30
    except Exception:
        v = 30
    return jsonify({'days': max(1, min(365, v))})


@app.route('/api/admin/newbie-days', methods=['POST'])
def api_set_newbie_days():
    """새신우 유지 기간(일) 변경. 1~365일."""
    d = request.get_json(silent=True) or {}
    try:
        v = int(d.get('days'))
    except (TypeError, ValueError):
        return jsonify({'ok': False, 'msg': '숫자를 입력하세요.'}), 400
    if not (1 <= v <= 365):
        return jsonify({'ok': False, 'msg': '1~365 사이의 값으로 입력하세요.'}), 400
    conn = db()
    conn.execute("INSERT OR REPLACE INTO settings (key, value) VALUES ('newbie_days', ?)", (str(v),))
    conn.commit()
    conn.close()
    try:
        refresh_web_report(env=SERVER_ENV)
    except Exception:
        pass
    return jsonify({'ok': True, 'days': v})


@app.route('/api/admin/teams/create', methods=['POST'])
def admin_create_team():
    """새 팀을 등록한다. 인원이 없어도 드롭다운에 바로 표시된다."""
    d = request.get_json(silent=True) or {}
    name = (d.get('name') or '').strip()
    if not name:
        return jsonify({'ok': False, 'msg': '팀 이름을 입력하세요.'}), 400
    conn = db()
    dup = conn.execute('SELECT COUNT(*) FROM users WHERE team=?', (name,)).fetchone()[0]
    custom = _get_custom_teams(conn)
    if dup or name in custom:
        conn.close()
        return jsonify({'ok': False, 'msg': "'%s' 팀이 이미 존재합니다." % name}), 400
    custom.append(name)
    _set_custom_teams(conn, custom)
    conn.commit()
    conn.close()
    return jsonify({'ok': True, 'name': name})


@app.route('/api/admin/teams/delete', methods=['POST'])
def admin_delete_team():
    """팀을 삭제한다. 인원이 남아 있으면 거부하고, 비어 있는 팀만 삭제한다.

    인원이 있는 팀(custom_teams 아님)은 삭제 불가.
    인원이 없는 팀(0명 또는 custom_teams에만 존재)만 custom_teams 목록에서 제거한다.
    """
    d = request.get_json(silent=True) or {}
    name = (d.get('name') or '').strip()
    if not name:
        return jsonify({'ok': False, 'msg': '삭제할 팀을 선택하세요.'}), 400
    conn = db()
    cnt = conn.execute('SELECT COUNT(*) FROM users WHERE team=?', (name,)).fetchone()[0]
    custom = _get_custom_teams(conn)
    if cnt > 0:
        conn.close()
        return jsonify({'ok': False, 'msg': "'%s' 팀에 인원 %d명이 있어 삭제할 수 없습니다. 먼저 인원을 이동하세요." % (name, cnt)}), 400
    if name not in custom:
        conn.close()
        return jsonify({'ok': False, 'msg': "'%s' 팀이 존재하지 않거나 인원이 있는 팀입니다." % name}), 400
    custom.remove(name)
    _set_custom_teams(conn, custom)
    conn.commit()
    conn.close()
    try:
        refresh_web_report(env=SERVER_ENV)
    except Exception:
        pass
    return jsonify({'ok': True, 'name': name})


@app.route('/api/admin/users')
def admin_users():
    conn = db()
    prune_expired_users(conn)
    rows = conn.execute('SELECT * FROM users ORDER BY id').fetchall()
    conn.close()
    return jsonify([dict(r) for r in rows])


@app.route('/api/admin/users', methods=['POST'])
def admin_create_user():
    d = request.get_json(silent=True) or {}
    name = (d.get('name') or '').strip()
    if not name:
        return jsonify({'ok': False, 'msg': '이름을 입력하세요.'}), 400
    d['note'] = _normalize_newbie_note(d.get('note'))
    d['birthday'] = norm_birthday(d.get('birthday'))
    d['is_chaplain'] = 1 if int(d.get('is_chaplain') or 0) else 0
    conn = db()
    cur = conn.execute(
        'INSERT INTO users (name, baptism, affiliation, team, phone, discharge_date, birthday, note, is_chaplain) '
        'VALUES (?,?,?,?,?,?,?,?,?)',
        (name, d.get('baptism', ''), d.get('affiliation', ''), d.get('team', ''), d.get('phone', ''),
         d.get('discharge_date', ''), d.get('birthday', ''), d.get('note', ''), d['is_chaplain']))
    conn.commit()
    conn.close()
    try:
        refresh_web_report(env=SERVER_ENV)
    except Exception as e:
        pass
    return jsonify({'ok': True, 'id': cur.lastrowid})


@app.route('/api/admin/users/<int:uid>', methods=['PUT'])
def admin_update_user(uid):
    d = request.get_json(silent=True) or {}
    new_note = _normalize_newbie_note(d.get('note'))
    conn = db()
    user = conn.execute('SELECT id FROM users WHERE id=?', (uid,)).fetchone()
    if not user:
        conn.close()
        return jsonify({'ok': False, 'msg': '사용자가 없습니다.'}), 404
    d['note'] = new_note
    d['birthday'] = norm_birthday(d.get('birthday'))
    d['is_chaplain'] = 1 if int(d.get('is_chaplain') or 0) else 0
    sets = ', '.join('%s=?' % f for f in USER_FIELDS)
    vals = [d.get(f, '') for f in USER_FIELDS]
    conn.execute('UPDATE users SET %s WHERE id=?' % sets, vals + [uid])
    conn.commit()
    conn.close()
    try:
        refresh_web_report(env=SERVER_ENV)
    except Exception as e:
        pass
    return jsonify({'ok': True})


@app.route('/api/admin/users/<int:uid>', methods=['DELETE'])
def admin_delete_user(uid):
    """명단에서 삭제한다. 수동 삭제도 users_archive로 백업해 추적·복원 가능하게 한다."""
    conn = db()
    row = conn.execute('SELECT * FROM users WHERE id=?', (uid,)).fetchone()
    if not row:
        conn.close()
        return jsonify({'ok': False, 'msg': '사용자가 없습니다.'}), 404
    _archive_user(conn, row)
    conn.execute('DELETE FROM users WHERE id=?', (uid,))
    conn.commit()
    conn.close()
    try:
        refresh_web_report(env=SERVER_ENV)
    except Exception as e:
        pass
    return jsonify({'ok': True})


@app.route('/api/admin/users/archive')
def admin_archived_users():
    """전역일로 인해 아카이브된 사용자 목록."""
    conn = db()
    rows = conn.execute('SELECT * FROM users_archive ORDER BY archived_at DESC, id').fetchall()
    conn.close()
    return jsonify([dict(r) for r in rows])


@app.route('/api/admin/users/archive/<int:uid>/restore', methods=['POST'])
def admin_restore_user(uid):
    """아카이브된 사용자를 명단으로 복원한다."""
    conn = db()
    row = conn.execute('SELECT * FROM users_archive WHERE id=?', (uid,)).fetchone()
    if not row:
        conn.close()
        return jsonify({'ok': False, 'msg': '아카이브에 해당 사용자가 없습니다.'}), 404
    conn.execute('DELETE FROM users_archive WHERE id=?', (uid,))
    conn.execute(
        'INSERT INTO users (id, name, baptism, affiliation, team, phone, discharge_date, birthday, note, prev_church, is_chaplain) '
        'VALUES (?,?,?,?,?,?,?,?,?,?,?)',
        (row['id'], row['name'], row['baptism'], row['affiliation'], row['team'],
         row['phone'], row['discharge_date'], row['birthday'], row['note'], row['prev_church'] or '',
         (row['is_chaplain'] if 'is_chaplain' in row.keys() else 0) or 0))
    conn.commit()
    conn.close()
    return jsonify({'ok': True, 'name': row['name']})


def _refresh_report_for_absences(mode='wednesday', env=None):
    """결석 사유 변경 후 웹 보고서 HTML/PNG를 갱신한다."""
    env = env or SERVER_ENV
    try:
        refresh_web_report(mode, env=env)
    except Exception:
        pass
    try:
        threading.Thread(target=render_reports_to_png, kwargs={'mode': mode, 'env': env}, daemon=True).start()
    except Exception:
        pass


@app.route('/api/admin/absences')
def admin_absences():
    """지정된 날짜(수요일)의 미출석 군종병과 기등록 결석 사유를 조회한다."""
    date_str = (request.args.get('date') or '').strip()
    mode = request.args.get('mode') or 'wednesday'
    env = request.args.get('env') or SERVER_ENV
    conn = db()
    absentees = []
    if date_str:
        attended = {r['user_id'] for r in conn.execute(
            'SELECT user_id FROM attendance WHERE mode=? AND env=? AND check_date=?',
            (mode, env, date_str)).fetchall()}
        abs_rows = conn.execute(
            'SELECT id, user_id, reason FROM absences WHERE mode=? AND env=? AND check_date=?',
            (mode, env, date_str)).fetchall()
        abs_map = {r['user_id']: {'id': r['id'], 'reason': r['reason'] or ''} for r in abs_rows}
        users = conn.execute(
            'SELECT id, name, affiliation, team FROM users WHERE is_chaplain=1 ORDER BY affiliation, id').fetchall()
        hist = {}
        if users:
            ids = [u['id'] for u in users]
            ph = ','.join(['?'] * len(ids))
            hist_rows = conn.execute(
                "SELECT user_id, check_date, reason FROM absences "
                "WHERE user_id IN (%s) AND mode=? AND env=? AND check_date < ? AND reason != '' "
                "ORDER BY check_date ASC" % ph,
                ids + [mode, env, date_str]).fetchall()
            for r in hist_rows:
                hist.setdefault(r['user_id'], []).append({'date': r['check_date'], 'reason': r['reason']})
        for u in users:
            if u['id'] in attended:
                continue
            h = hist.get(u['id'], [])
            absentees.append({
                'id': u['id'], 'name': u['name'],
                'affiliation': u['affiliation'] or '', 'team': u['team'] or '',
                'absence': abs_map.get(u['id']),
                'history': h[-4:],
            })
    conn.close()
    return jsonify({'ok': True, 'date': date_str, 'absentees': absentees})


@app.route('/api/admin/absences', methods=['POST'])
def admin_absence_upsert():
    """수요일 결석 사유를 저장/수정한다. (user_id, check_date, mode, env) 중복 시 덮어쓴다."""
    d = request.get_json(silent=True) or {}
    uid = d.get('user_id')
    date_str = (d.get('date') or '').strip()
    mode = d.get('mode') or 'wednesday'
    env = d.get('env') or SERVER_ENV
    reason = (d.get('reason') or '').strip()
    if not uid or not date_str:
        return jsonify({'ok': False, 'msg': '사용자와 날짜를 입력하세요.'}), 400
    conn = db()
    if not conn.execute('SELECT id FROM users WHERE id=?', (uid,)).fetchone():
        conn.close()
        return jsonify({'ok': False, 'msg': '사용자가 없습니다.'}), 404
    now = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    conn.execute(
        'INSERT INTO absences (user_id, check_date, reason, mode, env, created_at) VALUES (?,?,?,?,?,?) '
        'ON CONFLICT (user_id, check_date, mode, env) DO UPDATE SET reason=excluded.reason, created_at=excluded.created_at',
        (uid, date_str, reason, mode, env, now))
    conn.commit()
    conn.close()
    _refresh_report_for_absences(mode, env)
    return jsonify({'ok': True})


@app.route('/api/admin/absences/<int:aid>', methods=['DELETE'])
def admin_absence_delete(aid):
    """등록된 결석 사유를 삭제한다."""
    conn = db()
    row = conn.execute('SELECT * FROM absences WHERE id=?', (aid,)).fetchone()
    if not row:
        conn.close()
        return jsonify({'ok': False, 'msg': '등록된 사유가 없습니다.'}), 404
    conn.execute('DELETE FROM absences WHERE id=?', (aid,))
    conn.commit()
    mode = row['mode'] or 'wednesday'
    env = row['env'] or SERVER_ENV
    conn.close()
    _refresh_report_for_absences(mode, env)
    return jsonify({'ok': True})


init_db()

if __name__ == '__main__':
    app.run(host='127.0.0.1', port=5000, debug=False)