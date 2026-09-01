# -*- coding: utf-8 -*-
"""사용자 관리 비즈니스 로직.

- 검색(일반·숫자·초성) 정렬/순위 로직
- 비고의 '새신우' 태그 정규화, 생일 포맷 통일
"""
import calendar
import datetime
import re
import threading
import time

from models import user as user_model
from models.database import db
from models.settings import get_current_mode
from models.user import prune_expired_users
from constants import CHOSUNG, CHOSUNG_SET, MODES


def normalize_newbie_note(note):
    """비고에 '새신우'가 있으면 등록 날짜를 자동 부여한다. -> 새신우(YYYY-MM-DD)

    이미 날짜가 붙은 태그는 그대로 둔다. (web_report.expire_newbie_notes가 N일 후 자동 삭제)
    """
    s = (note or '').strip()
    if not s:
        return s
    return re.sub(r'새신우(?!\(\d{4}-\d{2}-\d{2}\))',
                  '새신우(%s)' % datetime.date.today().isoformat(), s)


def norm_birthday(b):
    """생일을 네 자리 숫자(MMDD)로 통일한다. -> '0102' (1월 2일)

    지원 입력: 'MM월 DD일', 'M월 D일', 'YYYY-MM-DD', 'YYYY.MM.DD', 'MMDD'
    MMDD는 월(01~12)·일(01~31) 범위를 검증하며, 변환 실패 시 원본 그대로 반환한다.
    """
    s = (b or '').strip()
    if not s:
        return ''
    if re.match(r'^\d{4}$', s):
        mo, d = int(s[:2]), int(s[2:])
        if 1 <= mo <= 12 and 1 <= d <= calendar.monthrange(2000, mo)[1]:
            return s
        return ''
    m = re.match(r'^(\d{4})[-.](\d{1,2})[-.](\d{1,2})$', s)
    if m:
        mo, d = int(m.group(2)), int(m.group(3))
        if 1 <= mo <= 12 and 1 <= d <= calendar.monthrange(2000, mo)[1]:
            return '%02d%02d' % (mo, d)
        return ''
    m = re.match(r'^(\d{1,2})\s*월\s*(\d{1,2})\s*일?$', s)
    if m:
        mo, d = int(m.group(1)), int(m.group(2))
        if 1 <= mo <= 12 and 1 <= d <= calendar.monthrange(2000, mo)[1]:
            return '%02d%02d' % (mo, d)
        return ''
    return s


def _to_chosung(s):
    """문자열의 한글 음절을 초성으로 치환한 문자열을 반환한다."""
    out = []
    for ch in s:
        o = ord(ch)
        if 0xAC00 <= o <= 0xD7A3:
            out.append(CHOSUNG[(o - 0xAC00) // 588])
        else:
            out.append(ch)
    return ''.join(out)


def _is_chosung_query(q):
    """공백 제외 전 문자가 한글 초성(ㄱ~ㅎ)이면 True. (초성 검색 판별)"""
    return all(ch in CHOSUNG_SET or ch.isspace() for ch in q)


def validate_user_data(data):
    """사용자 생성/수정 입력의 필수값(이름)을 검증한다.

    반환: (ok, msg)
    """
    if not (data or {}).get('name', '').strip():
        return False, '이름을 입력하세요.'
    return True, ''


_last_prune_ts = 0
_prune_lock = threading.Lock()


def _maybe_prune(conn):
    """5분 주기로 전역자 정리를 실행한다. (스레드 안전: 동시 실행 방지)"""
    global _last_prune_ts
    with _prune_lock:
        if time.time() - _last_prune_ts > 300:
            prune_expired_users(conn)
            _last_prune_ts = time.time()


def search_users_with_mode(q, mode):
    """사용자 검색. 빈 쿼리는 전체 목록(소속·id 정렬), 그 외엔 숫자/초성/일반 순위 검색.

    반환: 사용자 dict 목록
    """
    conn = db()
    try:
        _maybe_prune(conn)
        if mode not in MODES:
            mode = get_current_mode(conn)
        users = _search_all_users(conn)
    finally:
        conn.close()

    q = (q or '').strip()
    if not q:
        users.sort(key=lambda u: (u['affiliation'] or '', u['id']))
        return users

    # 1) 숫자 검색: id 또는 이름에 포함
    if q.isdigit():
        return [u for u in users if str(u['id']) == q or q in (u['name'] or '')]

    # 2) 초성 검색: 모든 문자(공백 제외)가 한글 초성이면 이름·소속·팀의 초성으로 매칭
    if _is_chosung_query(q):
        qc = _to_chosung(q).replace(' ', '')
        scored = []
        for u in users:
            name_c = _to_chosung(u['name'] or '')
            if qc in name_c:
                scored.append((1, name_c.index(qc), u))
                continue
            aff_c = _to_chosung(u['affiliation'] or '')
            if qc in aff_c:
                scored.append((2, aff_c.index(qc), u))
                continue
            team_c = _to_chosung(u['team'] or '')
            if qc in team_c:
                scored.append((3, team_c.index(qc), u))
        scored.sort(key=lambda t: (t[0], t[1], t[2]['id']))
        return [u for _, _, u in scored]

    # 3) 일반 텍스트 검색: 이름 우선(정확일치·접두·포함), 이어서 소속·팀
    scored = []
    for u in users:
        name = u['name'] or ''
        aff = u['affiliation'] or ''
        team = u['team'] or ''
        rank = None
        if name == q:
            rank = (0, 0, 0)
        elif name.startswith(q):
            rank = (0, 1, len(name))
        elif q in name:
            rank = (0, 2, name.index(q))
        elif q in aff:
            rank = (1, 0, 0)
        elif q in team:
            rank = (2, 0, 0)
        if rank is not None:
            scored.append((rank, u))
    scored.sort(key=lambda t: (t[0][0], t[0][1], t[0][2], t[1]['id']))
    return [u for _, u in scored]


def _search_all_users(conn):
    """검색용 사용자 조회 (models.user의 헬퍼 위임)."""
    return user_model.search_all_users(conn)
