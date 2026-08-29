# -*- coding: utf-8 -*-
"""데코레이터 모음.

- require_admin_pin: 관리자 요청을 X-Admin-Pin 헤더로 검증한다.
- validate_json / handle_errors: 요청/오류 처리를 표준화한다.
"""
import functools

from flask import jsonify, request

from config import ADMIN_PIN


def require_admin_pin(f):
    """관리자 요청에 PIN 검증을 적용한다. 요청 헤더 X-Admin-Pin 필요.

    참고: 기본 동작과의 호환을 위해 기본 적용하지 않는다.
    """
    @functools.wraps(f)
    def wrapper(*args, **kwargs):
        pin = request.headers.get('X-Admin-Pin', '')
        if pin == ADMIN_PIN:
            return f(*args, **kwargs)
        return jsonify({'ok': False, 'msg': '관리자 인증이 필요합니다.'}), 401
    return wrapper


def validate_json(f):
    """요청 본문이 JSON형식인지 검증한다. (잘못되면 빈 dict로 대체)"""
    @functools.wraps(f)
    def wrapper(*args, **kwargs):
        data = request.get_json(silent=True) or {}
        kwargs['json_data'] = data
        return f(*args, **kwargs)
    return wrapper


def handle_errors(f):
    """라우트 핸들러에서 발생한 예외를 JSON 오류로 변환한다.

    참고: 기존 동작과의 호환을 위해 기본 적용하지 않는다.
    """
    @functools.wraps(f)
    def wrapper(*args, **kwargs):
        try:
            return f(*args, **kwargs)
        except Exception as e:
            return jsonify({'ok': False, 'msg': '서버 오류: %s' % e}), 500
    return wrapper
