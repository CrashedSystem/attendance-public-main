/* ================================================================
   public/checkin.js — 2단계 출석 확인 및 결과 화면
   ================================================================ */
(function () {
  'use strict';

  var pendingUser = null;

  /**
   * 사용자 선택 — 확인 화면에 정보 표시.
   * @param {Object} u - 선택된 사용자 객체
   */
  function select(u) {
    pendingUser = u;
    window.$('confirm-name').textContent = u.name;
    var sub = '소속: ' + (u.affiliation || '-');
    if (u.birthday) sub += ' · 생일: ' + window.utils.fmtBirthday(u.birthday);
    window.$('confirm-sub').textContent = sub;
    window.screenManager.show('screen-confirm');
  }

  /** 확인 버튼 처리 — 서버에 체크인 요청. */
  function onOk() {
    var u = pendingUser;
    if (!u) return;
    window.api.checkin(u.id)
      .then(function (res) {
        if (res.ok) showResult(true, res.name + '님 출석 완료', '출석 시각 ' + res.time + ' · 누적 ' + (res.weeks || 0) + '주차 출석 중!');
        else showResult(false, res.msg || '오류가 발생했습니다', '');
      });
  }

  /** 취소 버튼 처리 — 메인으로 복귀. */
  function onCancel() {
    pendingUser = null;
    window.screenManager.show('screen-main');
  }

  /**
   * 결과 화면 표시 — 성공 1.5초, 실패 3초 후 메인 복귀.
   * @param {boolean} ok - 성공 여부
   * @param {string} msg - 메시지
   * @param {string} sub - 보조 메시지
   */
  function showResult(ok, msg, sub) {
    window.$('result-icon').textContent = ok ? '✓' : '✕';
    window.$('result-icon').className = 'result-icon ' + (ok ? 'ok' : 'err');
    window.$('result-msg').textContent = msg;
    window.$('result-sub').textContent = sub || '';
    window.screenManager.show('screen-result');
    setTimeout(function () {
      window.searchManager.clear();
      window.screenManager.show('screen-main');
    }, ok ? 1500 : 3000);
  }

  /**
   * 모듈 초기화 — 확인/취소 버튼 이벤트 등록.
   */
  function init() {
    window.$('btn-ok').addEventListener('click', onOk);
    window.$('btn-cancel').addEventListener('click', onCancel);
  }

  window.checkinManager = {
    init: init,
    select: select,
    showResult: showResult
  };
})();
