/* ================================================================
   admin/roster.js — 명단 관리 (검색·필터·정렬·수정·삭제)
   ================================================================ */
(function () {
  'use strict';

  var rosterUsers = [];

  /**
   * 정렬 키에 따른 정렬값 계산.
   * @param {Object} u - 사용자 객체
   * @param {string} key - 정렬 키 (name/team/birthday/id)
   * @returns {*} 정렬에 사용할 값
   */
  function sortValue(u, key) {
    if (key === 'name') return (u.name || '').toLowerCase();
    if (key === 'team') return (u.team || '') + ' ' + (u.affiliation || '');
    if (key === 'birthday') return u.birthday ? u.birthday.match(/^\d{4}$/) ? u.birthday : '9999' : '9999';
    return u.id;
  }

  /**
   * 정렬 select 값에서 실제 정렬 키 추출.
   * @param {string} v - 예: 'name_asc', 'birthday_desc'
   * @returns {string} 정렬 키
   */
  function rosterSortKey(v) {
    var m = v.match(/^(name|birthday|team|id)_?(asc|desc)?$/);
    return m ? m[1] : 'id';
  }

  /** 명단 테이블 렌더링. */
  function renderRoster(users) {
    var html = '<table><tr><th>No</th><th>이름</th><th>군종</th><th>세례</th><th>소속</th><th>팀</th><th>기존 교회</th><th>생일</th><th>연락처</th><th>전역일자</th><th>비고</th><th></th></tr>';
    users.forEach(function (u) {
      html += '<tr><td>' + u.id + '</td><td>' + window.utils.esc(u.name) + '</td>' +
        (u.is_chaplain ? '<td><span class="chaplain-badge">군종</span></td>' : '<td></td>') +
        '<td>' + window.utils.esc(u.baptism || '') + '</td>' +
        '<td>' + window.utils.esc(u.affiliation || '') + '</td>' +
        '<td>' + window.utils.esc(u.team || '') + '</td>' +
        '<td>' + window.utils.esc(u.prev_church || '') + '</td>' +
        '<td>' + window.utils.fmtBirthdayDisplay(u.birthday) + '</td>' +
        '<td>' + window.utils.esc(u.phone || '') + '</td><td>' + window.utils.esc(u.discharge_date || '') + '</td>' +
        '<td>' + window.utils.esc(u.note || '') + '</td>' +
        '<td class="row-actions"><button class="mini-btn edit" data-edit="' + u.id + '">수정</button>' +
        '<button class="mini-btn del" data-del="' + u.id + '">삭제</button></td></tr>';
    });
    html += '</table>';
    var wrap = window.$('roster-table-wrap');
    wrap.innerHTML = html;
    wrap.querySelectorAll('[data-edit]').forEach(function (b) {
      b.addEventListener('click', function () { window.userFormManager.open(parseInt(b.dataset.edit, 10)); });
    });
    wrap.querySelectorAll('[data-del]').forEach(function (b) {
      b.addEventListener('click', function () { deleteUser(parseInt(b.dataset.del, 10)); });
    });
  }

  /**
   * 검색/필터/정렬 적용 후 테이블 갱신.
   */
  function filterRoster() {
    var q = (window.$('roster-search').value || '').trim().toLowerCase();
    var aff = window.$('roster-filter-aff').value;
    var team = window.$('roster-filter-team').value;
    var bap = window.$('roster-filter-baptism').value;
    var ch = window.$('roster-filter-chaplain').value;
    var sort = window.$('roster-sort').value;
    var key = rosterSortKey(sort);
    var desc = sort.indexOf('desc') !== -1;

    var filtered = rosterUsers.filter(function (u) {
      if (q && ((u.name || '') + ' ' + (u.affiliation || '') + ' ' + (u.team || '')).toLowerCase().indexOf(q) === -1) return false;
      if (aff && (u.affiliation || '') !== aff) return false;
      if (team && (u.team || '') !== team) return false;
      if (bap === 'blank') { if (u.baptism) return false; }
      else if (bap && !u.baptism) return false;
      else if (bap === 'O' || bap === 'X') { if ((u.baptism || '') !== bap) return false; }
      if (ch !== '' && (u.is_chaplain ? 1 : 0) !== parseInt(ch, 10)) return false;
      return true;
    });

    var cmp = key === 'id' ? function (a, b) { return a.id - b.id; } : function (a, b) {
      var x = sortValue(a, key), y = sortValue(b, key);
      if (x < y) return -1; if (x > y) return 1; return a.id - b.id;
    };
    if (desc) filtered = filtered.slice().sort(function (a, b) { return -cmp(a, b); });
    else filtered = filtered.slice().sort(cmp);
    renderRoster(filtered);
  }

  /** 필터 드롭다운(소속/팀)을 현재 목록 기준으로 채움. */
  function populateRosterFilters() {
    var affs = {}, teams = {};
    rosterUsers.forEach(function (u) {
      if (u.affiliation) affs[u.affiliation] = 1;
      if (u.team) teams[u.team] = 1;
    });
    var affSel = window.$('roster-filter-aff');
    var curA = affSel.value;
    affSel.innerHTML = '<option value="">소속 전체</option>';
    Object.keys(affs).sort().forEach(function (a) {
      var o = document.createElement('option'); o.value = a; o.textContent = a; affSel.appendChild(o);
    });
    affSel.value = curA;
    var teamSel = window.$('roster-filter-team');
    var curT = teamSel.value;
    teamSel.innerHTML = '<option value="">팀 전체</option>';
    Object.keys(teams).sort().forEach(function (t) {
      var o = document.createElement('option'); o.value = t; o.textContent = t; teamSel.appendChild(o);
    });
    teamSel.value = curT;
  }

  /** 명단 로드 후 필터/정렬 반영. */
  function load() {
    window.api.getUsers()
      .then(function (users) {
        rosterUsers = users;
        populateRosterFilters();
        filterRoster();
      });
  }

  /**
   * 사용자 삭제 확인 및 실행.
   * @param {number} id - 사용자 id
   */
  function deleteUser(id) {
    window.dialogManager.confirm('No.' + id + ' 사용자를 삭제하시겠습니까?', { title: '사용자 삭제', okLabel: '삭제', destructive: true }, function () {
      window.api.deleteUser(id)
        .then(function () { window.dialogManager.toast('사용자를 삭제했습니다.'); load(); });
    });
  }

  /**
   * 모듈 초기화 — 검색/필터/정렬 이벤트 등록.
   */
  function init() {
    window.$('roster-search').addEventListener('input', filterRoster);
    window.$('roster-filter-aff').addEventListener('change', filterRoster);
    window.$('roster-filter-team').addEventListener('change', filterRoster);
    window.$('roster-filter-baptism').addEventListener('change', filterRoster);
    window.$('roster-filter-chaplain').addEventListener('change', filterRoster);
    window.$('roster-sort').addEventListener('change', filterRoster);
  }

  window.rosterManager = {
    init: init,
    load: load,
    filter: filterRoster
  };
})();
