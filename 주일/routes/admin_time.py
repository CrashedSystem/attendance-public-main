# -*- coding: utf-8 -*-
"""관리자 시간 관리 라우트.

- GET  /api/admin/time       - 시스템/인터넷 시간 조회
- POST /api/admin/sync-time  - 인터넷 시간으로 시스템 시간 동기화
"""
from flask import Blueprint, jsonify

from services import time_service
from utils import decorators

bp = Blueprint('admin_time', __name__)


@bp.route('/api/admin/time', methods=['GET'])
@decorators.require_admin_pin
def admin_get_time():
    """현재 시스템(로컬) 시간과 인터넷(NTP) 시간을 표시한다. (읽기 전용, 시간 변경 없음)"""
    return jsonify(time_service.get_time_info())


@bp.route('/api/admin/sync-time', methods=['POST'])
@decorators.require_admin_pin
def admin_sync_time():
    """인터넷(NTP) 시간을 받아 컴퓨터 시스템 시간을 동기화한다."""
    resp, code = time_service.sync_time()
    return jsonify(resp), code
