# -*- coding: utf-8 -*-
"""Flask 앱 진입점.

- Flask 앱 생성 및 정적 파일 설정
- 블루프린트 등록 (routes/*)
- init_db() 호출 (스키마/마이그레이션)
- 루트(/) 인덱스 라우트
"""
from flask import Flask, send_from_directory
from werkzeug.serving import make_server

from config import BASE_DIR
from models.database import init_db
from routes import (admin_absence, admin_attendance, admin_auth,
                    admin_import, admin_team, admin_time, admin_user,
                    public, report)
from server_ctl import register_server

app = Flask(__name__, static_folder='static', static_url_path='/static')


# ---------------------------------------------------------------------------
# 블루프린트 등록
# ---------------------------------------------------------------------------
app.register_blueprint(public.bp)
app.register_blueprint(admin_auth.bp)
app.register_blueprint(admin_user.bp)
app.register_blueprint(admin_attendance.bp)
app.register_blueprint(admin_team.bp)
app.register_blueprint(admin_import.bp)
app.register_blueprint(admin_absence.bp)
app.register_blueprint(admin_time.bp)
app.register_blueprint(report.bp)


# ---------------------------------------------------------------------------
# 기본 라우트
# ---------------------------------------------------------------------------
@app.route('/')
def index():
    """키오스크 메인 화면(index.html)을 제공한다."""
    return send_from_directory(app.static_folder, 'index.html')


# ---------------------------------------------------------------------------
# 초기화 및 실행
# ---------------------------------------------------------------------------
init_db()

if __name__ == '__main__':
    _server = make_server('127.0.0.1', 8000, app)
    register_server(_server)
    try:
        _server.serve_forever()
    finally:
        # 정상 종료: 서버 루프 종료 후 파이널라이저가 flush/atexit를 처리한다.
        import sys
        sys.stdout.flush()
        sys.stderr.flush()
