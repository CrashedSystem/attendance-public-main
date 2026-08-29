# -*- coding: utf-8 -*-
"""관리자 출석 관리 라우트.

- POST   /api/attendance/bulk           - 이름 일괄 출석 (동명이인 해결 포함)
- DELETE /api/attendance/<id>           - 출석 강제 취소
- GET    /api/admin/attendance/list     - 날짜별 출석 목록 조회
- POST   /api/admin/attendance          - 임의 날짜·시각 출석 추가
- DELETE /api/admin/attendance/<id>     - 임의 추가 출석 삭제
"""
from flask import Blueprint, jsonify, request

from services import attendance_service
from utils import decorators

bp = Blueprint('admin_attendance', __name__)


@bp.route('/api/attendance/bulk', methods=['POST'])
@decorators.require_admin_pin
def bulk_checkin():
    """이름 목록을 받아 일괄 출석 처리한다.

    1차 호출(names만): 이름이 유일하면 바로 출석, 중복(동명이인)이면 후보 목록을 반환해
    사용자가 직접 올바른 사람을 선택하게 한다. 이름이 없으면 미발견으로 표시.
    2차 호출(names + choices{인덱스: user_id}): 선택된 동명이인만 출석 처리한다.
    """
    data = request.get_json(silent=True) or {}
    raw_names = data.get('names') or []
    choices = data.get('choices') or {}
    names = [n.strip() for n in raw_names if n and n.strip()]

    if choices:
        resp, code = attendance_service.process_bulk_with_choices(names, choices)
    else:
        resp, code = attendance_service.bulk_checkin(names)
    return jsonify(resp), code


@bp.route('/api/attendance/<int:aid>', methods=['DELETE'])
@decorators.require_admin_pin
def admin_cancel_attendance(aid):
    """관리자가 출석 기록을 강제 취소한다. DB에서 제거."""
    resp, code = attendance_service.cancel_checkin(aid)
    return jsonify(resp), code


@bp.route('/api/admin/attendance/list')
@decorators.require_admin_pin
def admin_attendance_list():
    """지정 날짜의 출석 기록 목록을 반환한다. (date 파라미터 필수)"""
    date = request.args.get('date', '') or ''
    mode = request.args.get('mode', '') or ''
    rows = attendance_service.list_attendance(date, mode)
    return jsonify(rows)


@bp.route('/api/admin/attendance', methods=['POST'])
@decorators.require_admin_pin
def admin_add_attendance():
    """관리자가 임의 날짜·시각의 출석 기록을 추가한다.

    1차 호출(name 전달) - 이름으로 선택, 2차 호출(user_id 전달) - 동명이인 중 특정 사용자 지정.
    모드는 날짜의 요일로 자동 판별(일요일/수요일)하며, 지정 시 해당 모드를 사용한다.
    """
    data = request.get_json(silent=True) or {}
    name = (data.get('name') or '').strip()
    user_id = data.get('user_id')
    mode = (data.get('mode') or '').strip()
    resp, code = attendance_service.admin_add_attendance(
        name, user_id, (data.get('date') or '').strip(),
        (data.get('time') or '').strip(), mode or None)
    return jsonify(resp), code


@bp.route('/api/admin/attendance/<int:aid>', methods=['DELETE'])
@decorators.require_admin_pin
def admin_delete_attendance(aid):
    """관리자가 임의 추가한 출석 기록(어떤 날짜든)을 삭제한다."""
    resp, code = attendance_service.delete_admin_attendance(aid)
    return jsonify(resp), code
