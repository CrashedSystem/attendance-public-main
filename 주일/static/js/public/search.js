/* ================================================================
   public/search.js — 사용자 검색 및 소속별 그룹 렌더링
   ================================================================ */
(function () {
  'use strict';

  var text = '';
  var lastSearch = null;
  var searchSeq = 0;

  /**
   * 검색 실행 — 서버에서 사용자 목록 조회 후 렌더링.
   * 입력값이 직전 검색과 같으면 무시(불필요한 요청 방지).
   * 응답 시점에 최신 검색(세대 번호)과 다르면 무시(이전 검색 응답이 지연 도착해도 안 덮어쓴다).
   * @param {string} q - 검색어
   */
  function search(q) {
    q = (q || '').trim();
    if (q === lastSearch) return;
    lastSearch = q;
    var seq = ++searchSeq;
    var box = window.$('suggestions');
    var mode = window.modeManager.get();
    window.api.searchUsers(q, mode)
      .then(function (users) {
        if (seq !== searchSeq) return;
        box.innerHTML = '';
        if (!users.length) {
          var d = document.createElement('div');
          d.className = 'no-result';
          d.textContent = '검색 결과가 없습니다';
          box.appendChild(d);
          return;
        }
        if (!q) {
          renderGrouped(users);
          return;
        }
        var grid = document.createElement('div');
        grid.className = 'result-grid';
        var nameCounts = {};
        users.forEach(function (u) { nameCounts[u.name] = (nameCounts[u.name] || 0) + 1; });
        users.forEach(function (u) {
          var el = document.createElement('div');
          el.className = 'suggestion';
          var sub = u.affiliation || '';
          if (nameCounts[u.name] > 1 && u.birthday) {
            sub += (sub ? ' · ' : '') + '생일 ' + window.utils.fmtBirthday(u.birthday);
          }
          el.innerHTML = '<div class="s-name">' + window.utils.esc(u.name) + '</div>' +
            '<div class="s-aff">' + window.utils.esc(sub) + '</div>';
          el.addEventListener('click', function () { window.checkinManager.select(u); });
          grid.appendChild(el);
        });
        box.appendChild(grid);
      });
  }

  /**
   * 소속별 그룹(폴더) 형태로 전체 사용자 렌더링.
   * @param {Array} users - 사용자 목록
   */
  function renderGrouped(users) {
    var box = window.$('suggestions');
    var mode = window.modeManager.get();
    var groups = {};
    var order = [];
    users.forEach(function (u) {
      var aff = u.affiliation || '기타';
      if (!groups[aff]) { groups[aff] = []; order.push(aff); }
      groups[aff].push(u);
    });
    if (order.length > 1) {
      var toolbar = document.createElement('div');
      toolbar.className = 'group-toolbar';
      var btn = document.createElement('button');
      btn.className = 'btn-toggle-all';
      var allOpen = mode === 'wednesday';
      if (allOpen) box.classList.add('all-open');
      btn.textContent = allOpen ? '전체 접기' : '전체 펼치기';
      btn.addEventListener('click', function () {
        var open = box.classList.toggle('all-open');
        box.querySelectorAll('.group').forEach(function (g) {
          if (open) g.classList.add('open');
          else g.classList.remove('open');
        });
        btn.textContent = open ? '전체 접기' : '전체 펼치기';
      });
      toolbar.appendChild(btn);
      box.appendChild(toolbar);
    }
    order.forEach(function (aff) {
      var sec = document.createElement('div');
      sec.className = 'group' + (mode === 'wednesday' ? ' open' : '');
      var head = document.createElement('div');
      head.className = 'group-head';
      var label = document.createElement('span');
      label.className = 'group-label';
      label.textContent = aff;
      var count = document.createElement('span');
      count.className = 'group-count';
      count.textContent = groups[aff].length + '명';
      head.appendChild(label);
      head.appendChild(count);
      sec.appendChild(head);
      var grid = document.createElement('div');
      grid.className = 'group-grid';
      var affNameCounts = {};
      groups[aff].forEach(function (u) { affNameCounts[u.name] = (affNameCounts[u.name] || 0) + 1; });
      groups[aff].forEach(function (u) {
        var b = document.createElement('button');
        b.className = 'name-chip';
        var labelText = u.name;
        if (affNameCounts[u.name] > 1 && u.birthday) {
          labelText += ' · ' + window.utils.fmtBirthday(u.birthday);
        }
        b.textContent = labelText;
        b.addEventListener('click', function () { window.checkinManager.select(u); });
        grid.appendChild(b);
      });
      sec.appendChild(grid);
      head.addEventListener('click', function () { sec.classList.toggle('open'); });
      box.appendChild(sec);
    });
  }

  /**
   * 검색/선택 상태 초기화 (메인으로 복귀할 때 등).
   */
  function clear() {
    var input = window.$('name-input');
    input.value = '';
    text = '';
    lastSearch = null;
    search('');
  }

  /**
   * 검색 모듈 초기화 — 입력 이벤트 등록 + 초기 검색 수행.
   */
  function init() {
    var inputEl = window.$('name-input');
    inputEl.addEventListener('input', function () {
      text = inputEl.value;
      lastSearch = null;
      search(text);
    });
    inputEl.addEventListener('keydown', function (e) {
      if (e.key === 'Enter') {
        var first = document.querySelector('.suggestion, .name-chip');
        if (!first) first = document.querySelector('.group-head');
        if (first) first.click();
      }
    });
    search('');
  }

  window.searchManager = {
    init: init,
    search: search,
    clear: clear
  };
})();
