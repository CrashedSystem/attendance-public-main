/* ================================================================
   admin/auth.js — 관리자 PIN 인증 및 관리자 화면 진입
   ================================================================ */
(function () {
  'use strict';

  var pinValue = '';
  var adminPin = '';
  var KP = ['1', '2', '3', '4', '5', '6', '7', '8', '9', '지우기', '0', '확인'];

  /** PIN 키패드 DOM 생성. */
  function buildPinKeypad() {
    var kp = window.$('pin-keypad');
    KP.forEach(function (k) {
      var key = document.createElement('div');
      key.className = 'kp-key';
      key.textContent = k;
      key.addEventListener('click', function () { onPinKey(k); });
      kp.appendChild(key);
    });
  }

  /**
   * 키패드 입력 처리.
   * @param {string} k - 누른 키 (숫자/지우기/확인)
   */
  function onPinKey(k) {
    if (k === '확인') {
      if (!pinValue) return;
      window.api.adminLogin(pinValue)
        .then(function (res) {
          if (res.ok) {
            adminPin = pinValue;
            pinValue = '';
            openAdmin();
          }
          else { window.$('pin-error').textContent = res.msg || 'PIN 오류'; pinValue = ''; refreshPin(); }
        });
      return;
    }
    if (k === '지우기') pinValue = pinValue.slice(0, -1);
    else pinValue += k;
    refreshPin();
  }

  /** PIN 표시 갱신 (••••• 형태). */
  function refreshPin() {
    window.$('pin-display').innerHTML = pinValue ? pinValue.replace(/./g, '•') : '&nbsp;';
  }

  /** 관리자 화면 오픈 — 각 탭 데이터 로드. */
  function openAdmin() {
    window.screenManager.show('screen-admin');
    window.modeManager.refresh();
    window.rosterManager.load();
    window.attendanceManager.load();
    window.teamManager.loadTab();
  }

  /**
   * 모듈 초기화 — admin-zone 클릭 + admin-back 클릭 + 키패드 생성 등록.
   */
  function init() {
    buildPinKeypad();
    window.$('admin-zone').addEventListener('click', function () {
      pinValue = '';
      window.$('pin-display').innerHTML = '&nbsp;';
      window.$('pin-error').textContent = '';
      window.screenManager.show('screen-admin-login');
    });
    window.$('btn-admin-back').addEventListener('click', function () {
      window.searchManager.clear();
      window.screenManager.show('screen-main');
    });
  }

  /**
   * 저장된 관리자 PIN 반환 (API 헤더 자동 첨부용).
   * @returns {string}
   */
  function getPin() {
    return adminPin;
  }

  /**
   * 관리자 PIN 저장/갱신.
   * @param {string} pin
   */
  function setPin(pin) {
    adminPin = pin;
  }

  window.authManager = {
    init: init,
    openAdmin: openAdmin,
    getPin: getPin,
    setPin: setPin
  };
})();
