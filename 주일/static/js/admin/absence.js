/* ================================================================
   admin/absence.js — 수요 결석 관리
   ================================================================ */
(function () {
  'use strict';

  var ABS_TAGS = ['휴가', '외박', '근무', '입원', '훈련'];
  var absDate = '';

  /** 결석 탭 로드 시 초기화 (기본 = 최근 수요일). */
  function loadTab() {
    if (!absDate) { absDate = window.utils.mostRecentWed(); window.$('abs-date').value = absDate; }
    load();
  }

  /** 결석자 목록 조회. */
  function load() {
    window.api.getAbsences(absDate)
      .then(function (res) {
        if (!res.ok) { window.$('abs-list').innerHTML = '<p class="abs-empty">조회 실패</p>'; return; }
        renderAbsenceList(res.absentees || []);
      });
  }

  /**
   * 결석자 테이블 렌더링.
   * @param {Array} list - 결석자 목록
   */
  function renderAbsenceList(list) {
    var wrap = window.$('abs-list');
    if (!list.length) {
      wrap.innerHTML = '<div class="abs-empty">해당 수요일에 미출석한 군종병이 없습니다.</div>';
      return;
    }
    var html = '<table class="abs-table"><tr><th>No</th><th>이름</th><th>소속</th><th>팀</th><th>결석 사유</th><th>이전 주차 기록</th></tr>';
    list.forEach(function (u) {
      var reasonVal = u.absence ? (u.absence.reason || '') : '';
      var histHtml = (u.history || []).map(function (h) {
        return '<span class="abs-hist-chip">' + window.utils.fmtShortDate(h.date) + ' ' + window.utils.esc(h.reason) + '</span>';
      }).join('');
      if (!histHtml) histHtml = '<span class="abs-hist-none">-</span>';
      html += '<tr><td>' + u.id + '</td>' +
        '<td>' + window.utils.esc(u.name) + '</td>' +
        '<td>' + window.utils.esc(u.affiliation) + '</td>' +
        '<td>' + window.utils.esc(u.team) + '</td>' +
        '<td class="abs-reason-cell">' +
          '<span class="abs-tags">' +
            ABS_TAGS.map(function (t) {
              var cls = reasonVal === t ? ' active' : '';
              return '<button class="abs-tag' + cls + '" data-uid="' + u.id + '" data-tag="' + t + '">' + t + '</button>';
            }).join('') +
          '</span>' +
          '<input type="text" class="abs-reason" id="abs-reason-' + u.id + '" value="' + window.utils.escAttr(reasonVal) + '" placeholder="사유 직접 입력">' +
          '<button class="mini-btn edit abs-save" data-uid="' + u.id + '">저장</button>' +
          (u.absence ? '<button class="mini-btn del abs-del" data-uid="' + u.id + '" data-aid="' + u.absence.id + '">사유 삭제</button>' : '') +
        '</td>' +
        '<td class="abs-hist">' + histHtml + '</td></tr>';
    });
    wrap.innerHTML = html + '</table>';
    wrap.querySelectorAll('.abs-tag').forEach(function (b) {
      b.addEventListener('click', function () {
        var inp = window.$('abs-reason-' + b.dataset.uid);
        wrap.querySelectorAll('.abs-tag').forEach(function (x) { x.classList.remove('active'); });
        b.classList.add('active');
        inp.value = b.dataset.tag;
        inp.focus();
      });
    });
    wrap.querySelectorAll('.abs-save').forEach(function (b) {
      b.addEventListener('click', function () {
        save(parseInt(b.dataset.uid, 10), window.$('abs-reason-' + b.dataset.uid).value.trim());
      });
    });
    wrap.querySelectorAll('.abs-del').forEach(function (b) {
      b.addEventListener('click', function () {
        remove(b.dataset.uid, parseInt(b.dataset.aid, 10));
      });
    });
  }

  /**
   * 결석 사유 저장.
   * @param {number} uid - 사용자 id
   * @param {string} reason - 사유
   */
  function save(uid, reason) {
    window.api.saveAbsence(uid, absDate, reason)
      .then(function (res) {
        if (res.ok) { window.dialogManager.toast('결석 사유가 저장되었습니다.'); load(); }
        else window.dialogManager.alert(res.msg || '저장 실패', { title: '저장 실패' });
      });
  }

  /**
   * 결석 사유 삭제.
   * @param {number} uid - 사용자 id (표시용)
   * @param {number} aid - 결석 레코드 id
   */
  function remove(uid, aid) {
    window.dialogManager.confirm('이 결석 사유를 삭제할까요?', { title: '사유 삭제', destructive: true }, function () {
      window.api.deleteAbsence(aid)
        .then(function (res) {
          if (res.ok) { window.dialogManager.toast('결석 사유를 삭제했습니다.'); load(); }
          else window.dialogManager.alert(res.msg || '삭제 실패', { title: '삭제 실패' });
        });
    });
  }

  /**
   * 결석 날짜 이동 (7일/14일 뒤로).
   * @param {number} days - 이동할 일수
   */
  function shiftAbsDate(days) {
    var d = new Date(absDate + 'T00:00:00');
    d.setDate(d.getDate() - days);
    var m = String(d.getMonth() + 1).padStart(2, '0');
    var day = String(d.getDate()).padStart(2, '0');
    absDate = d.getFullYear() + '-' + m + '-' + day;
    window.$('abs-date').value = absDate;
    load();
  }

  /**
   * 모듈 초기화 — 날짜/버튼 이벤트 등록.
   */
  function init() {
    window.$('abs-date').addEventListener('change', function () {
      absDate = this.value;
      if (absDate) load();
    });
    window.$('btn-abs-prev1').addEventListener('click', function () { shiftAbsDate(7); });
    window.$('btn-abs-prev2').addEventListener('click', function () { shiftAbsDate(14); });
  }

  window.absenceManager = {
    init: init,
    loadTab: loadTab,
    load: load
  };
})();
