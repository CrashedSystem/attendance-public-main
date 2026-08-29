# -*- coding: utf-8 -*-
"""관리자 결석 관리 라우트.

- GET    /api/admin/absences         - 미출석 군종병 및 결석 사유 조회
- POST   /api/admin/absences         - 결석 사유 저장/수정
- DELETE /api/admin/absences/<id>    - 결석 사유 삭제
"""
from flask import Blueprint, jsonify, request

from config import SERVER_ENV
from services import absence_service
from utils import decorators

bp = Blueprint('admin_absence', __name__)


@bp.route('/api/admin/absences')
@decorators.require_admin_pin
def admin_absences():
    """지정된 날짜(수요일)의 미출석 군종병과 기등록 결석 사유를 조회한다."""
    date_str = (request.args.get('date') or '').strip()
    mode = request.args.get('mode') or 'wednesday'
    env = request.args.get('env') or SERVER_ENV
    resp = absence_service.get_absentees_for_date(date_str, mode, env)
    return jsonify(resp)


@bp.route('/api/admin/absences', methods=['POST'])
@decorators.require_admin_pin
def admin_absence_upsert():
    """수요일 결석 사유를 저장/수정한다. (user_id, check_date, mode, env) 중복 시 덮어쓴다."""
    d = request.get_json(silent=True) or {}
    resp, code = absence_service.save_absence_reason(
        d.get('user_id'), (d.get('date') or '').strip(), d.get('reason'),
        d.get('mode') or 'wednesday', d.get('env') or SERVER_ENV)
    return jsonify(resp), code


@bp.route('/api/admin/absences/<int:aid>', methods=['DELETE'])
@decorators.require_admin_pin
def admin_absence_delete(aid):
    """등록된 결석 사유를 삭제한다."""
    resp, code = absence_service.delete_absence(aid)
    return jsonify(resp), code
