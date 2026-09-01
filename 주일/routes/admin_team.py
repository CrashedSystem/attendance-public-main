# -*- coding: utf-8 -*-
"""관리자 팀/소속 관리 라우트.

- POST /api/admin/teams/bulk-move        - 소속 전체 팀 이동
- POST /api/admin/teams/rename           - 팀 이름 변경
- POST /api/admin/teams/create           - 새 팀 생성
- POST /api/admin/teams/delete           - 팀 삭제
- POST /api/admin/affiliations/rename    - 소속 이름 변경
- POST /api/admin/affiliations/create    - 임시 소속 생성
- GET/POST /api/admin/newbie-days        - 새신우 유지 기간 조회/설정
"""
from flask import Blueprint, jsonify, request

from services import team_service
from utils import decorators

bp = Blueprint('admin_team', __name__)


@bp.route('/api/admin/teams/bulk-move', methods=['POST'])
@decorators.require_admin_pin
def admin_bulk_move_team():
    """특정 소속의 모든 사용자를 특정 팀으로 일괄 이동. 통계에 즉시 반영."""
    d = request.get_json(silent=True) or {}
    resp, code = team_service.bulk_move_team(d.get('affiliation'), d.get('team'))
    return jsonify(resp), code


@bp.route('/api/admin/teams/rename', methods=['POST'])
@decorators.require_admin_pin
def admin_rename_team():
    """기존 팀의 이름을 변경한다. 소속된 모든 사용자와 통계에 즉시 반영."""
    d = request.get_json(silent=True) or {}
    resp, code = team_service.rename_team(d.get('old_name'), d.get('new_name'))
    return jsonify(resp), code


@bp.route('/api/admin/teams/create', methods=['POST'])
@decorators.require_admin_pin
def admin_create_team():
    """새 팀을 등록한다. 인원이 없어도 드롭다운에 바로 표시된다."""
    d = request.get_json(silent=True) or {}
    resp, code = team_service.create_team(d.get('name'))
    return jsonify(resp), code


@bp.route('/api/admin/teams/delete', methods=['POST'])
@decorators.require_admin_pin
def admin_delete_team():
    """팀을 삭제한다. 인원이 남아 있으면 거부하고, 비어 있는 팀만 삭제한다."""
    d = request.get_json(silent=True) or {}
    resp, code = team_service.delete_team(d.get('name'))
    return jsonify(resp), code


@bp.route('/api/admin/affiliations/rename', methods=['POST'])
@decorators.require_admin_pin
def admin_rename_affiliation():
    """소속 이름을 변경한다. 소속된 모든 사용자에게 즉시 반영."""
    d = request.get_json(silent=True) or {}
    resp, code = team_service.rename_affiliation(d.get('old_name'), d.get('new_name'))
    return jsonify(resp), code


@bp.route('/api/admin/affiliations/create', methods=['POST'])
@decorators.require_admin_pin
def admin_create_affiliation():
    """임시 소속을 추가한다. (아직 인원이 없는 소속)"""
    d = request.get_json(silent=True) or {}
    resp, code = team_service.create_affiliation(d.get('name'))
    return jsonify(resp), code


@bp.route('/api/admin/newbie-days', methods=['GET'])
@decorators.require_admin_pin
def api_get_newbie_days():
    """새신우 유지 기간(일) 조회. 기본 30."""
    return jsonify({'days': team_service.get_newbie_days()})


@bp.route('/api/admin/newbie-days', methods=['POST'])
@decorators.require_admin_pin
def api_set_newbie_days():
    """새신우 유지 기간(일) 변경. 1~365일."""
    d = request.get_json(silent=True) or {}
    resp, code = team_service.set_newbie_days(d.get('days'))
    return jsonify(resp), code


@bp.route('/api/admin/sunday-detail-threshold', methods=['GET'])
@decorators.require_admin_pin
def api_get_sunday_detail_threshold():
    """일요일 보고서 전체 출석자 상세 명단 표시 기준(명) 조회. 기본 30."""
    return jsonify({'sundayDetailThreshold': team_service.get_sunday_detail_threshold()})


@bp.route('/api/admin/sunday-detail-threshold', methods=['POST'])
@decorators.require_admin_pin
def api_set_sunday_detail_threshold():
    """일요일 보고서 상세 명단 표시 기준(명) 변경. 1~999."""
    d = request.get_json(silent=True) or {}
    resp, code = team_service.set_sunday_detail_threshold(d.get('threshold'))
    return jsonify(resp), code
