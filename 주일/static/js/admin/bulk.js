/* ================================================================
   admin/bulk.js — 일괄 출석 관리
   ================================================================ */
(function () {
  'use strict';

  var bulkNames = [];

  /** 일괄 탭 초기화 (결과/해결 영역 비움). */
  function loadBulk() {
    window.$('bulk-resolve').innerHTML = '';
    window.$('bulk-result').innerHTML = '';
  }

  /**
   * 입력값을 줄 단위로 파싱 (공백 제거 + 빈 줄 제거).
   * @returns {Array<string>} 이름 배열
   */
  function bulkParseNames() {
    return (window.$('bulk-names').value || '').split('\n')
      .map(function (s) { return s.trim(); })
      .filter(function (s) { return s; });
  }

  /**
   * 처리 결과 요약 HTML 생성.
   * @param {Object} res - bulk API 응답
   * @returns {string} 요약 HTML
   */
  function renderBulkSummary(res) {
    var ok = res.marked.filter(function (m) { return m.ok; }).length;
    var skip = res.marked.length - ok;
    var html = '<p class="bulk-sum">처리: 총 ' + res.count + '명 · 출석 ' + ok + '명' +
      (skip ? ' · 건너뜀 ' + skip + '명' : '') +
      (res.not_found.length ? ' · 미발견 ' + res.not_found.length + '명' : '') + '</p>';
    if (res.not_found.length) {
      html += '<p class="bulk-warn">명단에 없는 이름: ' +
        res.not_found.map(function (n) { return window.utils.esc(n.name); }).join(', ') + '</p>';
    }
    return html;
  }

  /** 일괄 출석 실행 (1차). */
  function submitBulk() {
    bulkNames = bulkParseNames();
    if (!bulkNames.length) { window.dialogManager.alert('이름을 입력하세요.', { title: '일괄 출석' }); return; }
    window.$('bulk-resolve').innerHTML = '처리 중...';
    window.$('bulk-result').innerHTML = '';
    window.api.bulkAttend(bulkNames, undefined)
      .then(function (res) {
        if (!res.ok) { window.$('bulk-resolve').innerHTML = ''; window.dialogManager.alert(res.msg || '오류', { title: '일괄 출석 실패' }); return; }
        window.$('bulk-result').innerHTML = renderBulkSummary(res);
        if (res.need_resolution) renderBulkResolve(res);
        else window.$('bulk-resolve').innerHTML = '';
      });
  }

  /**
   * 동명이인 해결 UI 렌더링.
   * @param {Object} res - need_resolution 응답
   */
  function renderBulkResolve(res) {
    var box = window.$('bulk-resolve');
    box.innerHTML = '<p class="bulk-warn">동명이인이 있어 올바른 사람을 선택해 주세요.</p>';
    var wrap = document.createElement('div');
    wrap.className = 'bulk-resolve-list';
    res.ambiguous.forEach(function (a) {
      var row = document.createElement('div');
      row.className = 'bulk-resolve-row';
      var label = document.createElement('div');
      label.className = 'bulk-resolve-name';
      label.textContent = a.name;
      var sel = document.createElement('select');
      sel.className = 'bulk-resolve-select';
      sel.dataset.index = a.index;
      var opt0 = document.createElement('option');
      opt0.value = ''; opt0.textContent = '선택하세요';
      sel.appendChild(opt0);
      a.candidates.forEach(function (c) {
        var o = document.createElement('option');
        o.value = c.id;
        o.textContent = (c.affiliation || '-') + ' · ' + (c.team || '-') +
          (c.birthday ? ' · 생일 ' + window.utils.fmtBirthday(c.birthday) : '');
        sel.appendChild(o);
      });
      row.appendChild(label);
      row.appendChild(sel);
      wrap.appendChild(row);
    });
    box.appendChild(wrap);
    var btn = document.createElement('button');
    btn.className = 'btn btn-primary';
    btn.textContent = '확정 처리';
    btn.addEventListener('click', function () {
      var doRun = function () {
        var choices = {};
        wrap.querySelectorAll('select.bulk-resolve-select').forEach(function (sel) {
          if (sel.value) choices[sel.dataset.index] = parseInt(sel.value, 10);
        });
        window.api.bulkAttend(bulkNames, choices)
          .then(function (r2) {
            if (!r2.ok) { window.dialogManager.alert(r2.msg || '오류', { title: '일괄 출석' }); return; }
            var ok2 = r2.marked.filter(function (m) { return m.ok; }).length;
            window.$('bulk-result').innerHTML += '<p class="bulk-sum">동명이인 처리: ' + ok2 + '명 출석 완료</p>';
            window.$('bulk-resolve').innerHTML = '';
          });
      };
      var incomplete = false;
      wrap.querySelectorAll('select.bulk-resolve-select').forEach(function (sel) {
        if (!sel.value) incomplete = true;
      });
      if (incomplete) {
        window.dialogManager.confirm('선택하지 않은 동명이인은 출석 처리되지 않습니다.\n계속할까요?', { title: '일괄 출석', okLabel: '계속' }, doRun);
      } else {
        doRun();
      }
    });
    box.appendChild(btn);
  }

  /**
   * 모듈 초기화 — 일괄 실행 버튼 이벤트 등록.
   */
  function init() {
    window.$('btn-bulk-run').addEventListener('click', submitBulk);
  }

  window.bulkManager = {
    init: init,
    load: loadBulk,
    renderBulkResolve: renderBulkResolve
  };
})();
