/* ================================================================
   ui/dialog.js — iOS 스타일 다이얼로그 / 토스트 / 액션시트 헬퍼
   ================================================================ */
(function () {
  'use strict';

  var iosLayerEl = null;
  var iosDialogEl = null;
  var iosToastEl = null;
  var iosTimer = null;
  var iosLastFocus = null;

  /**
   * 초기화 — 필요한 DOM 요소를 캐시하고 Enter/Escape 키 처리 등록.
   */
  function init() {
    iosLayerEl = window.$('ios-layer');
    if (!iosLayerEl) return;
    iosDialogEl = iosLayerEl.querySelector('.ios-dialog');
    iosToastEl = window.$('ios-toast');
    iosDialogEl.addEventListener('keydown', onDialogKey);
  }

  /**
   * 커스텀 다이얼로그 표시.
   * @param {Object|string} o - 다이얼로그 옵션 또는 메시지 문자열
   * @param {string} [o.title] - 제목
   * @param {string} [o.message] - 본문
   * @param {Array} [o.buttons] - 버튼 배열 [{label, value, style}]
   * @param {Function} [o.onResult] - 결과 콜백(value 전달)
   */
  function show(o) {
    if (typeof o !== 'object') o = { message: String(o || '') };
    var title = o.title || '알림';
    var msg = o.message || '';
    iosDialogEl.innerHTML =
      '<div class="d-title" id="ios-dialog-title">' + window.utils.esc(title) + '</div>' +
      (msg ? '<div class="d-msg">' + window.utils.esc(msg) + '</div>' : '') +
      '<div class="d-btns"></div>';
    var btns = document.querySelector('#ios-layer .d-btns');
    var focusTarget = null;
    (o.buttons || [{ label: '확인', value: true }]).forEach(function (b) {
      var btn = document.createElement('button');
      btn.className = 'd-btn' + (b.style ? ' ' + b.style : '');
      btn.textContent = b.label;
      if (!focusTarget) focusTarget = btn;
      btn.addEventListener('click', function () {
        close();
        if (o.onResult) o.onResult(b.value);
      });
      btns.appendChild(btn);
    });
    iosLastFocus = document.activeElement;
    iosLayerEl.classList.add('open');
    iosLayerEl.setAttribute('aria-hidden', 'false');
    if (focusTarget) focusTarget.focus();
  }

  /**
   * 다이얼로그 키보드 처리 (Enter=마지막, Escape=취소(첫번째)).
   * @param {Event} e - keydown 이벤트
   */
  function onDialogKey(e) {
    if (e.key !== 'Enter' && e.key !== 'Escape') return;
    var btns = document.querySelectorAll('#ios-layer .d-btn');
    if (!btns.length) return;
    e.preventDefault();
    var target = e.key === 'Enter' ? btns[btns.length - 1] : btns[0];
    target.click();
  }

  /** 다이얼로그 닫기 + 이전 포커스 복원. */
  function close() {
    if (!iosLayerEl) return;
    iosLayerEl.classList.remove('open');
    iosLayerEl.setAttribute('aria-hidden', 'true');
    if (iosLastFocus && iosLastFocus.focus) iosLastFocus.focus();
  }

  /**
   * 확인/취소 다이얼로그.
   * @param {string} message - 본문
   * @param {Object} [opts] - {title, cancelLabel, okLabel, destructive}
   * @param {Function} [onOk] - 확인 시 콜백
   */
  function confirm(message, opts, onOk) {
    if (typeof opts === 'function') { onOk = opts; opts = {}; }
    opts = opts || {};
    show({
      title: opts.title || '확인',
      message: message,
      buttons: [
        { label: opts.cancelLabel || '취소', value: false, style: 'cancel' },
        { label: opts.okLabel || '확인', value: true, style: opts.destructive ? 'destructive' : 'primary' }
      ],
      onResult: function (v) { if (v && onOk) onOk(); }
    });
  }

  /**
   * 알럿 다이얼로그.
   * @param {string} message - 본문
   * @param {Object} [opts] - {title, okLabel}
   * @param {Function} [onDone] - 확인 시 콜백
   */
  function alert(message, opts, onDone) {
    if (typeof opts === 'function') { onDone = opts; opts = {}; }
    opts = opts || {};
    show({
      title: opts.title || '알림',
      message: message,
      buttons: [{ label: opts.okLabel || '확인', value: true, style: 'primary' }],
      onResult: function () { if (onDone) onDone(); }
    });
  }

  /**
   * 토스트 메시지 표시 — 2.6초 후 자동 사라짐.
   * @param {string} message - 표시할 메시지
   */
  function toast(message) {
    if (!iosToastEl) return;
    iosToastEl.innerHTML =
      '<span class="ic" aria-hidden="true"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round"><path d="M5 12l5 5 9-10"/></svg></span>' +
      '<span>' + window.utils.esc(message) + '</span>';
    iosToastEl.classList.add('show');
    iosToastEl.setAttribute('aria-hidden', 'false');
    clearTimeout(iosTimer);
    iosTimer = setTimeout(function () {
      iosToastEl.classList.remove('show');
      iosToastEl.setAttribute('aria-hidden', 'true');
    }, 2600);
  }

  window.dialogManager = {
    init: init,
    show: show,
    confirm: confirm,
    alert: alert,
    toast: toast,
    close: close
  };
})();
