# -*- coding: utf-8 -*-
"""관리자 인증/모드 라우트.

- POST /api/admin/login - PIN 인증
- GET  /api/admin/mode  - 현재 모드 조회
- POST /api/admin/mode  - 서비스 모드 변경
"""
from flask import Blueprint, jsonify, request

from config import SERVER_ENV
from models import settings as settings_model
from models.database import db
from services import report_service
from utils import validators, decorators

bp = Blueprint('admin_auth', __name__)


@bp.route('/api/admin/login', methods=['POST'])
def admin_login():
    """관리자 PIN 인증."""
    data = request.get_json(silent=True) or {}
    ok, msg = validators.validate_pin(data.get('pin'))
    if ok:
        return jsonify({'ok': True})
    return jsonify({'ok': False, 'msg': msg}), 401


@bp.route('/api/admin/mode', methods=['GET'])
@decorators.require_admin_pin
def admin_get_mode():
    """현재 서비스 모드와 서버 환경을 반환한다."""
    conn = db()
    try:
        mode = settings_model.get_current_mode(conn)
    finally:
        conn.close()
    return jsonify({'mode': mode, 'env': SERVER_ENV})


@bp.route('/api/admin/mode', methods=['POST'])
@decorators.require_admin_pin
def api_set_mode():
    """서비스 모드를 sunday|wednesday로 변경하고 보고서를 갱신한다."""
    data = request.get_json(silent=True) or {}
    mode = data.get('mode') or ''
    ok, msg = validators.validate_mode(mode)
    if not ok:
        return jsonify({'ok': False, 'msg': msg}), 400
    conn = db()
    try:
        settings_model.set_current_mode(conn, mode)
    finally:
        conn.close()
    report_service.safe_refresh(mode, SERVER_ENV)
    return jsonify({'ok': True, 'mode': mode})
