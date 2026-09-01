# -*- coding: utf-8 -*-
"""공개(게스트) API 라우트.

- 현재 모드 조회
- 사용자 검색
- 출석 처리(체크인)
- 오늘 출석 / 최근 출석 기록 조회
"""
import datetime
import threading
import time

from flask import Blueprint, jsonify, request

from config import SERVER_ENV
from models import attendance as attendance_model
from models.database import db
from models.settings import get_current_mode
from services import attendance_service, user_service

bp = Blueprint('public', __name__)

# 체크인 rate limiting (키오스크 오남용/플러드 방지). 메모리 내 고정 60초 창 계수.
_RATE_MAX = 20
_RATE_WINDOW = 60.0
_RATE_MAX_KEYS = 1000
_rate_lock = threading.Lock()
_rate_hits = {}


def _rate_allowed(key):
    """key 기준으로 현재 창의 요청 수가 상한을 넘지 않았으면 True. 넘었으면 False.

    창 경계에서 키가 조기 리셋되는 문제를 막기 위해, 키별로 자체 창 스탬프를 유지해
    경계를 넘어도 카운터를 유지한다. (한꺼번에 전체 stale 키를 삭제하지 않는다)
    """
    now = time.time()
    with _rate_lock:
        cur_stamp = int(now // _RATE_WINDOW)
        if key not in _rate_hits:
            # 키 수가 과도하게 늘지 않도록 상한을 넘으면 가장 오래된 항목부터 정리한다.
            if len(_rate_hits) >= _RATE_MAX_KEYS:
                old = min(_rate_hits, key=lambda k: _rate_hits[k][0])
                del _rate_hits[old]
            _rate_hits[key] = (cur_stamp, [])
        stamp, hits = _rate_hits[key]
        if stamp != cur_stamp:
            # 새 창으로 전환되면 카운터 초기화
            stamp = cur_stamp
            hits = []
            _rate_hits[key] = (stamp, hits)
        if len(hits) >= _RATE_MAX:
            return False
        hits.append(now)
        return True


@bp.route('/api/mode')
def api_get_mode():
    """현재 서비스 모드와 서버 환경을 반환한다."""
    conn = db()
    try:
        mode = get_current_mode(conn)
    finally:
        conn.close()
    return jsonify({'mode': mode, 'env': SERVER_ENV})


@bp.route('/api/users/search')
def search_users():
    """사용자 검색. q(빈값=전체), mode 파라미터 지원.

    동작: 숫자(정확id·이름포함), 한글 초성, 일반 텍스트(이름·소속·팀 순위) 검색.
    """
    q = request.args.get('q', '') or ''
    mode = request.args.get('mode', '') or ''
    users = user_service.search_users_with_mode(q, mode)
    return jsonify(users)


@bp.route('/api/checkin', methods=['POST'])
def checkin():
    """사용자 id로 출석 처리한다."""
    data = request.get_json(silent=True) or {}
    uid = data.get('user_id')
    try:
        uid = int(uid)
        if uid <= 0:
            raise ValueError
    except (TypeError, ValueError):
        return jsonify({'ok': False, 'msg': '사용자를 선택해주세요.'}), 400
    if not _rate_allowed('checkin:%s' % uid):
        return jsonify({'ok': False, 'msg': '요청이 너무 잦습니다. 잠시 후 다시 시도해주세요.'}), 429
    resp, code = attendance_service.process_checkin(uid)
    return jsonify(resp), code


@bp.route('/api/attendance/today')
def attendance_today():
    """오늘 날짜의 전체 출석 기록(출석 시각순)을 반환한다."""
    conn = db()
    try:
        today = datetime.date.today().isoformat()
        resp = attendance_model.get_today_attendance(conn, today, SERVER_ENV)
    finally:
        conn.close()
    return jsonify(resp)


@bp.route('/api/attendance/history')
def attendance_history():
    """최근 출석 기록 전체(최신순, 최대 500건)를 반환한다."""
    conn = db()
    try:
        resp = attendance_model.get_attendance_history(conn, SERVER_ENV)
    finally:
        conn.close()
    return jsonify(resp)
