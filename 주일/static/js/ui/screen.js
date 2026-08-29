/* ================================================================
   ui/screen.js — 화면 전환 관리
   ================================================================ */
(function () {
  'use strict';

  /**
   * 화면 전환 — 모든 .screen을 비활성화하고 대상 화면만 활성화.
   * @param {string} id - 표시할 screen 요소의 id (예: 'screen-confirm')
   */
  function show(id) {
    document.querySelectorAll('.screen').forEach(function (s) {
      s.classList.remove('active');
    });
    var el = window.$(id);
    if (el) el.classList.add('active');
    if (id === 'screen-main') {
      window.$('name-input').focus();
    }
  }

  window.screenManager = {
    show: show
  };
})();
