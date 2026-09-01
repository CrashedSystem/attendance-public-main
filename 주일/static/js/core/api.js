/* ================================================================
   core/api.js — 서버 API 호출 통합 레이어
   모든 fetch 호출은 이 모듈을 통해 수행한다.
   ================================================================ */
(function () {
  'use strict';

  /**
   * 로그인 후 저장된 관리자 PIN 반환. 없으면 ''.
   * @returns {string}
   */
  function currentPin() {
    if (window.authManager && typeof window.authManager.getPin === 'function') {
      return window.authManager.getPin() || '';
    }
    return '';
  }

  /**
   * 공용 fetch 래퍼 — JSON 응답을 파싱해 반환.
   * 로그인한 관리자 PIN이 저장되어 있으면 모든 요청에 X-Admin-Pin 헤더를 자동 포함한다.
   * @param {string} path - API 경로
   * @param {Object} [opts] - fetch 옵션 (method, body, headers 등)
   * @returns {Promise<Object>} 파싱된 JSON
   */
  function request(path, opts) {
    opts = opts || {};
    var headers = { 'Content-Type': 'application/json' };
    var pin = currentPin();
    if (pin) headers['X-Admin-Pin'] = pin;
    var init = {
      method: opts.method || 'GET',
      headers: headers
    };
    if (opts.body !== undefined) init.body = JSON.stringify(opts.body);
    return fetch(path, init).then(function (r) { return r.json(); });
  }

  /**
   * HTML 응답(보고서 등)을 관리자 PIN 헤더와 함께 가져와 문자열로 반환.
   * @param {string} path - HTML 경로
   * @returns {Promise<string>}
   */
  function getReport(path) {
    var pin = currentPin();
    var headers = pin ? { 'X-Admin-Pin': pin } : {};
    return fetch(path, { method: 'GET', headers: headers }).then(function (r) {
      if (r.status === 401) throw new Error('관리자 인증이 필요합니다.');
      return r.text();
    });
  }

  /* ---------- 공개(메인) ---------- */

  /** 서버 모드 조회 (sunday/wednesday, env) */
  function getMode() { return request('/api/mode'); }

  /** 사용자 검색 */
  function searchUsers(q, mode) {
    var url = '/api/users/search?q=' + encodeURIComponent(q);
    if (mode) url += '&mode=' + encodeURIComponent(mode);
    return request(url);
  }

  /** 출석 체크인 */
  function checkin(userId) {
    return request('/api/checkin', { method: 'POST', body: { user_id: userId } });
  }

  /* ---------- 관리자 : 인증/모드 ---------- */

  /** PIN 로그인 */
  function adminLogin(pin) {
    return request('/api/admin/login', { method: 'POST', body: { pin: pin } });
  }

  /** 일요일/수요일 모드 변경 */
  function setMode(mode) {
    return request('/api/admin/mode', { method: 'POST', body: { mode: mode } });
  }

  /* ---------- 관리자 : 명단(사용자) ---------- */

  /** 사용자 전체 목록 조회 */
  function getUsers() { return request('/api/admin/users'); }

  /** 사용자 신규/수정 저장 (id 없으면 POST, 있으면 PUT) */
  function saveUser(payload, id) {
    var url = '/api/admin/users' + (id ? '/' + id : '');
    var method = id ? 'PUT' : 'POST';
    return request(url, { method: method, body: payload });
  }

  /** 사용자 삭제 */
  function deleteUser(id) {
    return request('/api/admin/users/' + id, { method: 'DELETE' });
  }

  /** 팀/소속 메타데이터 및 매핑 조회 */
  function getTeamsAffiliations() { return request('/api/admin/teams-affiliations'); }

  /* ---------- 관리자 : 출석 ---------- */

  /** 오늘 출석 현황 */
  function getAttendanceToday() { return request('/api/attendance/today'); }

  /** 출석 취소 */
  function deleteAttendance(id) { return request('/api/attendance/' + id, { method: 'DELETE' }); }

  /** 일괄 출석 */
  function bulkAttend(names, choices) {
    return request('/api/attendance/bulk', { method: 'POST', body: { names: names, choices: choices } });
  }

  /* ---------- 관리자 : 수요 결석 ---------- */

  /** 결석자 목록 조회 */
  function getAbsences(date) {
    return request('/api/admin/absences?date=' + encodeURIComponent(date));
  }

  /** 결석 사유 저장 */
  function saveAbsence(userId, date, reason) {
    return request('/api/admin/absences', { method: 'POST', body: { user_id: userId, date: date, reason: reason } });
  }

  /** 결석 사유 삭제 */
  function deleteAbsence(id) {
    return request('/api/admin/absences/' + id, { method: 'DELETE' });
  }

  /* ---------- 관리자 : 팀/소속 ---------- */

  /** 소속 일괄 이동 */
  function teamsBulkMove(affiliation, team) {
    return request('/api/admin/teams/bulk-move', { method: 'POST', body: { affiliation: affiliation, team: team } });
  }

  /** 소속 이름 변경 */
  function affRename(oldName, newName) {
    return request('/api/admin/affiliations/rename', { method: 'POST', body: { old_name: oldName, new_name: newName } });
  }

  /** 임시 소속 추가 */
  function affCreate(name) {
    return request('/api/admin/affiliations/create', { method: 'POST', body: { name: name } });
  }

  /** 팀 이름 변경 */
  function teamRename(oldName, newName) {
    return request('/api/admin/teams/rename', { method: 'POST', body: { old_name: oldName, new_name: newName } });
  }

  /** 새 팀 생성 */
  function teamCreate(name) {
    return request('/api/admin/teams/create', { method: 'POST', body: { name: name } });
  }

  /** 팀 삭제 */
  function teamDelete(name) {
    return request('/api/admin/teams/delete', { method: 'POST', body: { name: name } });
  }

  /** 새신우 유지 기간 조회 */
  function getNewbieDays() { return request('/api/admin/newbie-days'); }

  /** 새신우 유지 기간 설정 */
  function setNewbieDays(days) {
    return request('/api/admin/newbie-days', { method: 'POST', body: { days: days } });
  }

  /** 일요일 상세 명단 표시 기준(명) 조회 */
  function getSundayDetailThreshold() { return request('/api/admin/sunday-detail-threshold'); }

  /** 일요일 상세 명단 표시 기준(명) 설정 */
  function setSundayDetailThreshold(threshold) {
    return request('/api/admin/sunday-detail-threshold', { method: 'POST', body: { threshold: threshold } });
  }

  /* ---------- 관리자 : 기록/통계 ---------- */

  /** 지정 날짜 출석 기록 목록 */
  function attendanceList(date) {
    return request('/api/admin/attendance/list?date=' + encodeURIComponent(date));
  }

  /** 임의 출석 추가 */
  function addHistAttendance(body) {
    return request('/api/admin/attendance', { method: 'POST', body: body });
  }

  /** 임의 출석 기록 삭제 */
  function deleteHistAttendance(id) {
    return request('/api/admin/attendance/' + id, { method: 'DELETE' });
  }

  /* ---------- 관리자 : 시간 ---------- */

  /** 현재 시간 확인 */
  function getTime() { return request('/api/admin/time'); }

  /** 인터넷 시간 동기화 */
  function syncTime() { return request('/api/admin/sync-time', { method: 'POST' }); }

  /* ---------- 관리자 : 보고서/종료 ---------- */

  /** 종합 보고서 */
  function report() { return request('/api/report'); }

  /** 팀별 보고서 내보내기 */
  function exportTeams() { return request('/api/admin/export-teams', { method: 'POST' }); }

  /** 서버 종료 + 보고서 저장 */
  function shutdown() { return request('/api/admin/shutdown', { method: 'POST' }); }

  window.api = {
    request: request,
    getReport: getReport,
    getMode: getMode,
    searchUsers: searchUsers,
    checkin: checkin,
    adminLogin: adminLogin,
    setMode: setMode,
    getUsers: getUsers,
    saveUser: saveUser,
    deleteUser: deleteUser,
    getTeamsAffiliations: getTeamsAffiliations,
    getAttendanceToday: getAttendanceToday,
    deleteAttendance: deleteAttendance,
    bulkAttend: bulkAttend,
    getAbsences: getAbsences,
    saveAbsence: saveAbsence,
    deleteAbsence: deleteAbsence,
    teamsBulkMove: teamsBulkMove,
    affRename: affRename,
    affCreate: affCreate,
    teamRename: teamRename,
    teamCreate: teamCreate,
    teamDelete: teamDelete,
    getNewbieDays: getNewbieDays,
    setNewbieDays: setNewbieDays,
    getSundayDetailThreshold: getSundayDetailThreshold,
    setSundayDetailThreshold: setSundayDetailThreshold,
    attendanceList: attendanceList,
    addHistAttendance: addHistAttendance,
    deleteHistAttendance: deleteHistAttendance,
    getTime: getTime,
    syncTime: syncTime,
    report: report,
    exportTeams: exportTeams,
    shutdown: shutdown
  };
})();
