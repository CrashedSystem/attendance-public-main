# -*- coding: utf-8 -*-
"""보고서/내보내기/종료 라우트.

- GET  /api/report              - 웹 보고서(그래프 HTML) 열기
- GET  /api/report/a4           - A4 대응 보고서 열기
- GET  /api/admin/report        - 지정 날짜 기준 관리자 보고서
- POST /api/admin/export-teams  - 팀별 보고서 HTML/PNG 내보내기
- POST /api/admin/shutdown      - 웹 보고서 저장 후 서버 종료
"""
import datetime
import os
import threading
import time

from flask import Blueprint, jsonify, request, send_from_directory

from config import BASE_DIR, SERVER_ENV
from models.database import db
from models.settings import get_current_mode, mode_for_date
from services import report_service
from utils import decorators

bp = Blueprint('report', __name__)


def _resolve_mode(arg_mode):
    """파라미터 모드가 유효하면 그대로, 아니면 DB(settings)의 현재 모드를 반환한다."""
    if arg_mode in ('sunday', 'wednesday'):
        return arg_mode
    conn = db()
    mode = get_current_mode(conn)
    conn.close()
    return mode


def _resolve_date_mode(arg_mode, date_str):
    """모드가 유효하지 않으면 날짜 요일로 판별하고, 그래도 없으면 현재 모드를 반환한다."""
    if arg_mode in ('sunday', 'wednesday'):
        return arg_mode
    m = mode_for_date(date_str) if date_str else None
    if m:
        return m
    conn = db()
    mode = get_current_mode(conn)
    conn.close()
    return mode


@bp.route('/api/report')
@decorators.require_admin_pin
def download_report():
    """웹 보고서(출석_그래프.html)를 DB 기준으로 갱신하고 화면에 띄운다.

    date/mode 파라미터는 호환용으로 받되, 모드별 최신 서비스일 기준으로 갱신한다.
    """
    date_str = (request.args.get('date') or '').strip()
    try:
        datetime.date.fromisoformat(date_str)
    except ValueError:
        date_str = None
    mode = _resolve_mode((request.args.get('mode') or '').strip())
    try:
        report_service.safe_refresh(mode, SERVER_ENV)
    except Exception as e:
        return jsonify({'ok': False, 'msg': '보고서 생성 실패: %s' % e}), 500
    return send_from_directory(BASE_DIR, '출석_그래프_%s.html' % SERVER_ENV)


@bp.route('/api/report/a4')
@decorators.require_admin_pin
def download_a4_report():
    """웹 보고서를 갱신 후 띄운다."""
    mode = _resolve_mode((request.args.get('mode') or '').strip())
    try:
        report_service.safe_refresh(mode, SERVER_ENV)
    except Exception as e:
        return jsonify({'ok': False, 'msg': '보고서 생성 실패: %s' % e}), 500
    return send_from_directory(BASE_DIR, '출석_그래프_%s.html' % SERVER_ENV)


@bp.route('/api/admin/report')
@decorators.require_admin_pin
def admin_report_date():
    """지정 날짜(mode) 기준 출석 보고서를 생성해 화면에 띄운다."""
    date_str = (request.args.get('date') or '').strip()
    mode = _resolve_date_mode((request.args.get('mode') or '').strip(), date_str)
    try:
        main_path = report_service.refresh_report(
            mode, SERVER_ENV, date_str=date_str if date_str else None)
    except Exception as e:
        return jsonify({'ok': False, 'msg': '보고서 생성 실패: %s' % e}), 500
    return send_from_directory(BASE_DIR, os.path.basename(main_path))


@bp.route('/api/admin/export-teams', methods=['POST'])
@decorators.require_admin_pin
def admin_export_teams():
    """팀별 상세 보고서 HTML 파일들을 수동으로 생성/내보내기 한다."""
    mode = _resolve_mode((request.args.get('mode') or '').strip())
    try:
        report_service.safe_refresh(mode, SERVER_ENV)
        report_service.render_png(mode, SERVER_ENV)
        archive_dir = os.path.join(BASE_DIR, 'data', '통계_%s' % SERVER_ENV, 'teams')
        return jsonify({'ok': True, 'dir': archive_dir})
    except Exception as e:
        return jsonify({'ok': False, 'msg': '팀별 보고서 내보내기 실패: %s' % e}), 500


@bp.route('/api/admin/shutdown', methods=['POST'])
@decorators.require_admin_pin
def admin_shutdown():
    """웹 보고서를 갱신한 뒤 서버를 종료한다. (현재 모드 기준)"""
    conn = db()
    mode = get_current_mode(conn)
    conn.close()
    report = os.path.join(BASE_DIR, '출석_그래프_%s.html' % SERVER_ENV)
    try:
        report_service.safe_refresh(mode, SERVER_ENV)
    except Exception as e:
        return jsonify({'ok': False, 'msg': '보고서 생성 실패: %s' % e}), 500

    # 배포용 PNG 생성(최선 노력) 후 종료
    def _finish():
        try:
            report_service.render_png(mode, SERVER_ENV)
        except Exception:
            pass
        time.sleep(1.5)
        os._exit(0)
    threading.Thread(target=_finish, daemon=True).start()
    return jsonify({'ok': True, 'report': report, 'mode': mode, 'env': SERVER_ENV})
