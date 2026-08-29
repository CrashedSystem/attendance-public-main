# -*- coding: utf-8 -*-
"""결석(수요일 미출석) 관리 비즈니스 로직.

- 특정 날짜의 미출석 군종병 및 기등록 결석 사유 조회
- 결석 사유 저장/삭제
"""
import datetime

from config import SERVER_ENV
from models import absence as absence_model
from models import user as user_model
from models.database import db
from services.report_service import safe_refresh_with_png


def _attended_user_ids(conn, date_str, mode, env):
    """해당 날짜에 출석한 사용자 id 집합을 반환한다."""
    return {r['user_id'] for r in conn.execute(
        'SELECT user_id FROM attendance WHERE mode=? AND env=? AND check_date=?',
        (mode, env, date_str)).fetchall()}


def get_absentees_for_date(date_str, mode='wednesday', env=None):
    """지정 날짜(수요일)의 미출석 군종병과 기등록 결석 사유를 조회한다.

    반환: {'ok', 'date', 'absentees'}
    """
    env = env or SERVER_ENV
    conn = db()
    absentees = []
    if date_str:
        attended = _attended_user_ids(conn, date_str, mode, env)
        abs_map = {r['user_id']: {'id': r['id'], 'reason': r['reason'] or ''}
                   for r in absence_model.get_absences(conn, date_str, mode, env)}
        users = user_model.get_chaplains(conn)
        ids = [u['id'] for u in users]
        hist = absence_model.get_absence_history_for_ids(conn, ids, mode, env, date_str, limit_per_user=4)
        for u in users:
            if u['id'] in attended:
                continue
            h = hist.get(u['id'], [])
            absentees.append({
                'id': u['id'], 'name': u['name'],
                'affiliation': u['affiliation'] or '', 'team': u['team'] or '',
                'absence': abs_map.get(u['id']),
                'history': h,
            })
    conn.close()
    return {'ok': True, 'date': date_str, 'absentees': absentees}


def save_absence_reason(user_id, date_str, reason, mode='wednesday', env=None):
    """수요일 결석 사유를 저장/수정한다. (user_id, check_date, mode, env) 중복 시 덮어쓴다.

    반환: (응답 dict, HTTP 상태 코드)
    """
    env = env or SERVER_ENV
    reason = (reason or '').strip()
    if not user_id or not date_str:
        return ({'ok': False, 'msg': '사용자와 날짜를 입력하세요.'}, 400)
    conn = db()
    if not user_model.get_user(conn, user_id):
        conn.close()
        return ({'ok': False, 'msg': '사용자가 없습니다.'}, 404)
    now = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    absence_model.create_or_update_absence(conn, user_id, date_str, reason, mode, env, now)
    conn.commit()
    conn.close()
    safe_refresh_with_png(mode, env)
    return ({'ok': True}, 200)


def delete_absence(aid, env=None):
    """등록된 결석 사유를 삭제한다.

    반환: (응답 dict, HTTP 상태 코드)
    """
    env = env or SERVER_ENV
    conn = db()
    row = absence_model.get_absences_by_id(conn, aid)
    if not row:
        conn.close()
        return ({'ok': False, 'msg': '등록된 사유가 없습니다.'}, 404)
    absence_model.delete_absence(conn, aid)
    conn.commit()
    mode = row['mode'] or 'wednesday'
    row_env = row['env'] or env
    conn.close()
    safe_refresh_with_png(mode, row_env)
    return ({'ok': True}, 200)
