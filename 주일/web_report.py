import os
import re
import json
import datetime
import sqlite3

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, '군종.db')
REPORT_PATH = os.path.join(BASE_DIR, '출석_그래프_%s.html')
REPORT_ARCHIVE_DIR = os.path.join(BASE_DIR, 'data', '통계_%s')
# 생성 결과를 덮어쓰지 않는 별도 템플릿. (출력 파일을 자기 자신 템플릿으로 쓰면
# 모드 전환 시 치환 마커가 소실되어 수요일 통계가 일부만 표시되는 버그 발생)
TEMPLATE_PATH = os.path.join(BASE_DIR, 'report_template.html')

MODE_SHEETS = {'sunday': '일요일', 'wednesday': '수요일'}
MODE_WEEKDAY = {'sunday': 6, 'wednesday': 2}


def _report_path(env='commercial'):
    return REPORT_PATH % env


def _archive_dir(env='commercial'):
    return REPORT_ARCHIVE_DIR % env


def _db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def _mode_weekday(mode):
    return MODE_WEEKDAY.get(mode)


def _is_service_date(date_str, mode):
    wd = _mode_weekday(mode)
    if wd is None:
        return True
    try:
        return datetime.date.fromisoformat(date_str).weekday() == wd
    except ValueError:
        return False


def _load_users(conn, mode, team_filter=None):
    if team_filter:
        users = [dict(r) for r in conn.execute(
            'SELECT id, name, affiliation, team, birthday, phone, note, is_chaplain FROM users WHERE team = ? ORDER BY affiliation, id', (team_filter,))]
    else:
        users = [dict(r) for r in conn.execute(
            'SELECT id, name, affiliation, team, birthday, phone, note, is_chaplain FROM users ORDER BY affiliation, id')]
    return users


NEWBIE_DAYS = 30  # 새신우 유지 기간 기본값(일). settings의 'newbie_days'로 조정 가능


def _newbie_days():
    """설정된 새신우 유지 기간(일). 없으면 기본값 30."""
    conn = _db()
    row = conn.execute("SELECT value FROM settings WHERE key='newbie_days'").fetchone()
    conn.close()
    try:
        v = int(row['value']) if row and row['value'] else NEWBIE_DAYS
    except Exception:
        v = NEWBIE_DAYS
    return max(1, min(365, v))


def _is_newbie(note):
    """비고의 새신우 태그로 새신우 여부 판정. 등록 후 유지기간 이내면 True."""
    s = note or ''
    dates = re.findall(r'새신우\((\d{4}-\d{2}-\d{2})\)', s)
    if dates:
        limit = datetime.date.today() - datetime.timedelta(days=_newbie_days())
        return any(datetime.date.fromisoformat(d) >= limit for d in dates)
    return '새신우' in s  # 날짜 없는 태그는 정규화 전 수동 입력분 -> 새신우로 취급


def expire_newbie_notes():
    """유지기간이 지난 새신우 태그를 비고에서 자동 삭제한다.

    태그 외 다른 내용은 보존하고, 비고가 비게 되면 공백으로 만든다.
    """
    days = _newbie_days()
    conn = _db()
    rows = conn.execute("SELECT id, note FROM users WHERE note LIKE '%새신우%'").fetchall()
    today = datetime.date.today()
    limit = today - datetime.timedelta(days=days)
    changed = 0
    for r in rows:
        note = r['note'] or ''
        dates = re.findall(r'새신우\((\d{4}-\d{2}-\d{2})\)', note)
        if not dates:
            continue
        if min(datetime.date.fromisoformat(d) for d in dates) <= limit:
            new_note = re.sub(r'\s*새신우\(\d{4}-\d{2}-\d{2}\)', '', note).strip(' ,.;·/')
            if new_note != note:
                conn.execute('UPDATE users SET note=? WHERE id=?', (new_note, r['id']))
                changed += 1
    conn.commit()
    conn.close()
    return changed


def _build_newbies(conn, users, last_date, env, mode, absent=None):
    """새신우 명단 + 마지막 서비스일 출석 여부 및 연속 미출석 주차."""
    attended = {}
    if last_date:
        for r in conn.execute(
                "SELECT user_id, check_time FROM attendance WHERE mode=? AND env=? AND check_date=?",
                (mode, env, last_date)).fetchall():
            attended[r['user_id']] = r['check_time']
    absent = absent or {}
    out = []
    for u in users:
        if not _is_newbie(u.get('note')):
            continue
        out.append({'name': u['name'], 'aff': u.get('affiliation') or '',
                    'team': u.get('team') or '', 'phone': u.get('phone') or '',
                    'att': attended.get(u['id']) or '',
                    'w': int(absent.get(u['id'], 0))})
    out.sort(key=lambda x: x['name'])
    return out


def _parse_birthday(s):
    if not s:
        return None
    s = str(s).strip()
    m = re.match(r'^(\d{4})-(\d{1,2})-(\d{1,2})', s)
    if m:
        return int(m.group(2)), int(m.group(3)), '%d월 %d일' % (int(m.group(2)), int(m.group(3)))
    m = re.match(r'^(\d{2})(\d{2})$', s)
    if m:
        mo, d = int(m.group(1)), int(m.group(2))
        if 1 <= mo <= 12 and 1 <= d <= 31:
            return mo, d, '%d월 %d일' % (mo, d)
        return None
    m = re.match(r'(\d{1,2})\s*월\s*(\d{1,2})\s*일?', s)
    if m:
        return int(m.group(1)), int(m.group(2)), '%d월 %d일' % (int(m.group(1)), int(m.group(2)))
    return None


def _build_stats(conn, users, mode, env='commercial', team_filter=None):
    if team_filter:
        user_ids = [u['id'] for u in users]
        if not user_ids:
            return {'dates': [], 'counts': [], 'deltas': [], 'rates': [], 'total': 0, 'days': 0, 'avg': 0, 'thiswk': '', 'lastwk': '', 'maxd': '', 'last_change': ''}, {}
        placeholders = ','.join(['?'] * len(user_ids))
        rows = conn.execute(
            "SELECT check_date, COUNT(*) c FROM attendance WHERE mode=? AND env=? AND user_id IN (%s) GROUP BY check_date" % placeholders,
            [mode, env] + user_ids).fetchall()
    else:
        rows = conn.execute(
            "SELECT check_date, COUNT(*) c FROM attendance WHERE mode=? AND env=? GROUP BY check_date",
            (mode, env)).fetchall()
    date_map = {}
    for r in rows:
        d = r['check_date']
        if _is_service_date(d, mode):
            date_map[d] = date_map.get(d, 0) + r['c']
    dates = sorted(date_map)
    counts = [date_map[d] for d in dates]
    deltas = [None]
    rates = [None]
    for i in range(1, len(counts)):
        d = counts[i] - counts[i - 1]
        deltas.append(d)
        rates.append(round(d / counts[i - 1] * 100, 1) if counts[i - 1] else None)

    stats = {
        'dates': dates,
        'counts': counts,
        'deltas': deltas,
        'rates': rates,
        'total': sum(counts),
        'days': len(dates),
        'avg': round(sum(counts) / len(counts), 1) if counts else 0,
        'thiswk': '',
        'lastwk': '',
        'maxd': '',
        'last_change': '',
    }
    if len(dates) >= 1:
        stats['thiswk'] = '%s %d명' % (dates[-1], counts[-1])
    if len(dates) >= 2:
        stats['lastwk'] = '%s %d명' % (dates[-2], counts[-2])
        last_d = deltas[-1]
        last_r = rates[-1]
        if last_d is not None:
            sign = '+' if last_d > 0 else ''
            stats['last_change'] = '%s %s%d명 (%s%.1f%%)' % (dates[-1], sign, last_d, sign, last_r)
    if counts:
        mx = max(counts)
        stats['maxd'] = '%s %d명' % (dates[counts.index(mx)], mx)
    return stats, date_map


def _build_absent(conn, users, date_map, env='commercial', team_filter=None, mode=None):
    event_dates = sorted(date_map)
    user_ids = [u['id'] for u in users]
    if not user_ids:
        return [], {}
    if mode == 'wednesday':
        # 수요일 모드: 연속 미출석자 명단은 군종병만 표시
        users = [u for u in users if u.get('is_chaplain')]
        user_ids = [u['id'] for u in users]
        if not user_ids:
            return [], {}
    placeholders = ','.join(['?'] * len(user_ids))
    attended = {}
    for r in conn.execute("SELECT user_id, check_date FROM attendance WHERE mode IN ('sunday','wednesday') AND env=? AND user_id IN (%s)" % placeholders,
                          [env] + user_ids):
        d = r['check_date']
        if d in date_map:
            attended.setdefault(r['user_id'], set()).add(d)
    if not event_dates:
        return [], {}
    last_date = event_dates[-1]
    absent = {}
    for u in users:
        seen = attended.get(u['id'], set())
        weeks = 0
        for d in reversed(event_dates):
            if d > last_date:
                continue
            if d in seen:
                break
            weeks += 1
        absent[u['id']] = weeks
    # 수요일 모드: absences 테이블의 주차별 결석 사유를 미리 로드해 둔다.
    reasons_by_user = {}
    if mode == 'wednesday':
        for r in conn.execute(
                "SELECT user_id, check_date, reason FROM absences "
                "WHERE mode='wednesday' AND env=? AND reason != ''",
                (env,)).fetchall():
            reasons_by_user.setdefault(r['user_id'], {})[r['check_date']] = r['reason']
    listed = []
    for u in users:
        w = absent.get(u['id'], 0)
        if 1 <= w <= 4:
            item = {
                'name': u['name'], 'aff': u.get('affiliation') or '',
                'phone': u.get('phone') or '', 'w': w,
                'nb': _is_newbie(u.get('note')),
            }
            if mode == 'wednesday':
                # 과거주차 → 현재주차 순으로 사유를 묶어 텍스트 흐름으로 구성
                umap = reasons_by_user.get(u['id'], {})
                weeks_info = event_dates[-w:]
                item['reason'] = ' → '.join(
                    '[%d주차] %s' % (i + 1, umap.get(d) or '-')
                    for i, d in enumerate(weeks_info))
                reasons = [umap.get(d) or '' for d in weeks_info]
                item['unauth'] = any(r.strip() == '무단' or r.strip() == '' for r in reasons)
            else:
                item['team'] = u.get('team') or ''
            listed.append(item)
    listed.sort(key=lambda x: (x['w'], x['name']))
    return listed, absent


def _build_birthday(users, date_str):
    month = None
    try:
        month = datetime.date.fromisoformat(date_str).month
    except ValueError:
        pass
    if month is None:
        return []
    listed = []
    for u in users:
        p = _parse_birthday(u.get('birthday'))
        if p and p[0] == month:
            listed.append({'name': u['name'], 'aff': u.get('affiliation') or '',
                           'team': u.get('team') or '', 'phone': u.get('phone') or '',
                           'bday': p[2], 'day': p[1]})
    listed.sort(key=lambda x: x['day'])
    return listed


def _build_teams(conn, mode, last_date, env='commercial', team_filter=None):
    if not last_date:
        return []
    if team_filter:
        rows = conn.execute(
            "SELECT u.team team, COUNT(*) c FROM attendance a JOIN users u ON a.user_id = u.id "
            "WHERE a.mode=? AND a.check_date=? AND a.env=? AND u.team=? GROUP BY u.team ORDER BY c DESC, u.team",
            (mode, last_date, env, team_filter)).fetchall()
    else:
        rows = conn.execute(
            "SELECT u.team team, COUNT(*) c FROM attendance a JOIN users u ON a.user_id = u.id "
            "WHERE a.mode=? AND a.check_date=? AND a.env=? GROUP BY u.team ORDER BY c DESC, u.team",
            (mode, last_date, env)).fetchall()
    return [{'team': r['team'] or '-', 'count': r['c']} for r in rows]


TEAM_SUMMARY_SCRIPT = (
    "/* 팀별 출석 인원 (이번 주) */\n"
    "(function () {\n"
    "  const rows = C.teams.map(function (t) {\n"
    "    return '<tr><td>' + t.team + '</td><td>' + t.count + '명</td></tr>';\n"
    "  }).join('');\n"
    "  var html = '<table class=\"abs\"><tr><th>팀</th><th>출석 인원</th></tr>' + rows + '</table>';\n"
    "  document.getElementById('team-wrap').innerHTML = html;\n"
    "})();"
)

ATTENDEE_DETAIL_SCRIPT = (
    "/* 팀 출석자 상세 명단 */\n"
    "(function () {\n"
    "  const rows = (C.team_attendees || []).map(function (a, idx) {\n"
    "    return '<tr><td>' + (idx + 1) + '</td><td>' + a.name + '</td><td>' + a.aff + '</td><td>' + a.team + '</td>' +\n"
    "      '<td>' + (a.phone ? a.phone : '<span class=\"nophone\">-</span>') + '</td><td>' + a.time + '</td></tr>';\n"
    "  }).join('');\n"
    "  var html = '<table class=\"abs\"><tr><th>No</th><th>이름</th><th>소속</th><th>팀</th><th>휴대폰</th><th>출석시각</th></tr>' + rows + '</table>';\n"
    "  document.getElementById('team-wrap').innerHTML = html;\n"
    "})();"
)


def _build_team_attendees(conn, mode, last_date, env='commercial', team_filter=None):
    """지정된 팀(team_filter) 또는 전체(mode 기준) 마지막 서비스일 출석자 상세 명단."""
    if not last_date:
        return []
    if team_filter:
        rows = conn.execute(
            "SELECT u.name, u.affiliation, u.team, u.phone, a.check_time "
            "FROM attendance a JOIN users u ON a.user_id = u.id "
            "WHERE a.mode=? AND a.check_date=? AND a.env=? AND u.team=? "
            "ORDER BY u.affiliation, u.name",
            (mode, last_date, env, team_filter)).fetchall()
    else:
        rows = conn.execute(
            "SELECT u.name, u.affiliation, u.team, u.phone, a.check_time "
            "FROM attendance a JOIN users u ON a.user_id = u.id "
            "WHERE a.mode=? AND a.check_date=? AND a.env=? "
            "ORDER BY u.affiliation, u.name",
            (mode, last_date, env)).fetchall()
    return [{
        'name': r['name'],
        'aff': r['affiliation'] or '',
        'team': r['team'] or '',
        'phone': r['phone'] or '',
        'time': r['check_time'] or ''
    } for r in rows]


def _month_label(date_str):
    try:
        return datetime.date.fromisoformat(date_str).month
    except ValueError:
        return None


def _stat_boxes(stats, last_wk_is_up):
    this = stats['thiswk'] or '-'
    last = stats['lastwk'] or '-'
    boxes = [
        '<div class="box"><b>%s</b><span>이번 주 출석</span></div>' % this,
        '<div class="box fade"><b>%s</b><span>저번 주 출석</span></div>' % last,
        '<div class="box"><b>%d</b><span>주(일) 수</span></div>' % stats['days'],
        '<div class="box"><b>%s</b><span>평균 출석/주</span></div>' % stats['avg'],
        '<div class="box"><b>%s</b><span>최다 출석</span></div>' % (stats['maxd'] or '-'),
    ]
    lc = stats.get('last_change')
    if lc:
        boxes.append('<div class="box down"><b>%s</b><span>최근 변화 (이전 주 대비)</span></div>' % lc)
    return '\n    '.join(boxes)


def _safe_filename(name):
    """팀 이름을 파일명으로 안전하게 변환. (Windows 금지 문자 치환)"""
    return re.sub(r'[\\/:*?"<>|]', '_', str(name)).strip() or '이름없음'


def _png_dir(env='commercial'):
    """배포용 PNG 저장 폴더 (예: data/통계_commercial_png)"""
    return os.path.join(BASE_DIR, 'data', '통계_%s_png' % env)


def _render_html_to_png(html_path, png_path):
    """주어진 HTML 파일을 A4(가로 794px) 고해상도 PNG로 렌더링. 실패 시 False 반환."""
    if not os.path.isfile(html_path):
        return False
    try:
        from playwright.sync_api import sync_playwright
    except Exception:
        return False
    p = None
    b = None
    try:
        p = sync_playwright().start()
        b = p.chromium.launch(args=['--no-sandbox'])
        # device_scale_factor=3 → A4 기준 약 2382×3369px (≈288dpi)로 선명하게 캡처
        page = b.new_page(viewport={'width': 794, 'height': 1123}, device_scale_factor=3)
        page.goto('file:///' + os.path.abspath(html_path).replace('\\', '/'))
        page.wait_for_timeout(1500)
        page.screenshot(path=png_path, full_page=True)
        return True
    except Exception:
        return False
    finally:
        try:
            if b is not None:
                b.close()
        except Exception:
            pass
        try:
            if p is not None:
                p.stop()
        except Exception:
            pass


def _render_pngs_shared(html_png_pairs):
    """여러 HTML을 하나의 브라우저 세션으로 A4 PNG로 렌더링 (속도 최적화).

    html_png_pairs: [(html_path, png_path), ...] 실패한 항목은 무시하고 계속 진행.
    """
    if not html_png_pairs:
        return
    try:
        from playwright.sync_api import sync_playwright
    except Exception:
        return
    p = None
    b = None
    try:
        p = sync_playwright().start()
        b = p.chromium.launch(args=['--no-sandbox'])
        for html_path, png_path in html_png_pairs:
            if not os.path.isfile(html_path):
                continue
            try:
                page = b.new_page(viewport={'width': 794, 'height': 1123}, device_scale_factor=3)
                page.goto('file:///' + os.path.abspath(html_path).replace('\\', '/'))
                page.wait_for_timeout(1000)
                page.screenshot(path=png_path, full_page=True)
                page.close()
            except Exception:
                pass
    finally:
        try:
            if b is not None:
                b.close()
        except Exception:
            pass
        try:
            if p is not None:
                p.stop()
        except Exception:
            pass


def render_reports_to_png(mode=None, env='commercial', date_str=None):
    """현재/지정 날짜 기준으로 저장된 보고서 HTML을 A4 PNG로 렌더링한다.

    refresh_web_report()가 HTML을 생성한 뒤 호출하며, 메인 + 팀 보고서 PNG를
    data/통계_{env}_png 에 생성한다. (호출측에서 명시적으로 실행)
    """
    conn = _db()
    if mode not in MODE_SHEETS:
        row = conn.execute("SELECT value FROM settings WHERE key='current_mode'").fetchone()
        mode = row['value'] if row else 'sunday'
    rows = conn.execute(
        "SELECT check_date FROM attendance WHERE mode=? AND env=? ORDER BY check_date DESC LIMIT 1",
        (mode, env)).fetchall()
    teams_rows = conn.execute(
        "SELECT DISTINCT team FROM users WHERE team IS NOT NULL AND team != '' ORDER BY team").fetchall()
    conn.close()
    if not date_str:
        date_str = rows[0]['check_date'] if rows else datetime.date.today().isoformat()
    if not _is_service_date(date_str, mode):
        return

    stamp = date_str.replace('-', '')
    pairs = []
    # 메인 아카이브 보고서
    main_html = os.path.join(_archive_dir(env), '출석_그래프_%s.html' % stamp)
    main_png_dir = _png_dir(env)
    os.makedirs(main_png_dir, exist_ok=True)
    pairs.append((main_html, os.path.join(main_png_dir, '출석_그래프_%s.png' % stamp)))
    # 팀별 보고서
    team_png_dir = os.path.join(_png_dir(env), 'teams', stamp)
    os.makedirs(team_png_dir, exist_ok=True)
    for r in teams_rows:
        team = r['team']
        team_html = os.path.join(_archive_dir(env), 'teams', stamp,
                                 '출석_그래프_%s.html' % _safe_filename(team))
        pair = (team_html, os.path.join(team_png_dir, '출석_그래프_%s.png' % _safe_filename(team)))
        pairs.append(pair)
    _render_pngs_shared(pairs)


def _render_report_for_team(date_str, mode, env='commercial', team_filter=None, team_index=1):
    conn = _db()
    users = _load_users(conn, mode, team_filter=team_filter)
    stats, date_map = _build_stats(conn, users, mode, env, team_filter=team_filter)
    absent_list, absent_weeks = _build_absent(conn, users, date_map, env, team_filter=team_filter, mode=mode)
    bday = _build_birthday(users, date_str)
    last_date = stats['dates'][-1] if stats['dates'] else ''
    teams = _build_teams(conn, mode, last_date, env, team_filter=team_filter)
    team_attendees = _build_team_attendees(conn, mode, last_date, env, team_filter=team_filter)
    newbies = _build_newbies(conn, users, last_date, env, mode, absent=absent_weeks)
    conn.close()

    month = _month_label(date_str)
    total = stats['total']

    MAX_WEEKS = 16
    dates = stats['dates'][-MAX_WEEKS:]
    counts = stats['counts'][-MAX_WEEKS:]
    deltas = stats['deltas'][-MAX_WEEKS:]
    rates = stats['rates'][-MAX_WEEKS:]

    data = {
        'dates': dates,
        'counts': counts,
        'deltas': deltas,
        'rates': rates,
        'total': total,
        'days': stats['days'],
        'avg': stats['avg'],
        'thiswk': stats['thiswk'],
        'lastwk': stats['lastwk'],
        'maxd': stats['maxd'],
        'absent': absent_list,
        'bday': bday,
        'teams': teams,
        'team_attendees': team_attendees,
        'newbies': newbies,
    }
    json_data = json.dumps(data, ensure_ascii=False)

    team_title_suffix = ' (%s)' % team_filter if team_filter else ''
    mode_label = MODE_SHEETS.get(mode, '')
    sub = '%s 예배%s · %s ~ %s · 총 %d건' % (
        mode_label,
        team_title_suffix,
        stats['dates'][0] if stats['dates'] else '-',
        stats['dates'][-1] if stats['dates'] else '-',
        total)

    template_path = TEMPLATE_PATH
    if not os.path.exists(template_path):
        template_path = REPORT_PATH % 'commercial'
    html = open(template_path, encoding='utf-8').read()

    html = re.sub(r'<p class="sub">.*?</p>', '<p class="sub">%s</p>' % sub, html, count=1)

    stat_html = _stat_boxes(stats, False)
    html = re.sub(
        r'<div class="stat">.*?\n  </div>',
        lambda m: '<div class="stat">\n    ' + stat_html + '\n  </div>',
        html, count=1, flags=re.S)

    html = re.sub(
        r'연속 미출석자 명단 \(1~4주\) · 총 \d+명',
        '연속 미출석자 명단 (1~4주) · 총 %d명' % len(absent_list), html, count=1)

    if month:
        html = re.sub(
            r'이달의 생일자 \(\d+월\) · 총 \d+명',
            '이달의 생일자 (%d월) · 총 %d명' % (month, len(bday)), html, count=1)

    html = re.sub(
        r'새신우 현황 · 총 \d+명',
        '새신우 현황 · 총 %d명' % len(newbies), html, count=1)

    if mode == 'wednesday':
        # 수요일 모드: 새신우 현황·이달의 생일자 카드와 스크립트 제거
        html = re.sub(
            r'<div class="card">\s*<h2>(새신우 현황|이달의 생일자)[^<]*</h2>\s*<div class="table-wrap" id="[^"]*"></div>\s*</div>',
            '', html, flags=re.S)
        html = re.sub(
            r'/\* (새신우 현황|이달의 생일자)[^*]*\*/\s*\(function \(\) \{.*?\}\)\(\);\s*',
            '', html, flags=re.S)

    if team_filter:
        html = re.sub(
            r'<h2>팀별 출석 인원 \(이번 주\)</h2>',
            '<h2>팀 출석자 상세 명단 (%s) · 총 %d명</h2>' % (team_filter, len(team_attendees)), html, count=1)

        # 수요일 모드: 팀별 보고서에도 출석자 전체 상세 명단 표시
        html = html.replace(TEAM_SUMMARY_SCRIPT, ATTENDEE_DETAIL_SCRIPT)
    elif mode == 'wednesday':
        # 수요일 모드 기본 보고서: 팀 집계 대신 전체 출석자 상세 명단 표시
        html = re.sub(
            r'<h2>팀별 출석 인원 \(이번 주\)</h2>',
            '<h2>전체 출석자 상세 명단 · 총 %d명</h2>' % len(team_attendees), html, count=1)
        html = html.replace(TEAM_SUMMARY_SCRIPT, ATTENDEE_DETAIL_SCRIPT)

    html = re.sub(
        r'const C = \{.*?\};',
        'const C = ' + json_data + ';',
        html, count=1, flags=re.S)

    if team_filter:
        out_path = None
        if _is_service_date(date_str, mode):
            archive_dir = _archive_dir(env)
            team_dir = os.path.join(archive_dir, 'teams')
            stamp = date_str.replace('-', '')
            date_dir = os.path.join(team_dir, stamp)
            os.makedirs(date_dir, exist_ok=True)
            out_path = os.path.join(date_dir, '출석_그래프_%s.html' % _safe_filename(team_filter))
            open(out_path, 'w', encoding='utf-8').write(html)
        return out_path
    else:
        open(_report_path(env), 'w', encoding='utf-8').write(html)
        if _is_service_date(date_str, mode):
            archive_dir = _archive_dir(env)
            os.makedirs(archive_dir, exist_ok=True)
            stamp = date_str.replace('-', '')
            archive_path = os.path.join(archive_dir, '출석_그래프_%s.html' % stamp)
            open(archive_path, 'w', encoding='utf-8').write(html)
        return _report_path(env)


def refresh_web_report(mode=None, env='commercial', date_str=None):
    expire_newbie_notes()  # 30일 경과 새신우 태그 자동 삭제
    conn = _db()
    if mode not in MODE_SHEETS:
        row = conn.execute("SELECT value FROM settings WHERE key='current_mode'").fetchone()
        mode = row['value'] if row else 'sunday'
    rows = conn.execute(
        "SELECT check_date FROM attendance WHERE mode=? AND env=? ORDER BY check_date DESC LIMIT 1",
        (mode, env)).fetchall()
    
    teams_rows = conn.execute("SELECT DISTINCT team FROM users WHERE team IS NOT NULL AND team != '' ORDER BY team").fetchall()
    conn.close()

    if not date_str:
        date_str = rows[0]['check_date'] if rows else datetime.date.today().isoformat()
    else:
        try:
            datetime.date.fromisoformat(date_str)
        except ValueError:
            date_str = rows[0]['check_date'] if rows else datetime.date.today().isoformat()
    
    # 1. Generate main/default report
    main_path = _render_report_for_team(date_str, mode, env, team_filter=None)

    # 2. Generate individual HTML files for specific teams (팀 이름 기반 파일명)
    team_list = [r['team'] for r in teams_rows]
    for idx, team in enumerate(team_list, start=1):
        _render_report_for_team(date_str, mode, env, team_filter=team, team_index=idx)

    # 3. 팀 폴더 정리: 날짜별 하위 폴더 내 현재 존재하지 않는 팀 파일 및 구 번호식 파일 제거
    team_dir = os.path.join(_archive_dir(env), 'teams')
    if os.path.isdir(team_dir):
        valid = {_safe_filename(t) for t in team_list}
        legacy = re.compile(r'^출석_그래프_팀\d+_.*\.html$')
        named = re.compile(r'^출석_그래프_(.+)\.html$')
        for entry in os.listdir(team_dir):
            fp = os.path.join(team_dir, entry)
            # 날짜별 하위 폴더 처리
            if os.path.isdir(fp) and re.fullmatch(r'\d{8}', entry):
                # 서비스 요일이 아닌 폴더 전체 제거 (예: 목요일 등)
                try:
                    d = datetime.date(int(entry[:4]), int(entry[4:6]), int(entry[6:8]))
                    wd = _mode_weekday(mode)
                    is_service = (wd is None) or (d.weekday() == wd)
                except ValueError:
                    is_service = False
                if not is_service:
                    for f in os.listdir(fp):
                        fp3 = os.path.join(fp, f)
                        if os.path.isfile(fp3):
                            os.remove(fp3)
                    os.rmdir(fp)
                    continue
                for f in os.listdir(fp):
                    fp2 = os.path.join(fp, f)
                    if not os.path.isfile(fp2):
                        continue
                    if legacy.match(f):
                        os.remove(fp2)
                        continue
                    m = named.match(f)
                    if m and m.group(1) not in valid:
                        os.remove(fp2)
                if not os.listdir(fp):
                    os.rmdir(fp)
            # 구 방식: 날짜 스탬프를 파일명에 포함한 채 teams 루트에 남은 파일 제거
            elif os.path.isfile(fp):
                old_named = re.compile(r'^출석_그래프_(.+)_\d{8}\.html$')
                m = old_named.match(entry)
                if legacy.match(entry) or (m and m.group(1) not in valid):
                    os.remove(fp)

    return main_path


if __name__ == '__main__':
    path = refresh_web_report()
    print('웹 보고서 갱신 완료:', path)
