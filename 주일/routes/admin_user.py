# -*- coding: utf-8 -*-
"""관리자 사용자 관리 라우트.

- GET/POST  /api/admin/users              - 목록 조회/생성
- PUT/DELETE /api/admin/users/<id>        - 수정/삭제
- GET  /api/admin/users/archive           - 아카이브 목록
- POST /api/admin/users/archive/<id>/restore - 복원
- GET  /api/admin/teams-affiliations      - 팀↔소속 매핑
"""
from flask import Blueprint, jsonify, request

from config import SERVER_ENV
from models import user as user_model
from models.database import db
from services import report_service, team_service, user_service
from utils import decorators

bp = Blueprint('admin_user', __name__)


@bp.route('/api/admin/users')
@decorators.require_admin_pin
def admin_users():
    """모든 사용자 목록을 조회한다. (전역자 정리 포함)"""
    conn = db()
    try:
        user_model.prune_expired_users(conn)
        rows = user_model.get_all_users(conn)
    finally:
        conn.close()
    return jsonify(rows)


@bp.route('/api/admin/users', methods=['POST'])
@decorators.require_admin_pin
def admin_create_user():
    """사용자를 생성한다. (이름 필수, 비고·생일 정규화, 군종 여부 반영)"""
    d = request.get_json(silent=True) or {}
    ok, msg = user_service.validate_user_data(d)
    if not ok:
        return jsonify({'ok': False, 'msg': msg}), 400
    d['note'] = user_service.normalize_newbie_note(d.get('note'))
    d['birthday'] = user_service.norm_birthday(d.get('birthday'))
    try:
        d['is_chaplain'] = 1 if int(d.get('is_chaplain') or 0) else 0
    except (TypeError, ValueError):
        d['is_chaplain'] = 0
    conn = db()
    try:
        user_id = user_model.create_user(conn, d)
        conn.commit()
    finally:
        conn.close()
    report_service.safe_refresh()
    return jsonify({'ok': True, 'id': user_id})


@bp.route('/api/admin/users/<int:uid>', methods=['PUT'])
@decorators.require_admin_pin
def admin_update_user(uid):
    """사용자 정보를 갱신한다. (이름 필수, 비고·생일 정규화, 군종 여부 반영)"""
    d = request.get_json(silent=True) or {}
    ok, msg = user_service.validate_user_data(d)
    if not ok:
        return jsonify({'ok': False, 'msg': msg}), 400
    d['note'] = user_service.normalize_newbie_note(d.get('note'))
    d['birthday'] = user_service.norm_birthday(d.get('birthday'))
    try:
        d['is_chaplain'] = 1 if int(d.get('is_chaplain') or 0) else 0
    except (TypeError, ValueError):
        d['is_chaplain'] = 0
    conn = db()
    try:
        if not user_model.get_user(conn, uid):
            return jsonify({'ok': False, 'msg': '사용자가 없습니다.'}), 404
        user_model.update_user(conn, uid, d)
        conn.commit()
    finally:
        conn.close()
    report_service.safe_refresh()
    return jsonify({'ok': True})


@bp.route('/api/admin/users/<int:uid>', methods=['DELETE'])
@decorators.require_admin_pin
def admin_delete_user(uid):
    """명단에서 삭제한다. 수동 삭제도 users_archive로 백업해 추적·복원 가능하게 한다."""
    conn = db()
    try:
        row = user_model.get_user(conn, uid)
        if not row:
            return jsonify({'ok': False, 'msg': '사용자가 없습니다.'}), 404
        user_model.archive_user(conn, row)
        user_model.delete_user(conn, uid)
        conn.commit()
    finally:
        conn.close()
    report_service.safe_refresh()
    return jsonify({'ok': True})


@bp.route('/api/admin/users/archive')
@decorators.require_admin_pin
def admin_archived_users():
    """전역일로 인해 아카이브된 사용자 목록."""
    rows = user_model.get_archived_users()
    return jsonify(rows)


@bp.route('/api/admin/users/archive/<int:uid>/restore', methods=['POST'])
@decorators.require_admin_pin
def admin_restore_user(uid):
    """아카이브된 사용자를 명단으로 복원한다."""
    conn = db()
    try:
        row = user_model.restore_user(conn, uid)
    finally:
        conn.close()
    if not row:
        return jsonify({'ok': False, 'msg': '아카이브에 해당 사용자가 없습니다.'}), 404
    report_service.safe_refresh()
    return jsonify({'ok': True, 'name': row['name']})


@bp.route('/api/admin/teams-affiliations')
@decorators.require_admin_pin
def admin_teams_affiliations():
    """소속→팀 매핑을 반환한다. (다수결 대표 팀 + custom 팀/소속 포함)"""
    return jsonify(team_service.get_teams_affiliations_mapping())
