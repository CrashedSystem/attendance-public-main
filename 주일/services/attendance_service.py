# -*- coding: utf-8 -*-
"""출석 처리 비즈니스 로직.

- 일반 출석(체크인), 일괄 출석(동명이인 해결), 출석 취소
- 관리자의 임의 날짜·시각 출석 추가
"""
import datetime
import re
import sqlite3

from config import SERVER_ENV
from models import attendance as attendance_model
from models import user as user_model
from models.database import db
from models.settings import get_current_mode, mode_for_date
from services.report_service import safe_refresh


def _now_parts():
    """오늘 날짜와 현재 시각(HH:MM:SS)을 반환한다."""
    return datetime.date.today().isoformat(), datetime.datetime.now().strftime('%H:%M:%S')


def _mark_user_attendance(conn, uid, name, today, now, mode, env):
    """단일 사용자 출석 기록. 중복/존재여부를 검사한다. (commit은 호출자 책임)

    반환: {'name', 'user_id', 'ok', 'msg'}
    """
    user = user_model.get_user(conn, uid)
    if not user:
        return {'name': name, 'user_id': uid, 'ok': False, 'msg': '사용자 없음'}
    dup = attendance_model.get_attendance(conn, uid, today, mode, env)
    if dup:
        return {'name': user['name'], 'user_id': uid, 'ok': False, 'msg': '이미 출석'}
    try:
        attendance_model.create_attendance(
            conn, uid, user['name'], user['affiliation'], today, now, mode, env)
    except sqlite3.IntegrityError:
        return {'name': user['name'], 'user_id': uid, 'ok': False, 'msg': '이미 출석'}
    return {'name': user['name'], 'user_id': uid, 'ok': True, 'msg': '완료'}


def process_checkin(user_id, mode=None, env=None):
    """단일 사용자 출석 처리.

    반환: (응답 dict, HTTP 상태 코드)
    """
    env = env or SERVER_ENV
    if not user_id:
        return ({'ok': False, 'msg': '사용자를 선택해주세요.'}, 400)
    conn = db()
    try:
        user = user_model.get_user(conn, user_id)
        if not user:
            return ({'ok': False, 'msg': '존재하지 않는 사용자입니다.'}, 404)
        today, now = _now_parts()
        mode = mode or get_current_mode(conn)
        dup = attendance_model.get_attendance(conn, user_id, today, mode, env)
        if dup:
            return ({'ok': False, 'msg': '%s님은 이미 출석하셨습니다. (%s)' % (user['name'], dup['check_time'])}, 409)
        try:
            attendance_model.create_attendance(conn, user_id, user['name'], user['affiliation'], today, now, mode, env)
        except sqlite3.IntegrityError:
            return ({'ok': False, 'msg': '%s님은 이미 출석하셨습니다.' % user['name']}, 409)
        weeks = attendance_model.get_weeks_attended(conn, user_id, mode, today, env)
        conn.commit()
    finally:
        conn.close()
    safe_refresh(mode, env)
    return ({'ok': True, 'name': user['name'], 'affiliation': user['affiliation'],
             'time': now, 'weeks': weeks}, 200)


def bulk_checkin(names, mode=None, env=None):
    """이름 목록을 받아 1차 분류. 유일하면 바로 출석, 동명이인이면 후보 반환.

    반환: (응답 dict, HTTP 상태 코드)
    """
    env = env or SERVER_ENV
    conn = db()
    try:
        mode = mode or get_current_mode(conn)
        today, now = _now_parts()
        ambiguous = []
        marked = []
        not_found = []
        for i, nm in enumerate(names):
            users = user_model.find_users_by_name(conn, nm)
            if not users:
                not_found.append({'index': i, 'name': nm})
            elif len(users) == 1:
                marked.append(_mark_user_attendance(conn, users[0]['id'], nm, today, now, mode, env))
            else:
                ambiguous.append({'index': i, 'name': nm, 'candidates': users})
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
    safe_refresh(mode, env)
    return ({
        'ok': True,
        'need_resolution': bool(ambiguous),
        'count': len(names),
        'marked': marked,
        'ambiguous': ambiguous,
        'not_found': not_found,
    }, 200)


def process_bulk_with_choices(names, choices, mode=None, env=None):
    """2차 호출: 사용자가 선택한 동명이인만 출석 처리한다.

    반환: (응답 dict, HTTP 상태 코드)
    """
    env = env or SERVER_ENV
    conn = db()
    try:
        mode = mode or get_current_mode(conn)
        today, now = _now_parts()
        marked = []
        for idx_str, uid in choices.items():
            try:
                idx = int(idx_str)
                uid = int(uid)
            except (TypeError, ValueError):
                continue
            if 0 <= idx < len(names):
                marked.append(_mark_user_attendance(conn, uid, names[idx], today, now, mode, env))
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
    safe_refresh(mode, env)
    return ({'ok': True, 'done': True, 'marked': marked}, 200)


def cancel_checkin(aid, env=None):
    """관리자가 출석 기록을 강제 취소한다. DB에서 제거.

    반환: (응답 dict, HTTP 상태 코드)
    """
    env = env or SERVER_ENV
    conn = db()
    try:
        row = attendance_model.get_attendance_by_id_env(conn, aid, env)
        if not row:
            return ({'ok': False, 'msg': '해당 출석 기록이 없습니다.'}, 404)
        attendance_model.delete_attendance(conn, aid)
        conn.commit()
        mode = row['mode'] or 'sunday'
        row_env = row['env'] or env
        date = row['check_date']
        name = row['name']
    finally:
        conn.close()
    safe_refresh(mode, row_env, date_str=date)
    return ({'ok': True, 'name': name, 'date': date}, 200)


def admin_add_attendance(name, user_id, date, time_str, mode=None, env=None):
    """관리자가 임의 날짜·시각의 출석 기록을 추가한다.

    1차 호출(name 전달) - 이름으로 선택: 유일하면 바로 출석, 동명이인이면 후보 반환,
    명단에 없으면 오류. 2차 호출(user_id 전달) - 동명이인 중 특정 사용자 지정 출석.
    모드는 날짜의 요일로 자동 판별하며, 지정 시 해당 모드를 사용한다.

    반환: (응답 dict, HTTP 상태 코드)
    """
    env = env or SERVER_ENV
    try:
        datetime.date.fromisoformat(date)
    except (ValueError, TypeError):
        return ({'ok': False, 'msg': '날짜를 올바르게 입력하세요. (YYYY-MM-DD)'}, 400)
    if not re.match(r'^([01]\d|2[0-3]):[0-5]\d$', time_str) and \
       not re.match(r'^([01]\d|2[0-3]):[0-5]\d:[0-5]\d$', time_str):
        return ({'ok': False, 'msg': '시각을 HH:MM 또는 HH:MM:SS 형식으로 입력하세요. (예: 10:30)'}, 400)
    if not user_id and not name:
        return ({'ok': False, 'msg': '추가할 이름을 입력하세요.'}, 400)

    conn = db()
    u_name = name
    try:
        if mode not in ('sunday', 'wednesday'):
            mode = mode_for_date(date) or get_current_mode(conn)

        # 1차: 이름으로 해석 (동명이인 확인)
        if not user_id:
            users = user_model.find_users_by_name(conn, name)
            if not users:
                return ({'ok': False, 'msg': "'%s'은(는) 명단에 없는 이름입니다." % name}, 404)
            if len(users) > 1:
                return ({'ok': True, 'need_resolution': True, 'name': name, 'ambiguous': users}, 200)
            user_id = users[0]['id']

        user = user_model.get_user(conn, user_id)
        if not user:
            return ({'ok': False, 'msg': '존재하지 않는 사용자입니다.'}, 404)
        dup = attendance_model.get_attendance(conn, user_id, date, mode, env)
        if dup:
            return ({'ok': False, 'msg': '%s님은 해당 날짜에 이미 출석 기록이 있습니다. (%s)'
                     % (user['name'], dup['check_time'])}, 409)
        check_time = time_str if re.match(r'^([01]\d|2[0-3]):[0-5]\d:[0-5]\d$', time_str) \
            else time_str + ':00'
        try:
            attendance_model.create_attendance(
                conn, user_id, user['name'], user['affiliation'], date, check_time, mode, env)
        except sqlite3.IntegrityError:
            return ({'ok': False, 'msg': '%s님은 해당 날짜에 이미 출석 기록이 있습니다.' % user['name']}, 409)
        conn.commit()
        u_name = user['name']
    finally:
        conn.close()
    safe_refresh(mode, env, date_str=date)
    return ({'ok': True, 'name': u_name, 'date': date, 'time': time_str, 'mode': mode}, 200)


def delete_admin_attendance(aid, env=None):
    """관리자가 임의 추가한 출석 기록(어떤 날짜든)을 삭제한다.

    cancel_checkin과 동일 동작. 반환: (응답 dict, HTTP 상태 코드)
    """
    return cancel_checkin(aid, env=env)


def list_attendance(date, mode, env=None):
    """지정 날짜 또는 최근 전체의 출석 기록 목록을 반환한다. (커밋 없음, 조회 전용)

    반환: dict 목록
    """
    env = env or SERVER_ENV
    conn = db()
    try:
        if mode not in ('sunday', 'wednesday'):
            mode = mode_for_date(date) or get_current_mode(conn)
        if date and date.strip():
            rows = attendance_model.get_attendance_by_date(conn, date, mode, env)
        else:
            rows = attendance_model.get_attendance_recent(conn, mode, env)
    finally:
        conn.close()
    return rows
