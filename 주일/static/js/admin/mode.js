/* ================================================================
   admin/mode.js — 일요일/수요일 모드 관리
   ================================================================ */
(function () {
  'use strict';

  var mode = '';

  /**
   * 현재 모드 반환 ('sunday'/'wednesday'/'').
   * @returns {string} 현재 모드
   */
  function get() {
    return mode;
  }

  /** 관리자 모드 버튼 활성화 상태 갱신. */
  function refresh() {
    document.querySelectorAll('.mode-admin-btn').forEach(function (b) {
      b.classList.toggle('active', b.dataset.mode === mode);
    });
  }

  /** 서버에서 모드 조회 후 화면에 반영. */
  function load() {
    window.api.getMode()
      .then(function (res) {
        mode = res.mode || '';
        var label = mode === 'wednesday' ? '수요일' : '일요일';
        var badge = window.$('mode-badge');
        badge.textContent = label;
        badge.classList.toggle('wed', mode === 'wednesday');
        window.$('env-badge').style.display = (res.env === 'dev') ? '' : 'none';
        window.searchManager.clear();
      });
  }

  /**
   * 모드 변경 — 서버에 저장 후 갱신. 실패 시 롤백.
   * @param {string} newMode - 'sunday' 또는 'wednesday'
   */
  function set(newMode) {
    var prev = mode;
    mode = newMode;
    refresh();
    var badge = window.$('mode-badge');
    badge.textContent = newMode === 'wednesday' ? '수요일' : '일요일';
    badge.classList.toggle('wed', newMode === 'wednesday');
    window.$('mode-admin-hint').textContent = newMode === 'wednesday' ? '수요일 모드로 전환됨 (전체 표시)' : '일요일 모드로 전환됨 (전체 표시)';
    window.api.setMode(newMode)
      .then(function (res) {
        if (res.ok) {
          load();
        } else {
          mode = prev;
          refresh();
          window.$('mode-admin-hint').textContent = res.msg || '모드 전환 실패';
        }
      });
  }

  /**
   * 모듈 초기화 — 모드 버튼 이벤트 등록.
   */
  function init() {
    document.querySelectorAll('.mode-admin-btn').forEach(function (b) {
      b.addEventListener('click', function () { set(b.dataset.mode); });
    });
  }

  window.modeManager = {
    init: init,
    get: get,
    refresh: refresh,
    load: load,
    set: set
  };
})();
