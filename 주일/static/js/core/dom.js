/* ================================================================
   core/dom.js — DOM 헬퍼 ($)
   ================================================================ */
(function () {
  'use strict';

  /**
   * 아이디로 요소를 조회한다.
   * @param {string} id - 요소의 id
   * @returns {HTMLElement|null} 해당 요소
   */
  function byId(id) {
    return document.getElementById(id);
  }

  window.$ = byId;

  window.dom = {
    byId: byId
  };
})();
