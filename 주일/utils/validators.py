# -*- coding: utf-8 -*-
"""입력 검증 함수들.

각 검증 함수는 (ok, msg) 또는 유효 값/예외 형태로 일관되게 결과를 반환한다.
"""
import datetime
import re

from config import ADMIN_PIN


def validate_pin(pin):
    """PIN을 검증한다.

    반환: (ok, msg)
    """
    if str(pin) == str(ADMIN_PIN):
        return True, ''
    return False, 'PIN이 올바르지 않습니다.'


def validate_date(date_str):
    """날짜가 YYYY-MM-DD 형식인지 검증한다.

    반환: (ok, msg)
    """
    try:
        datetime.date.fromisoformat(date_str)
        return True, ''
    except (ValueError, TypeError):
        return False, '날짜를 올바르게 입력하세요. (YYYY-MM-DD)'


def validate_time(time_str):
    """시각이 HH:MM(또는 HH:MM:SS) 형식인지 검증한다.

    반환: (ok, msg)
    """
    if not re.match(r'^([01]\d|2[0-3]):[0-5]\d$', time_str) and \
       not re.match(r'^([01]\d|2[0-3]):[0-5]\d:[0-5]\d$', time_str):
        return False, '시각을 HH:MM 형식으로 입력하세요. (예: 10:30)'
    return True, ''


def validate_mode(mode):
    """모드가 sunday|wednesday 인지 검증한다.

    반환: (ok, msg)
    """
    if mode in ('sunday', 'wednesday'):
        return True, ''
    return False, '모드가 올바르지 않습니다.'


def validate_user_id(user_id):
    """사용자 id가 양의 정수인지 검증한다. 유효 시 정수, 아니면 None 반환."""
    try:
        uid = int(user_id)
    except (TypeError, ValueError):
        return None
    return uid
