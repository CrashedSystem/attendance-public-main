/* ================================================================
   admin/attendance.js — 오늘 출석 현황 관리
   ================================================================ */
(function () {
  'use strict';

  /** 오늘 출석 현황 로드 및 테이블 렌더링. */
  function load() {
    window.api.getAttendanceToday()
      .then(function (rows) {
        window.$('attend-summary').textContent = '오늘 출석 ' + rows.length + '명';
        var html = '<tr><th>No</th><th>이름</th><th>소속</th><th>출석 시각</th><th></th></tr>';
        rows.forEach(function (r) {
          html += '<tr><td>' + r.user_id + '</td><td>' + window.utils.esc(r.name) + '</td><td>' + window.utils.esc(r.affiliation || '') + '</td>' +
            '<td>' + window.utils.esc(r.check_time) + '</td>' +
            '<td class="row-actions"><button class="mini-btn del" data-cancel="' + r.id + '" data-name="' + window.utils.esc(r.name) + '">취소</button></td></tr>';
        });
        var table = window.$('attend-table');
        table.innerHTML = html;
        table.querySelectorAll('[data-cancel]').forEach(function (b) {
          b.addEventListener('click', function () {
            var id = parseInt(b.dataset.cancel, 10);
            var nm = b.dataset.name;
            window.dialogManager.confirm(nm + '님의 출석 기록을 취소하시겠습니까?', { title: '출석 취소', okLabel: '취소', destructive: true }, function () {
              window.api.deleteAttendance(id)
                .then(function (res) {
                  if (res.ok) { window.dialogManager.toast(nm + '님의 출석이 취소되었습니다.'); load(); }
                  else window.dialogManager.alert(res.msg || '취소 실패', { title: '출석 취소 실패' });
                });
            });
          });
        });
      });
  }

  window.attendanceManager = {
    load: load
  };
})();
