# -*- coding: utf-8 -*-
"""서버 실행 제어 모듈.

app.py에서 make_server 인스턴스를 등록하고, 보고서 종료 라우트가 정상 종료를 요청한다.
Werkzeug의 wsgi server.shutdown()은 소켓을 닫아 서버 루프를 정상 종료시켜
atexit 파이널라이저 실행을 보장한다. (os._exit 및 Windows SIGTERM 강제 종료 회피)
"""

_server = None
_shutdown_requested = False


def register_server(server):
    """make_server 인스턴스를 등록한다."""
    global _server
    _server = server


def shutdown_server():
    """서버를 정상 종료시킨다. 서버 미등록 시 False를 반환한다."""
    global _shutdown_requested
    _shutdown_requested = True
    srv = _server
    if srv is None:
        return False
    try:
        srv.shutdown()
        return True
    except Exception:
        return False