# -*- coding: utf-8 -*-
"""관리자 데이터 임포트(과거 엑셀 등) 라우트.

- GET  /api/admin/import/template  - 작성용 .xlsx 템플릿 다운로드
- POST /api/admin/import/preview   - 업로드 파일 파싱 + 적용 예상 요약(token 발급)
- POST /api/admin/import/commit    - 미리보기 token 기준 DB 반영
"""
import io

from flask import Blueprint, jsonify, request, send_file

from services import import_service
from utils import decorators

bp = Blueprint('admin_import', __name__)


@bp.route('/api/admin/import/template', methods=['GET'])
@decorators.require_admin_pin
def api_get_import_template():
    """임포트용 엑셀 템플릿을 생성해 다운로드한다."""
    data = import_service.build_template_bytes()
    return send_file(
        io.BytesIO(data),
        mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        as_attachment=True,
        download_name='신우_임포트_템플릿.xlsx')


@bp.route('/api/admin/import/preview', methods=['POST'])
@decorators.require_admin_pin
def api_import_preview():
    """업로드된 파일을 파싱해 임포트 예상 결과를 반환한다."""
    f = request.files.get('file')
    if not f or not f.filename:
        return jsonify({'ok': False, 'msg': '파일을 선택해주세요.'}), 400
    raw = f.read()
    if not raw:
        return jsonify({'ok': False, 'msg': '파일이 비어 있습니다.'}), 400
    ok, resp = import_service.build_preview(f.filename, raw)
    if not ok:
        return jsonify(resp), 400
    return jsonify(resp), 200


@bp.route('/api/admin/import/commit', methods=['POST'])
@decorators.require_admin_pin
def api_import_commit():
    """미리보기 결과를 실제 DB에 반영한다."""
    d = request.get_json(silent=True) or {}
    ok, resp = import_service.commit(d.get('token'))
    if not ok:
        return jsonify(resp), 400
    return jsonify(resp), 200