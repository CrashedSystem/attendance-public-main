/* ================================================================
   core/utils.js — 공용 유틸리티 함수
   (이스케이프, 날짜/생일 포맷팅, 요일, 최근 수요일)
   ================================================================ */
(function () {
  'use strict';

  /**
   * HTML 이스케이프 — 사용자 입력 문자열을 안전하게 변환.
   * @param {string} s - 원본 문자열
   * @returns {string} 이스케이프된 문자열
   */
  function esc(s) {
    var d = document.createElement('div');
    d.textContent = s;
    return d.innerHTML;
  }

  /**
   * 속성값 이스케이프 — 큰따옴표까지 이스케이프.
   * @param {string} s - 원본 문자열
   * @returns {string} 이스케이프된 문자열
   */
  function escAttr(s) {
    return esc(s).replace(/"/g, '&quot;');
  }

  /**
   * 생일 포맷팅 — 다양한 입력(YYYY-MM-DD, MMDD, M월D일)을 'M월 D일'로 통일.
   * @param {*} b - 생일 값
   * @returns {string} 포맷된 생일 문자열
   */
  function fmtBirthday(b) {
    if (!b) return '';
    var s = String(b).trim();
    var m = s.match(/^(\d{4})-(\d{1,2})-(\d{1,2})/);
    if (m) return parseInt(m[2], 10) + '월 ' + parseInt(m[3], 10) + '일';
    m = s.match(/^(\d{2})(\d{2})$/);
    if (m && parseInt(m[1], 10) >= 1 && parseInt(m[1], 10) <= 12 && parseInt(m[2], 10) >= 1 && parseInt(m[2], 10) <= 31)
      return parseInt(m[1], 10) + '월 ' + parseInt(m[2], 10) + '일';
    m = s.match(/(\d{1,2})\s*월\s*(\d{1,2})\s*일?/);
    if (m) return parseInt(m[1], 10) + '월 ' + parseInt(m[2], 10) + '일';
    return s;
  }

  /**
   * 생일 표시용 포맷 — 명단에서 괄호 형태로 표기.
   * YYYYMMDD는 '(M월 D일)', 그 외는 fmtBirthday 결과.
   * @param {*} b - 생일 값
   * @returns {string} 포맷된 생일 문자열
   */
  function fmtBirthdayDisplay(b) {
    if (!b) return '';
    var s = String(b).trim();
    var m = s.match(/^(\d{4})(\d{2})(\d{2})$/);
    if (m) return '(' + parseInt(m[2], 10) + '월 ' + parseInt(m[3], 10) + '일)';
    return fmtBirthday(s);
  }

  /**
   * 날짜 단축 표시 — 'YYYY-MM-DD'를 'MM/DD'로 변환.
   * @param {string} s - ISO 날짜 문자열
   * @returns {string} MM/DD 형식
   */
  function fmtShortDate(s) {
    if (!s) return '-';
    var m2 = s.split('-');
    if (m2.length !== 3) return s;
    return m2[1] + '/' + m2[2];
  }

  /**
   * 오늘 날짜를 'YYYY년 M월 D일 (요일)' 형태로 표기.
   * @returns {string} 한글 장문 날짜
   */
  function fmtToday() {
    var d = new Date();
    var days = ['일', '월', '화', '수', '목', '금', '토'];
    return d.getFullYear() + '년 ' + (d.getMonth() + 1) + '월 ' + d.getDate() + '일 (' + days[d.getDay()] + ')';
  }

  /**
   * 오늘 날짜를 ISO 형식(YYYY-MM-DD)으로 반환.
   * @returns {string} ISO 날짜
   */
  function todayISODate() {
    var d = new Date();
    return d.getFullYear() + '-' + String(d.getMonth() + 1).padStart(2, '0') + '-' + String(d.getDate()).padStart(2, '0');
  }

  /**
   * 날짜 문자열의 요일 라벨 반환 ('일'~'토').
   * @param {string} dateStr - ISO 날짜 문자열
   * @returns {string} 요일 한 글자
   */
  function weekdayLabel(dateStr) {
    if (!dateStr) return '';
    var d = new Date(dateStr + 'T00:00:00');
    var days = ['일', '월', '화', '수', '목', '금', '토'];
    return days[d.getDay()];
  }

  /**
   * 가장 최근에 지나간 수요일의 ISO 날짜 반환.
   * @returns {string} 최근 수요일(YYYY-MM-DD)
   */
  function mostRecentWed() {
    var d = new Date();
    var off = (d.getDay() - 3 + 7) % 7;
    d.setDate(d.getDate() - off);
    var m = String(d.getMonth() + 1).padStart(2, '0');
    var day = String(d.getDate()).padStart(2, '0');
    return d.getFullYear() + '-' + m + '-' + day;
  }

  window.utils = {
    esc: esc,
    escAttr: escAttr,
    fmtBirthday: fmtBirthday,
    fmtBirthdayDisplay: fmtBirthdayDisplay,
    fmtShortDate: fmtShortDate,
    fmtToday: fmtToday,
    todayISODate: todayISODate,
    weekdayLabel: weekdayLabel,
    mostRecentWed: mostRecentWed
  };
})();
