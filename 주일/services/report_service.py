# -*- coding: utf-8 -*-
"""보고서 생성 로직 (web_report.py 통합).

- refresh_web_report 호출 관리 (에러 무시 처리)
- render_reports_to_png 호출 관리 (백그라운드 포함)
"""
import logging
import threading

from config import SERVER_ENV
from web_report import refresh_web_report, render_reports_to_png

logger = logging.getLogger(__name__)


def safe_refresh(mode=None, env=None, date_str=None):
    """웹 보고서 HTML을 갱신한다. 실패해도 예외를 유발하지 않는다. (실패는 로그에 남김)"""
    env = env or SERVER_ENV
    try:
        refresh_web_report(mode, env=env, date_str=date_str if date_str else None)
    except Exception:
        logger.exception('웹 보고서 갱신 실패 (mode=%s env=%s)', mode, env)


def refresh_report(mode=None, env=None, date_str=None):
    """웹 보고서 HTML을 갱신하고 결과(경로)를 반환한다. 실패 시 예외를 유발한다."""
    env = env or SERVER_ENV
    return refresh_web_report(mode, env=env, date_str=date_str if date_str else None)


def safe_refresh_with_png(mode=None, env=None):
    """웹 보고서를 갱신하고 배포용 PNG 생성을 백그라운드로 시작한다. 실패 무시."""
    env = env or SERVER_ENV
    safe_refresh(mode, env)
    try:
        threading.Thread(target=_render_png_logged,
                         kwargs={'mode': mode, 'env': env}, daemon=True).start()
    except Exception:
        logger.exception('PNG 백그라운드 생성 스레드 시작 실패 (mode=%s env=%s)', mode, env)


def _render_png_logged(mode=None, env=None):
    try:
        render_reports_to_png(mode, env=env)
    except Exception:
        logger.exception('PNG 렌더 실패 (mode=%s env=%s)', mode, env)


def render_png(mode=None, env=None):
    """보고서 PNG 배포 생성. 실패 시 예외를 유발한다."""
    env = env or SERVER_ENV
    render_reports_to_png(mode, env=env)
