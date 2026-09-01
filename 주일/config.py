# -*- coding: utf-8 -*-
"""전역 설정 및 상수.

- DB 경로, 관리자 PIN, 서버 실행 환경(commercial/dev) 결정
- 실행 인자(dev|commercial) 또는 환경변수 SERVER_ENV로 서버 환경을 설정
"""
import os
import sys

# 프로젝트 루트 (config.py가 있는 폴더)
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# SQLite 데이터베이스 경로
DB_PATH = os.path.join(BASE_DIR, '군종.db')

# 관리자 인증용 PIN (키오스크 관리 화면 로그인)
# 환경변수 ADMIN_PIN 또는 파일(.admin_pin)로 설정 가능. 기본 '1717'은 로컬 키오스크용.
_admin_pin_file = os.path.join(BASE_DIR, '.admin_pin')
if os.environ.get('ADMIN_PIN'):
    ADMIN_PIN = os.environ['ADMIN_PIN']
elif os.path.isfile(_admin_pin_file):
    with open(_admin_pin_file, 'r', encoding='utf-8') as _f:
        ADMIN_PIN = _f.read().strip() or '1717'
else:
    ADMIN_PIN = '1717'

# 서버 실행 모드: 'commercial'(상업/운영) | 'dev'(개발/테스트)
# 환경변수 SERVER_ENV 또는 실행인자(dev/commercial)로 결정, 기본 commercial
SERVER_ENV = os.environ.get('SERVER_ENV', 'commercial')
for _a in sys.argv[1:]:
    if _a in ('dev', 'commercial'):
        SERVER_ENV = _a
