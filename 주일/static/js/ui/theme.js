/* ================================================================
   ui/theme.js — 라이트/다크 테마 관리
   ================================================================ */
(function () {
  'use strict';

  var THEME_KEY = 'kiosk-theme';

  /**
   * 현재 테마 문자열 반환.
   * @returns {string} 'light' 또는 'dark'
   */
  function current() {
    return document.documentElement.getAttribute('data-theme') === 'light' ? 'light' : 'dark';
  }

  /**
   * 테마 버튼 아이콘 갱신.
   * @param {HTMLElement} btn - 테마 토글 버튼
   */
  function paintThemeButton(btn) {
    var dark = current() === 'dark';
    btn.innerHTML = dark
      ? '<span class="ic" aria-hidden="true"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="4"/><path d="M12 2v2m0 16v2M4.9 4.9l1.4 1.4m11.4 11.4 1.4 1.4M2 12h2m16 0h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4"/></svg></span>라이트'
      : '<span class="ic" aria-hidden="true"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 12.8A9 9 0 1 1 11.2 3 7 7 0 0 0 21 12.8z"/></svg></span>다크';
  }

  /**
   * 테마 적용.
   * @param {string} theme - 'light' 또는 'dark'
   * @param {boolean} persist - localStorage에 저장 여부
   */
  function apply(theme, persist) {
    document.documentElement.setAttribute('data-theme', theme);
    if (persist) { try { localStorage.setItem(THEME_KEY, theme); } catch (e) {} }
    var btn = window.$('btn-theme');
    if (btn) paintThemeButton(btn);
  }

  /** 테마 토글 (버튼 클릭 시). */
  function toggle() {
    var next = current() === 'dark' ? 'light' : 'dark';
    apply(next, true);
    window.dialogManager.toast(next === 'dark' ? '다크 모드로 전환되었습니다.' : '라이트 모드로 전환되었습니다.');
  }

  /**
   * 초기 테마 결정 및 적용.
   * localStorage 우선, 없으면 OS 선호, 그 외 계속 변경 감지.
   */
  function initTheme() {
    var saved = null;
    try { saved = localStorage.getItem(THEME_KEY); } catch (e) {}
    var initial = (saved === 'light' || saved === 'dark') ? saved
      : (window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches) ? 'dark' : 'light';
    apply(initial, false);
    if (saved === null && window.matchMedia) {
      window.matchMedia('(prefers-color-scheme: dark)').addEventListener('change', function (m) {
        apply(m.matches ? 'dark' : 'light', false);
      });
    }
  }

  /**
   * 모듈 초기화 — 테마 적용 및 버튼 이벤트 등록.
   */
  function init() {
    initTheme();
    var btn = window.$('btn-theme');
    if (btn) btn.addEventListener('click', toggle);
  }

  window.themeManager = {
    init: init,
    current: current,
    apply: apply,
    toggle: toggle
  };
})();
