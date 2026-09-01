/* ================================================================
   components/tabs.js — 관리자 탭 전환
   ================================================================ */
(function () {
  'use strict';

  /**
   * 탭 클릭 시 활성 탭 전환 및 해당 모듈 데이터 로드.
   * @param {string} tab - 데이터 탭 이름 (roster/attend/bulk/teams/absences/history)
   */
  function activate(tab) {
    document.querySelectorAll('.tab').forEach(function (x) { x.classList.remove('active'); });
    document.querySelectorAll('.tab-panel').forEach(function (p) { p.classList.remove('active'); });
    var el = window.$('tab-' + tab);
    if (!el) return;
    el.classList.add('active');
    document.querySelectorAll('.tab').forEach(function (x) {
      if (x.dataset.tab === tab) {
        x.classList.add('active');
        x.setAttribute('aria-selected', 'true');
      } else {
        x.setAttribute('aria-selected', 'false');
      }
    });

    if (tab === 'roster') window.rosterManager.load();
    else if (tab === 'teams') window.teamManager.loadTab();
    else if (tab === 'bulk') window.bulkManager.load();
    else if (tab === 'absences') window.absenceManager.loadTab();
    else if (tab === 'history') window.historyManager.loadTab();
    else if (tab === 'import') window.importManager.loadTab();
    else window.attendanceManager.load();
  }

  /**
   * 모듈 초기화 — 탭 클릭 이벤트 등록.
   */
  function init() {
    document.querySelectorAll('.tab').forEach(function (t) {
      t.addEventListener('click', function () { activate(t.dataset.tab); });
    });
  }

  window.tabsManager = {
    init: init,
    activate: activate
  };
})();
