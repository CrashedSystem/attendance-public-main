# -*- coding: utf-8 -*-
"""팀/소속 관리 비즈니스 로직.

- 팀↔소속 매핑, 소속 일괄 이동, 소속·팀 이름 변경/생성/삭제
- custom_teams / custom_affiliations (아직 인원이 없는 신규 항목) 관리
- 새신우 유지 기간 설정
"""
import json

from constants import DEFAULT_NEWBIE_DAYS, TEMP_AFFIL
from models import user as user_model
from models.database import db
from models.settings import get_setting, set_setting
from services.report_service import safe_refresh


# ---------------------------------------------------------------------------
# custom_teams / custom_affiliations (settings에 JSON으로 저장)
# ---------------------------------------------------------------------------
def get_custom_teams(conn):
    """settings에 저장된, 아직 인원이 없는 신규 팀 목록."""
    raw = get_setting(conn, 'custom_teams', '')
    if not raw:
        return []
    try:
        return json.loads(raw)
    except Exception:
        return []


def set_custom_teams(conn, teams):
    set_setting(conn, 'custom_teams', json.dumps(teams, ensure_ascii=False))


def get_custom_affiliations(conn):
    """settings에 저장된, 아직 인원이 없는 임시 소속 목록."""
    raw = get_setting(conn, 'custom_affiliations', '')
    if not raw:
        return []
    try:
        return json.loads(raw)
    except Exception:
        return []


def set_custom_affiliations(conn, affs):
    set_setting(conn, 'custom_affiliations', json.dumps(affs, ensure_ascii=False))


def _count_by(conn, column, value):
    return conn.execute('SELECT COUNT(*) FROM users WHERE %s=?' % column, (value,)).fetchone()[0]


# ---------------------------------------------------------------------------
# 팀/소속 조회
# ---------------------------------------------------------------------------
def get_teams_affiliations_mapping():
    """소속→팀 매핑. 원칙: 같은 소속은 반드시 같은 팀.

    혹시 이질 데이터가 섞여도 가장 많은(다수결) 팀을 대표값으로 사용한다.
    custom_teams(아직 인원이 없는 새 팀)와 custom_affiliations(임시 소속)도 포함한다.

    반환: {'teams', 'affiliations', 'mapping'}
    """
    conn = db()
    rows = conn.execute(
        'SELECT affiliation, team, COUNT(*) c FROM users '
        'WHERE affiliation IS NOT NULL AND affiliation != "" AND team IS NOT NULL AND team != "" '
        'GROUP BY affiliation, team').fetchall()
    custom = get_custom_teams(conn)
    custom_affs = get_custom_affiliations(conn)
    conn.close()
    counts = {}
    for r in rows:
        counts.setdefault(r['affiliation'], []).append((r['c'], r['team']))
    mapping = {aff: max(lst)[1] for aff, lst in counts.items()}
    teams = sorted(set(mapping.values()) | set(custom))
    affiliations = sorted(set(mapping.keys()) | set(custom_affs) | {TEMP_AFFIL})
    return {'teams': teams, 'affiliations': affiliations, 'mapping': mapping}


# ---------------------------------------------------------------------------
# 소속 이동 / 이름 변경 / 생성
# ---------------------------------------------------------------------------
def bulk_move_team(affiliation, team):
    """특정 소속의 모든 사용자를 특정 팀으로 일괄 이동. 통계에 즉시 반영.

    반환: (응답 dict, HTTP 상태 코드)
    """
    if not affiliation or not team:
        return ({'ok': False, 'msg': '소속과 이동할 팀을 모두 선택하세요.'}, 400)
    conn = db()
    cur = conn.execute('UPDATE users SET team=? WHERE affiliation=?', (team, affiliation))
    moved = cur.rowcount
    custom = get_custom_teams(conn)
    if team in custom:
        custom.remove(team)
        set_custom_teams(conn, custom)
    conn.commit()
    conn.close()
    safe_refresh()
    return ({'ok': True, 'moved': moved, 'affiliation': affiliation, 'team': team}, 200)


def rename_affiliation(old_name, new_name):
    """소속 이름을 변경한다. 소속된 모든 사용자에게 즉시 반영.

    임시 소속('임시')을 다른 이름으로 바꾸면 빈 '임시' 소속이 다시 생긴다.

    반환: (응답 dict, HTTP 상태 코드)
    """
    old = (old_name or '').strip()
    new = (new_name or '').strip()
    if not old or not new:
        return ({'ok': False, 'msg': '변경할 소속과 새 이름을 모두 입력하세요.'}, 400)
    if old == new:
        return ({'ok': False, 'msg': '새 이름이 기존 이름과 같습니다.'}, 400)
    conn = db()
    exists = _count_by(conn, 'affiliation', new)
    custom = get_custom_affiliations(conn)
    if exists or new in custom:
        conn.close()
        return ({'ok': False, 'msg': "'%s' 소속이 이미 존재합니다." % new}, 400)
    cur = conn.execute('UPDATE users SET affiliation=? WHERE affiliation=?', (new, old))
    renamed = cur.rowcount
    if old in custom:
        custom = [new if a == old else a for a in custom]
        set_custom_affiliations(conn, custom)
    if old == TEMP_AFFIL and TEMP_AFFIL not in custom:
        custom.append(TEMP_AFFIL)
        set_custom_affiliations(conn, custom)
    conn.commit()
    conn.close()
    safe_refresh()
    return ({'ok': True, 'renamed': renamed, 'old_name': old, 'new_name': new}, 200)


def create_affiliation(name):
    """임시 소속을 추가한다. (아직 인원이 없는 소속)

    기본적으로 '임시' 소속을 만들며, 이름을 지정하면 그 이름으로 생성한다.

    반환: (응답 dict, HTTP 상태 코드)
    """
    name = (name or '').strip() or TEMP_AFFIL
    conn = db()
    existing = _count_by(conn, 'affiliation', name)
    custom = get_custom_affiliations(conn)
    if existing or name in custom:
        conn.close()
        return ({'ok': False, 'msg': "'%s' 소속이 이미 존재합니다." % name}, 400)
    custom.append(name)
    set_custom_affiliations(conn, custom)
    conn.commit()
    conn.close()
    safe_refresh()
    return ({'ok': True, 'name': name, 'temp': name == TEMP_AFFIL}, 200)


# ---------------------------------------------------------------------------
# 팀 이름 변경 / 생성 / 삭제
# ---------------------------------------------------------------------------
def rename_team(old_name, new_name):
    """기존 팀의 이름을 변경한다. 소속된 모든 사용자와 통계에 즉시 반영.

    반환: (응답 dict, HTTP 상태 코드)
    """
    old = (old_name or '').strip()
    new = (new_name or '').strip()
    if not old or not new:
        return ({'ok': False, 'msg': '변경할 팀과 새 이름을 모두 입력하세요.'}, 400)
    if old == new:
        return ({'ok': False, 'msg': '새 이름이 기존 이름과 같습니다.'}, 400)
    conn = db()
    dup = _count_by(conn, 'team', new)
    custom = get_custom_teams(conn)
    if dup or new in custom:
        conn.close()
        return ({'ok': False, 'msg': "'%s' 팀이 이미 존재합니다." % new}, 400)
    cur = conn.execute('UPDATE users SET team=? WHERE team=?', (new, old))
    renamed = cur.rowcount
    if old in custom:
        custom = [new if t == old else t for t in custom]
        set_custom_teams(conn, custom)
    conn.commit()
    conn.close()
    safe_refresh()
    return ({'ok': True, 'renamed': renamed, 'old_name': old, 'new_name': new}, 200)


def create_team(name):
    """새 팀을 등록한다. 인원이 없어도 드롭다운에 바로 표시된다.

    반환: (응답 dict, HTTP 상태 코드)
    """
    name = (name or '').strip()
    if not name:
        return ({'ok': False, 'msg': '팀 이름을 입력하세요.'}, 400)
    conn = db()
    dup = _count_by(conn, 'team', name)
    custom = get_custom_teams(conn)
    if dup or name in custom:
        conn.close()
        return ({'ok': False, 'msg': "'%s' 팀이 이미 존재합니다." % name}, 400)
    custom.append(name)
    set_custom_teams(conn, custom)
    conn.commit()
    conn.close()
    return ({'ok': True, 'name': name}, 200)


def delete_team(name):
    """팀을 삭제한다. 인원이 남아 있으면 거부하고, 비어 있는 팀만 삭제한다.

    인원이 없는 팀(0명 또는 custom_teams에만 존재)만 custom_teams 목록에서 제거한다.

    반환: (응답 dict, HTTP 상태 코드)
    """
    name = (name or '').strip()
    if not name:
        return ({'ok': False, 'msg': '삭제할 팀을 선택하세요.'}, 400)
    conn = db()
    cnt = _count_by(conn, 'team', name)
    custom = get_custom_teams(conn)
    if cnt > 0:
        conn.close()
        return ({'ok': False, 'msg': "'%s' 팀에 인원 %d명이 있어 삭제할 수 없습니다. 먼저 인원을 이동하세요."
                 % (name, cnt)}, 400)
    if name not in custom:
        conn.close()
        return ({'ok': False, 'msg': "'%s' 팀이 존재하지 않거나 인원이 있는 팀입니다." % name}, 400)
    custom.remove(name)
    set_custom_teams(conn, custom)
    conn.commit()
    conn.close()
    safe_refresh()
    return ({'ok': True, 'name': name}, 200)


# ---------------------------------------------------------------------------
# 새신우 유지 기간
# ---------------------------------------------------------------------------
def get_newbie_days():
    """새신우 유지 기간(일) 조회. 기본 30, 범위 1~365로 제한."""
    conn = db()
    raw = get_setting(conn, 'newbie_days', None)
    conn.close()
    try:
        v = int(raw) if raw else DEFAULT_NEWBIE_DAYS
    except Exception:
        v = DEFAULT_NEWBIE_DAYS
    return max(1, min(365, v))


def set_newbie_days(days):
    """새신우 유지 기간(일) 변경. 1~365일.

    반환: (응답 dict, HTTP 상태 코드)
    """
    try:
        v = int(days)
    except (TypeError, ValueError):
        return ({'ok': False, 'msg': '숫자를 입력하세요.'}, 400)
    if not (1 <= v <= 365):
        return ({'ok': False, 'msg': '1~365 사이의 값으로 입력하세요.'}, 400)
    conn = db()
    set_setting(conn, 'newbie_days', str(v))
    conn.commit()
    conn.close()
    safe_refresh()
    return ({'ok': True, 'days': v}, 200)
