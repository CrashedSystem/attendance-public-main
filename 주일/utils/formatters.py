# -*- coding: utf-8 -*-
"""포맷팅 함수들."""
from constants import MODE_SUNDAY, MODE_WEDNESDAY


def format_birthday(b):
    """생일 문자열을 MMDD 네 자리 표준형으로 포맷한다. 실패 시 원본 반환."""
    b = (b or '').strip()
    if not b:
        return ''
    if len(b) == 4 and b.isdigit():
        return b
    # YYYY-MM-DD / YYYY.MM.DD -> MMDD
    parts = b.replace('-', '.').split('.')
    if len(parts) == 3:
        try:
            return '%02d%02d' % (int(parts[1]), int(parts[2]))
        except ValueError:
            return b
    return b


def format_date(d):
    """날짜 문자열을 표준형(YYYY-MM-DD)으로 포맷하거나, 유효하지 않으면 빈 문자열 반환."""
    try:
        import datetime
        return datetime.date.fromisoformat((d or '').strip()).isoformat()
    except (ValueError, TypeError):
        return ''


def format_mode_label(mode):
    """모드 키를 사용자용 라벨 한글로 변환한다."""
    if mode == MODE_SUNDAY:
        return '일요일'
    if mode == MODE_WEDNESDAY:
        return '수요일'
    return mode or ''
