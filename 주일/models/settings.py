# -*- coding: utf-8 -*-
"""설정(settings) 관련 DB 쿼리 및 모드·요일 헬퍼.
"""
import datetime

from models.database import db
from constants import MODE_WEDNESDAY, MODE_SUNDAY

# 모드별 서비스 요일: sunday=일요일(6), wednesday=수요일(2)
MODE_WEEKDAY = {MODE_SUNDAY: 6, MODE_WEDNESDAY: 2}


def get_setting(conn, key, default=None):
    """settings 테이블에서 key의 값을 조회한다. 없으면 default를 반환한다."""
    row = conn.execute('SELECT value FROM settings WHERE key=?', (key,)).fetchone()
    return row['value'] if row else default


def set_setting(conn, key, value):
    """settings 테이블에 key/value를 저장하거나 덮어쓴다."""
    conn.execute('INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)', (key, value))


def get_current_mode(conn=None):
    """현재 서비스 모드를 조회한다. 없으면 'sunday'."""
    own = conn is None
    if own:
        conn = db()
    mode = get_setting(conn, 'current_mode', MODE_SUNDAY)
    if own:
        conn.close()
    return mode


def set_current_mode(conn, mode):
    """현재 서비스 모드를 설정한다."""
    set_setting(conn, 'current_mode', mode)
    conn.commit()


def _mode_weekday(mode):
    """모드별 서비스 요일. sunday=일요일(6), wednesday=수요일(2). 없으면 None."""
    return MODE_WEEKDAY.get(mode)


def mode_for_date(date_str):
    """날짜의 요일로 모드 자동 판별. 일요일→sunday, 수요일→wednesday, 그 외엔 None."""
    try:
        wd = datetime.date.fromisoformat(date_str).weekday()
    except (ValueError, TypeError):
        return None
    if wd == 6:
        return MODE_SUNDAY
    if wd == 2:
        return MODE_WEDNESDAY
    return None


def is_service_date(date_str, mode):
    """해당 날짜가 모드의 서비스 요일인지 여부. 모드가 없으면 항상 True."""
    wd = _mode_weekday(mode)
    if wd is None:
        return True
    try:
        return datetime.date.fromisoformat(date_str).weekday() == wd
    except ValueError:
        return False
