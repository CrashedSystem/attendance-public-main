# -*- coding: utf-8 -*-
"""출석(attendance) 관련 DB 쿼리.
"""
from models.settings import is_service_date


def get_attendance(conn, user_id, date, mode, env):
    """특정 사용자·날짜·모드·환경의 출석 기록을 조회한다. 없으면 None."""
    return conn.execute(
        'SELECT * FROM attendance WHERE user_id=? AND check_date=? AND mode=? AND env=?',
        (user_id, date, mode, env)).fetchone()


def get_attendance_by_id_env(conn, aid, env):
    """id·env로 출석 기록을 조회한다. 없으면 None."""
    return conn.execute(
        'SELECT * FROM attendance WHERE id=? AND env=?', (aid, env)).fetchone()


def create_attendance(conn, user_id, name, affiliation, date, time, mode, env):
    """출석 기록을 삽입한다."""
    conn.execute(
        'INSERT INTO attendance (user_id, name, affiliation, check_date, check_time, mode, env) '
        'VALUES (?,?,?,?,?,?,?)',
        (user_id, name, affiliation, date, time, mode, env))


def delete_attendance(conn, aid):
    """출석 기록을 삭제한다."""
    conn.execute('DELETE FROM attendance WHERE id=?', (aid,))


def get_weeks_attended(conn, user_id, mode, today, env):
    """특정 사용자의 해당 모드 누적 출석 주수(서로 다른 날짜 수)를 반환한다."""
    return conn.execute(
        'SELECT COUNT(DISTINCT check_date) FROM attendance '
        'WHERE user_id=? AND mode=? AND check_date<=? AND env=?',
        (user_id, mode, today, env)).fetchone()[0]


def get_today_attendance(conn, today, env):
    """오늘 날짜의 전체 출석 기록을 (출석 시각순) 조회한다."""
    rows = conn.execute(
        'SELECT * FROM attendance WHERE check_date=? AND env=? ORDER BY check_time',
        (today, env)).fetchall()
    return [dict(r) for r in rows]


def get_attendance_history(conn, env, limit=500):
    """최근 출석 기록 전체(최신순)를 조회한다."""
    rows = conn.execute(
        'SELECT * FROM attendance WHERE env=? ORDER BY check_date DESC, check_time DESC LIMIT ?',
        (env, limit)).fetchall()
    return [dict(r) for r in rows]


def get_attendance_by_date(conn, date, mode, env):
    """지정 날짜·모드·환경의 출석 목록(시각순)."""
    rows = conn.execute(
        'SELECT * FROM attendance WHERE check_date=? AND mode=? AND env=? ORDER BY check_time',
        (date, mode, env)).fetchall()
    return [dict(r) for r in rows]


def get_attendance_recent(conn, mode, env, limit=200):
    """지정 모드·환경의 최근 출석 목록(날짜·시각 내림차순)."""
    rows = conn.execute(
        'SELECT * FROM attendance WHERE mode=? AND env=? ORDER BY check_date DESC, check_time LIMIT ?',
        (mode, env, limit)).fetchall()
    return [dict(r) for r in rows]


def get_report_data(conn, date_str, mode=None):
    """출석 보고서용 데이터를 DB에서 읽는다.

    반환: (users, attendance, last_attendance, absent_weeks)
    - users: 모든 사용자 (소속·id 정렬)
    - attendance: {user_id: check_time} (보고일 출석)
    - last_attendance: {user_id: 최근 출석일}
    - absent_weeks: {user_id: 보고일 기준 연속 미출석 주수}

    mode='sunday'|'wednesday'면 해당 모드 출석만 필터링하고, 서비스 요일에 해당하지 않는
    날짜의 기록은 통계에서 제외한다.
    """
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
    attendance = {r['user_id']: r['check_time'] for r in att_rows}
    if mode in ('sunday', 'wednesday') and not is_service_date(date_str, mode):
        attendance = {}
    last_attendance = {r['user_id']: r['last_date'] for r in last_rows}
    if mode in ('sunday', 'wednesday'):
        last_attendance = {uid: d for uid, d in last_attendance.items() if is_service_date(d, mode)}

    event_dates = sorted(d for d in {r[0] for r in event_rows} if is_service_date(d, mode))
    if is_service_date(date_str, mode) and date_str not in event_dates:
        event_dates.append(date_str)
    attended_dates = {}
    for r in user_event_rows:
        if is_service_date(r['check_date'], mode):
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
