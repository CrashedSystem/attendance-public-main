# -*- coding: utf-8 -*-
"""출석 키오스크 원터치 실행 프로그램 (Windows kiosk.exe 진입점).

1) 이전에 떠 있는 키오스크 서버 종료 (포트 충돌 방지)
2) 시작 직전 DB 를 backups/군종_*.db.bak 로 백업
3) Flask 서버 기동 (포트 8665, 환경변수 KIOSK_PORT 로 변경 가능)
4) 전체화면 브라우저(Edge→Chrome)로 키오스크 화면 열기
5) 브라우저를 닫으면 서버도 함께 정상 종료, 보고서의 '종료' 버튼으로도 종료 가능

EXE 로 만드는 방법: build_exe.bat 실행 → dist/kiosk.exe
PNG 보고서: Chromium이 exe 안에 포함되어 있어 추가 설치 없이 동작합니다.
"""
import logging
import os
import socket
import subprocess
import sys
import threading
import time

FROZEN = getattr(sys, 'frozen', False)
PROG_DIR = os.path.dirname(os.path.abspath(sys.executable if FROZEN else __file__))
LOG_PATH = os.path.join(PROG_DIR, 'kiosk.log')

logging.basicConfig(
    filename=LOG_PATH, encoding='utf-8', level=logging.INFO,
    format='%(asctime)s %(levelname)s %(message)s',
)
log = logging.getLogger('kiosk')


def _excepthook(typ, val, tb):
    import traceback
    log.error('치명 오류:\n%s', ''.join(traceback.format_exception(typ, val, tb)))
    try:
        import ctypes
        ctypes.windll.user32.MessageBoxW(0, str(val), '키오스크 오류', 0x10)
    except Exception:
        pass


sys.excepthook = _excepthook


def _port():
    return int(os.environ.get('KIOSK_PORT', '8665'))


def _url():
    return 'http://127.0.0.1:%d' % _port()


def _listener_pids(port):
    try:
        out = subprocess.check_output(['netstat', '-ano'], text=True, errors='ignore')
    except Exception:
        return []
    pids = []
    for line in out.splitlines():
        if (':%d ' % port) in line and 'LISTENING' in line:
            parts = line.split()
            if parts:
                pids.append(parts[-1])
    return pids


def _kill_stale(port):
    for pid in _listener_pids(port):
        try:
            subprocess.check_call(
                ['taskkill', '/F', '/PID', pid],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            log.info('이전 서버 종료 (PID %s)', pid)
        except Exception as e:
            log.warning('구서버 종료 실패 PID %s: %s', pid, e)
    time.sleep(1)


def _wait_server(port, timeout=20):
    for _ in range(timeout):
        try:
            with socket.create_connection(('127.0.0.1', port), timeout=0.5):
                return True
        except OSError:
            time.sleep(0.5)
    return False


def _browser_candidates():
    return [
        os.path.expandvars(r'%ProgramFiles(x86)%\Microsoft\Edge\Application\msedge.exe'),
        os.path.expandvars(r'%ProgramFiles%\Microsoft\Edge\Application\msedge.exe'),
        r'C:\Program Files\Google\Chrome\Application\chrome.exe',
        r'C:\Program Files (x86)\Google\Chrome\Application\chrome.exe',
        os.path.expandvars(r'%LocalAppData%\Google\Chrome\Application\chrome.exe'),
    ]


def _open_browser():
    profile = os.path.join(PROG_DIR, '.chrome_profile')
    for exe in _browser_candidates():
        if os.path.isfile(exe):
            try:
                return subprocess.Popen([
                    exe, '--kiosk', '--start-fullscreen', '--no-first-run',
                    '--disable-session-crashed-bubble',
                    '--user-data-dir=%s' % profile, _url()])
            except Exception as e:
                log.warning('브라우저 실행 실패 %s: %s', exe, e)
    import webbrowser
    try:
        webbrowser.open(_url())
    except Exception as e:
        log.warning('기본 브라우저 열기 실패: %s', e)
    return None


def main():
    port = _port()
    log.info('===== 출석 키오스크 시작 (포트 %d) =====', port)

    _kill_stale(port)

    # 서버 시작 직전 DB 백업 (backups/군종_*.db.bak)
    try:
        from db_backup import do_backup
        path = do_backup()
        log.info('DB 백업 완료: %s', path)
    except Exception:
        log.exception('DB 백업 실패')

    # 이 시점에 app 모듈 로드 → init_db + 같은 날 자동백업(중복 방지)
    import app as kiosk_app
    from server_ctl import register_server, shutdown_server
    from werkzeug.serving import make_server

    server = make_server('127.0.0.1', port, kiosk_app.app)
    register_server(server)
    thr = threading.Thread(target=server.serve_forever, daemon=True)
    thr.start()

    if not _wait_server(port):
        log.error('서버 기동 실패 (포트 %d)', port)
        return 1

    log.info('서버 실행 중: %s', _url())
    browser = _open_browser()
    log.info('브라우저 열기 완료')

    if browser is not None:
        # 브라우저(사용자)가 닫거나, 보고서의 [종료] 버튼으로 서버가 죽을 때까지 대기
        try:
            while thr.is_alive() and browser.poll() is None:
                time.sleep(1)
            if not thr.is_alive():
                log.info('서버 종료됨(보고서 종료 버튼) → 브라우저 닫기')
                try:
                    browser.terminate()
                except Exception:
                    pass
            else:
                shutdown_server()  # 브라우저 닫힘 → 서버 종료
                log.info('브라우저 닫힘 → 서버 종료')
        except Exception as e:
            log.warning('감시 루프 오류: %s', e)
            shutdown_server()
    else:
        log.info('웹 보고서의 [종료] 버튼으로 서버를 종료할 수 있습니다')
        thr.join()

    try:
        server.shutdown()
    except Exception:
        pass
    thr.join(timeout=5)
    log.info('===== 키오스크 종료 =====')
    return 0


if __name__ == '__main__':
    sys.exit(main())