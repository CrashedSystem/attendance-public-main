# -*- coding: utf-8 -*-
"""공개(게스트) API 라우트.

- 현재 모드 조회
- 사용자 검색
- 출석 처리(체크인)
- 오늘 출석 / 최근 출석 기록 조회
"""
import datetime

from flask import Blueprint, jsonify, request

from config import SERVER_ENV
from models import attendance as attendance_model
from models.database import db
from models.settings import get_current_mode
from services import attendance_service, user_service

bp = Blueprint('public', __name__)


@bp.route('/api/mode')
def api_get_mode():
    """현재 서비스 모드와 서버 환경을 반환한다."""
    conn = db()
    mode = get_current_mode(conn)
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
    resp, code = attendance_service.process_checkin(uid)
    return jsonify(resp), code


@bp.route('/api/attendance/today')
def attendance_today():
    """오늘 날짜의 전체 출석 기록(출석 시각순)을 반환한다."""
    conn = db()
    today = datetime.date.today().isoformat()
    resp = attendance_model.get_today_attendance(conn, today, SERVER_ENV)
    conn.close()
    return jsonify(resp)


@bp.route('/api/attendance/history')
def attendance_history():
    """최근 출석 기록 전체(최신순, 최대 500건)를 반환한다."""
    conn = db()
    resp = attendance_model.get_attendance_history(conn, SERVER_ENV)
    conn.close()
    return jsonify(resp)
