/* ================================================================
   components/adminmenu.js — 관리자 더보기(⋯) 메뉴 열기/닫기
   서버 종료 같은 위험 동작을 헤더에서 분리해 메뉴 안으로 격리한다.
   ================================================================ */
(function () {
  'use strict';

  var menu = null;
  var more = null;

  /** 메뉴 닫기(aria 상태 동기화). */
  function close() {
    if (!menu) return;
    if (!menu.classList.contains('open')) return;
    menu.classList.remove('open');
    more && more.setAttribute('aria-expanded', 'false');
  }

  /** 메뉴 열기(aria 상태 동기화). */
  function open() {
    if (!menu) return;
    menu.classList.add('open');
    more && more.setAttribute('aria-expanded', 'true');
  }

  /**
   * 모듈 초기화 — ⋯ 버튼 토글 + 외부 클릭/Escape 닫기 등록.
   */
  function init() {
    menu = window.$('admin-menu');
    more = window.$('btn-more');
    if (!menu || !more) return;

    more.addEventListener('click', function (e) {
      e.stopPropagation();
      menu.classList.contains('open') ? close() : open();
    });

    document.addEventListener('mousedown', function (e) {
      if (menu.classList.contains('open') && !menu.contains(e.target) && e.target !== more && !more.contains(e.target)) {
        close();
      }
    });

    document.addEventListener('keydown', function (e) {
      if (e.key === 'Escape') close();
    });
  }

  window.adminMenuManager = {
    init: init,
    open: open,
    close: close
  };
})();