/* ================================================================
   admin/auth.js — 관리자 PIN 인증 및 관리자 화면 진입
   ================================================================ */
(function () {
  'use strict';

  var pinValue = '';
  var adminPin = '';
  var MAX_PIN = 12; // config.py의 ADMIN_PIN은 .admin_pin 파일/환경변수로 길이 변경 가능 → 고정 4자리 금지
  var pinDots = [];
  var KP = ['1', '2', '3', '4', '5', '6', '7', '8', '9', '지우기', '0', '확인'];

  /** PIN dot 인디케이터 DOM 캐시. */
  function cacheDots() {
    var dots = window.$('pin-dots');
    pinDots = dots ? Array.prototype.slice.call(dots.querySelectorAll('.pin-dot')) : [];
  }

  /** PIN 키패드 DOM 생성 (버튼 계열로 강조 구분). */
  function buildPinKeypad() {
    var kp = window.$('pin-keypad');
    KP.forEach(function (k) {
      var key = document.createElement('button');
      key.type = 'button';
      key.className = 'kp-key' + (k === '확인' ? ' kp-confirm' : k === '지우기' ? ' kp-backspace' : ' kp-num');
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
            refreshPin();
            openAdmin();
          }
          else { window.$('pin-error').textContent = res.msg || 'PIN 오류'; pinValue = ''; refreshPin(); }
        });
      return;
    }
    if (k === '지우기') pinValue = pinValue.slice(0, -1);
    else if (pinValue.length < MAX_PIN) pinValue += k;
    refreshPin();
  }

  /** PIN dot 인디케이터 갱신. */
  function refreshPin() {
    if (!pinDots.length) cacheDots();
    pinDots.forEach(function (d, i) {
      d.classList.toggle('filled', i < pinValue.length);
    });
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
   * PIN 화면 닫고 메인으로 복귀 (입력 값 초기화).
   */
  function cancelLogin() {
    pinValue = '';
    window.$('pin-error').textContent = '';
    refreshPin();
    window.screenManager.show('screen-main');
  }

  /**
   * 모듈 초기화 — admin-zone 클릭 + admin-back 클릭 + 키패드 생성 등록.
   */
  function init() {
    cacheDots();
    buildPinKeypad();
    window.$('admin-zone').addEventListener('click', function () {
      pinValue = '';
      window.$('pin-error').textContent = '';
      refreshPin();
      window.screenManager.show('screen-admin-login');
    });
    window.$('btn-pin-back').addEventListener('click', cancelLogin);
    document.addEventListener('keydown', function (e) {
      if (e.key === 'Escape' && window.$('screen-admin-login').classList.contains('active')) {
        cancelLogin();
      }
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
