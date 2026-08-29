/* ================================================================
   ui/picker.js — 애플식 하단 시트 피커 + 인라인 달력
   - 모든 <select>를 하단 시트로 교체 (기존 change 이벤트 유지)
   - 모든 <input type="date">를 커스텀 인라인 달력으로 대체
   ================================================================ */
(function () {
  'use strict';

  var calState = { focus: null };

  /* ==================== 하단 시트 피커 ==================== */

  /** 하단 시트 레이어 DOM 생성/재사용. */
  function sheetEl() {
    var el = document.getElementById('ios-picker');
    if (!el) {
      el = document.createElement('div');
      el.id = 'ios-picker';
      el.className = 'ios-picker';
      el.setAttribute('aria-hidden', 'true');
      el.innerHTML =
        '<div class="list-backdrop" data-close></div>' +
        '<div class="list-sheet" role="dialog" aria-modal="true">' +
        '<div class="list-grabber"></div>' +
        '<div class="list-title"></div>' +
        '<div class="list-options" role="listbox"></div>' +
        '</div>';
      document.body.appendChild(el);
    }
    return el;
  }

  /** 하단 시트 닫기 + 원본 select로 포커스 복원. */
  function closeSheet() {
    var el = document.getElementById('ios-picker');
    if (!el) return;
    el.classList.remove('open');
    el.setAttribute('aria-hidden', 'true');
    var owner = el._owner;
    el._owner = null;
    if (owner && owner.focus) { try { owner.focus(); } catch (e) {} }
  }

  /** 시트 열기 (옵션 목록 렌더링). */
  function openSimpleSheet(title, items, onPick) {
    var sheet = sheetEl();
    sheet.querySelector('.list-title').textContent = title;
    var opts = sheet.querySelector('.list-options');
    opts.innerHTML = '';
    items.forEach(function (it) {
      var b = document.createElement('button');
      b.type = 'button';
      b.className = 'list-row' + (it.selected ? ' selected' : '');
      b.setAttribute('role', 'option');
      b.setAttribute('aria-selected', it.selected ? 'true' : 'false');
      b.innerHTML = '<span class="list-row-label">' + window.utils.esc(it.label) + '</span>';
      if (it.selected) b.innerHTML += '<span class="list-check"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"><path d="M5 12l5 5 9-10"/></svg></span>';
      b.addEventListener('click', function () { onPick(it); });
      opts.appendChild(b);
    });
    sheet.classList.add('open');
    sheet.setAttribute('aria-hidden', 'false');
    var first = opts.querySelector('button');
    if (first) { try { first.focus(); } catch (e) {} }
  }

  /**
   * select의 옵션을 배열로 추출.
   * @param {HTMLSelectElement} sel - 대상 select
   * @returns {Array<{value:string,label:string,selected:boolean}>}
   */
  function optionList(sel) {
    var out = [];
    for (var i = 0; i < sel.options.length; i++) {
      var o = sel.options[i];
      out.push({ value: o.value, label: o.textContent, selected: o.selected });
    }
    return out;
  }

  /**
   * select 클릭 시 하단 시트 피커 열기.
   * 선택 시 select.value 설정 + change/input 이벤트 발화.
   * @param {HTMLSelectElement} sel - 대상 select
   */
  function openSelectSheet(sel) {
    var items = optionList(sel);
    sheetEl()._owner = sel;
    openSimpleSheet('선택', items, function (it) {
      sel.value = it.value;
      sel.dispatchEvent(new Event('change', { bubbles: true }));
      sel.dispatchEvent(new Event('input', { bubbles: true }));
      closeSheet();
    });
  }

  /* ==================== 인라인 달력 ==================== */

  /**
   * 오늘 날짜 ISO 문자열.
   * @returns {string} YYYY-MM-DD
   */
  function todayISO() {
    var d = new Date();
    return d.getFullYear() + '-' + String(d.getMonth() + 1).padStart(2, '0') + '-' + String(d.getDate()).padStart(2, '0');
  }

  /**
   * ISO 문자열 -> Date 객체.
   * @param {string} s - YYYY-MM-DD
   * @returns {Date|null}
   */
  function parseISO(s) {
    if (!s) return null;
    var m = /^(\d{4})-(\d{1,2})-(\d{1,2})$/.exec(s);
    if (!m) return null;
    return new Date(Number(m[1]), Number(m[2]) - 1, Number(m[3]));
  }

  /**
   * Date -> ISO 문자열.
   * @param {Date} d - 날짜
   * @returns {string} YYYY-MM-DD
   */
  function fmtISO(d) {
    return d.getFullYear() + '-' + String(d.getMonth() + 1).padStart(2, '0') + '-' + String(d.getDate()).padStart(2, '0');
  }

  /** 인라인 달력 레이어 DOM 생성/재사용. */
  function calendarEl() {
    var el = document.getElementById('ios-calendar');
    if (!el) {
      el = document.createElement('div');
      el.id = 'ios-calendar';
      el.className = 'ios-calendar';
      el.setAttribute('aria-hidden', 'true');
      el.innerHTML =
        '<div class="cal-card" role="dialog" aria-modal="true">' +
        '<div class="cal-head">' +
        '<button type="button" class="cal-nav" data-cal-nav="prev"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round"><path d="M15 6l-6 6 6 6"/></svg></button>' +
        '<div class="cal-title"></div>' +
        '<button type="button" class="cal-nav" data-cal-nav="next"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round"><path d="M9 6l6 6-6 6"/></svg></button>' +
        '</div>' +
        '<div class="cal-week"><span>일</span><span>월</span><span>화</span><span>수</span><span>목</span><span>금</span><span>토</span></div>' +
        '<div class="cal-grid"></div>' +
        '<div class="cal-foot"><button type="button" class="cal-clear">지우기</button><button type="button" class="cal-close">완료</button></div>' +
        '</div>';
      document.body.appendChild(el);
      el.addEventListener('click', onCalendarClick);
      document.addEventListener('mousedown', onCalendarOutside);
      document.addEventListener('keydown', onCalendarKey);
    }
    return el;
  }

  /** 달력 내부 클릭 처리 (월 이동, 날짜 선택, 지우기, 완료). */
  function onCalendarClick(e) {
    var nav = e.target.closest && e.target.closest('[data-cal-nav]');
    if (nav) {
      var dir = nav.getAttribute('data-cal-nav') === 'prev' ? -1 : 1;
      calState.monthView = new Date(calState.monthView.getFullYear(), calState.monthView.getMonth() + dir, 1);
      renderCalendar();
      return;
    }
    var day = e.target.closest && e.target.closest('.cal-day');
    if (day && !day.classList.contains('empty')) {
      calState.value = fmtISO(new Date(calState.monthView.getFullYear(), calState.monthView.getMonth(), Number(day.getAttribute('data-day'))));
      renderCalendar();
      return;
    }
    if (e.target.closest && e.target.closest('.cal-clear')) {
      calState.value = '';
      if (calState.focus) calState.focus.value = '';
      calState.focus.dispatchEvent(new Event('input', { bubbles: true }));
      calState.focus.dispatchEvent(new Event('change', { bubbles: true }));
      renderCalendar();
      return;
    }
    if (e.target.closest && e.target.closest('.cal-close')) {
      commitCalendar();
      return;
    }
  }

  /** 달력 바깥 클릭 시 확정(commit). */
  function onCalendarOutside(e) {
    var cal = document.getElementById('ios-calendar');
    if (!cal || !cal.classList.contains('open')) return;
    if (e.target.closest && e.target.closest('.ios-calendar')) return;
    if (e.target.classList && e.target.classList.contains('cal-field')) return;
    commitCalendar();
  }

  /** Escape 키로 달력 닫기. */
  function onCalendarKey(e) {
    if (e.key === 'Escape') {
      var c = document.getElementById('ios-calendar');
      if (c && c.classList.contains('open')) commitCalendar();
    }
  }

  /** 달력 그리드 렌더링. */
  function renderCalendar() {
    var cal = calendarEl();
    var y = calState.monthView.getFullYear();
    var mo = calState.monthView.getMonth();
    var first = new Date(y, mo, 1);
    var daysIn = new Date(y, mo + 1, 0).getDate();
    var lead = first.getDay();
    var grid = cal.querySelector('.cal-grid');
    grid.innerHTML = '';
    for (var i = 0; i < lead; i++) {
      var e0 = document.createElement('div');
      e0.className = 'cal-day empty';
      grid.appendChild(e0);
    }
    for (var d = 1; d <= daysIn; d++) {
      var iso = fmtISO(new Date(y, mo, d));
      var cell = document.createElement('button');
      cell.type = 'button';
      cell.className = 'cal-day';
      cell.setAttribute('data-day', String(d));
      cell.textContent = String(d);
      if (iso === todayISO()) cell.classList.add('today');
      if (iso === calState.value) cell.classList.add('selected');
      grid.appendChild(cell);
    }
    cal.querySelector('.cal-title').textContent = y + '년 ' + (mo + 1) + '월';
  }

  /**
   * 달력 열기 — 입력 필드 근처에 팝오버로 표시.
   * @param {HTMLInputElement} input - 대상 날짜 입력
   */
  function openCalendar(input) {
    calendarEl();
    calState.focus = input;
    var cur = input.value ? parseISO(input.value) : new Date();
    calState.value = input.value || '';
    calState.monthView = new Date(cur.getFullYear(), cur.getMonth(), 1);
    renderCalendar();
    var cal = document.getElementById('ios-calendar');
    cal.classList.add('open');
    cal.setAttribute('aria-hidden', 'false');
    var pos = input.getBoundingClientRect();
    var card = cal.querySelector('.cal-card');
    card.style.left = '';
    card.style.top = '';
    var cw = card.offsetWidth || 320;
    var ch = card.offsetHeight || 360;
    var left = Math.min(Math.max(12, pos.left - cw + pos.width), window.innerWidth - cw - 12);
    var top = pos.bottom + 10;
    if (top + ch > window.innerHeight - 12) top = Math.max(12, pos.top - ch - 10);
    card.style.left = left + 'px';
    card.style.top = top + 'px';
  }

  /** 달력 닫기 + 선택값을 입력 필드에 반영하고 change/input 발화. */
  function commitCalendar() {
    var cal = document.getElementById('ios-calendar');
    if (!cal) return;
    cal.classList.remove('open');
    cal.setAttribute('aria-hidden', 'true');
    if (!calState.focus) return;
    var input = calState.focus;
    calState.focus = null;
    var finalVal = calState.value || '';
    if (input.value !== finalVal) {
      input.value = finalVal;
      input.dispatchEvent(new Event('input', { bubbles: true }));
      input.dispatchEvent(new Event('change', { bubbles: true }));
    }
    try { input.focus(); } catch (e) {}
  }

  /**
   * date 입력 -> 읽기 전용 text(.cal-field)로 변환.
   * 네이티브 date picker가 뜨지 않게 막는다.
   * @param {HTMLInputElement} input - date 입력
   */
  function convertDateInput(input) {
    var type = (input.getAttribute('type') || '').toLowerCase();
    if (type !== 'date') return;
    if (input.getAttribute('data-cal') === '1') return;
    input.setAttribute('data-cal', '1');
    input.setAttribute('type', 'text');
    input.setAttribute('readonly', 'readonly');
    input.setAttribute('inputmode', 'none');
    input.classList.add('cal-field');
  }

  /** 기존 date 입력 변환 + 동적 추가 감지(MutationObserver). */
  function initCalendarInputs() {
    document.querySelectorAll('input[type="date"]').forEach(convertDateInput);
    if (window.MutationObserver) {
      var obs = new MutationObserver(function (muts) {
        muts.forEach(function (m) {
          m.addedNodes && m.addedNodes.forEach(function (n) {
            if (n.nodeType !== 1) return;
            if (n.matches && n.matches('input[type="date"]')) convertDateInput(n);
            n.querySelectorAll && n.querySelectorAll('input[type="date"]').forEach(convertDateInput);
          });
        });
      });
      obs.observe(document.body, { childList: true, subtree: true });
    }
  }

  /* ---------- 전역 위임 이벤트 등록 (IIFE 내 1회) ---------- */

  // 시트 백드롭 클릭 시 닫기
  document.addEventListener('mousedown', function (e) {
    if (e.target.closest && e.target.closest('.list-backdrop')) {
      e.preventDefault();
      closeSheet();
    }
  });

  // Escape로 시트 닫기
  document.addEventListener('keydown', function (e) {
    if (e.key === 'Escape') closeSheet();
  });

  // select 클릭 시 (capture) 하단 시트 열기 — 네이티브 드롭다운 방지
  document.addEventListener('mousedown', function (e) {
    var t = e.target;
    if (!t || t.tagName !== 'SELECT') return;
    if (sheetEl().classList.contains('open')) return;
    var label = '선택';
    var wrap = t.closest && t.closest('label');
    if (wrap && wrap.firstChild) {
      var lbl = (wrap.firstChild.textContent || '').trim();
      if (lbl) label = lbl;
    }
    e.preventDefault();
    openSelectSheet(t);
  }, true);

  // .cal-field(date) 클릭 시 (capture) 커스텀 달력 열기
  document.addEventListener('mousedown', function (e) {
    var t = e.target;
    if (!t || t.tagName !== 'INPUT') return;
    if (!t.classList || !t.classList.contains('cal-field')) return;
    if (t.disabled) return;
    var pickerOpen = document.getElementById('ios-picker') && document.getElementById('ios-picker').classList.contains('open');
    if (pickerOpen) return;
    if (calState.focus) commitCalendar();
    e.preventDefault();
    openCalendar(t);
  }, true);

  window.picker = {
    init: initCalendarInputs
  };
})();
