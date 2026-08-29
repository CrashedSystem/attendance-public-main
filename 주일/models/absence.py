# -*- coding: utf-8 -*-
"""결석(absences) 관련 DB 쿼리.
"""


def get_absences(conn, date, mode, env):
    """지정 날짜·모드·환경의 결석 사유 목록을 조회한다."""
    rows = conn.execute(
        'SELECT id, user_id, reason FROM absences WHERE mode=? AND env=? AND check_date=?',
        (mode, env, date)).fetchall()
    return rows


def get_absences_by_id(conn, aid):
    """id로 결석 사유를 조회한다. 없으면 None."""
    return conn.execute('SELECT * FROM absences WHERE id=?', (aid,)).fetchone()


def create_or_update_absence(conn, user_id, date, reason, mode, env, created_at):
    """결석 사유를 저장/수정한다. (user_id, check_date, mode, env) 중복 시 덮어쓴다."""
    conn.execute(
        'INSERT INTO absences (user_id, check_date, reason, mode, env, created_at) VALUES (?,?,?,?,?,?) '
        'ON CONFLICT (user_id, check_date, mode, env) DO UPDATE SET reason=excluded.reason, created_at=excluded.created_at',
        (user_id, date, reason, mode, env, created_at))


def delete_absence(conn, aid):
    """등록된 결석 사유를 삭제한다."""
    conn.execute('DELETE FROM absences WHERE id=?', (aid,))


def get_absence_history_for_ids(conn, user_ids, mode, env, before_date, limit_per_user=None):
    """여러 사용자의 과거 결석 사유(날짜 오름차순)를 조회해 user_id별로 묶어 반환한다.

    반환: {user_id: [{'date':..., 'reason':...}, ...]}
    """
    if not user_ids:
        return {}
    ph = ','.join(['?'] * len(user_ids))
    rows = conn.execute(
        "SELECT user_id, check_date, reason FROM absences "
        "WHERE user_id IN (%s) AND mode=? AND env=? AND check_date < ? AND reason != '' "
        "ORDER BY check_date ASC" % ph,
        list(user_ids) + [mode, env, before_date]).fetchall()
    hist = {}
    for r in rows:
        hist.setdefault(r['user_id'], []).append({'date': r['check_date'], 'reason': r['reason']})
    if limit_per_user is not None:
        hist = {uid: lst[-limit_per_user:] for uid, lst in hist.items()}
    return hist
