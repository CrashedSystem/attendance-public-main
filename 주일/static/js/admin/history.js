/* ================================================================
   admin/history.js — 기록·통계·시간 탭
   (출석 기록 조회, 임의 출석 추가, 시간 확인/동기화)
   ================================================================ */
(function () {
  'use strict';

  var histAmbiguous = null;

  /** 기록 탭 로드 시 초기화 — 오늘 날짜/현재 시각 기본값 설정. */
  function loadTab() {
    histAmbiguous = null;
    window.$('h-resolve').innerHTML = '';
    window.$('h-add-hint').textContent = '';
    if (!window.$('h-date').value) window.$('h-date').value = window.utils.todayISODate();
    loadList();
    if (!window.$('h-time').value) window.$('h-time').value = new Date().toTimeString().slice(0, 5);
  }

  /** 지정 날짜의 출석 기록 조회 및 렌더링. */
  function loadList() {
    var date = window.$('h-date').value;
    window.api.attendanceList(date)
      .then(function (rows) {
        var html = '<table><tr><th>No</th><th>이름</th><th>소속</th><th>팀</th><th>출석 시각</th><th></th></tr>';
        if (!rows.length) html += '<tr><td colspan="6" style="text-align:center;color:#888">해당 날짜의 출석 기록이 없습니다.</td></tr>';
        rows.forEach(function (r) {
          html += '<tr><td>' + r.id + '</td><td>' + window.utils.esc(r.name) + '</td><td>' + window.utils.esc(r.affiliation || '') + '</td>' +
            '<td>' + window.utils.esc(r.team || '') + '</td><td>' + window.utils.esc(r.check_time) + '</td>' +
            '<td class="row-actions"><button class="mini-btn del" data-del="' + r.id + '" data-name="' + window.utils.esc(r.name) + '">삭제</button></td></tr>';
        });
        html += '</table>';
        var wrap = window.$('h-list');
        wrap.innerHTML = html;
        wrap.querySelectorAll('[data-del]').forEach(function (b) {
          b.addEventListener('click', function () {
            var id = parseInt(b.dataset.del, 10);
            var nm = b.dataset.name;
            window.dialogManager.confirm(nm + '님의 이 출석 기록을 삭제하시겠습니까?', { title: '기록 삭제', okLabel: '삭제', destructive: true }, function () {
              window.api.deleteHistAttendance(id)
                .then(function (res) {
                  if (res.ok) { window.dialogManager.toast(nm + '님의 기록을 삭제했습니다.'); loadList(); }
                  else window.dialogManager.alert(res.msg || '삭제 실패', { title: '기록 삭제 실패' });
                });
            });
          });
        });
      });
  }

  /**
   * 임의 출석 추가 요청.
   * @param {Object} body - {name|user_id, date, time}
   * @returns {Promise<Object>} 서버 응답
   */
  function addHistAttendance(body) {
    return window.api.addHistAttendance(body);
  }

  /**
   * 동명이인 해결 UI 렌더링.
   * @param {Object} res - need_resolution 응답
   */
  function renderHistResolve(res) {
    var box = window.$('h-resolve');
    box.innerHTML = '<p class="bulk-warn">동명이인이 있어 올바른 사람을 선택해 주세요.</p>';
    var wrap = document.createElement('div');
    wrap.className = 'bulk-resolve-list';
    res.ambiguous.forEach(function (c) {
      var label = document.createElement('div');
      label.className = 'bulk-resolve-name';
      label.textContent = c.name;
      var sel = document.createElement('select');
      sel.className = 'bulk-resolve-select';
      var opt0 = document.createElement('option');
      opt0.value = ''; opt0.textContent = '선택하세요';
      sel.appendChild(opt0);
      res.ambiguous.forEach(function (c2) {
        var o = document.createElement('option');
        o.value = c2.id;
        o.textContent = (c2.affiliation || '-') + ' · ' + (c2.team || '-') +
          (c2.birthday ? ' · 생일 ' + window.utils.fmtBirthday(c2.birthday) : '');
        sel.appendChild(o);
      });
      wrap.appendChild(label);
      wrap.appendChild(sel);
    });
    box.appendChild(wrap);
    var btn = document.createElement('button');
    btn.className = 'btn btn-primary';
    btn.textContent = '확정 추가';
    btn.addEventListener('click', function () {
      var sels = wrap.querySelectorAll('select.bulk-resolve-select');
      if (sels.length !== 1 || !sels[0].value) { window.dialogManager.alert('동명이인 중 올바른 사람을 선택하세요.', { title: '출석 추가' }); return; }
      var date = window.$('h-date').value;
      var time = window.$('h-time').value || '';
      addHistAttendance({ user_id: parseInt(sels[0].value, 10), date: date, time: time })
        .then(function (resp) {
          if (resp.ok) {
            window.dialogManager.toast(resp.name + '님 출석 추가 완료 (' + date + ' ' + time + ')');
          } else if (resp.need_resolution) {
            renderHistResolve(resp); return;
          } else {
            window.dialogManager.alert(resp.msg || '추가 실패', { title: '출석 추가 실패' }); return;
          }
          window.$('h-resolve').innerHTML = '';
          window.$('h-name').value = '';
          loadList();
        });
    });
    box.appendChild(btn);
  }

  /** 임의 출석 추가 실행 (이름 입력 경로). */
  function onAdd() {
    var date = window.$('h-date').value;
    var time = window.$('h-time').value || '';
    var name = window.$('h-name').value.trim();
    if (!name) { window.dialogManager.alert('추가할 이름을 입력하세요.', { title: '출석 추가' }); return; }
    if (!time) { window.dialogManager.alert('시각을 선택하세요.', { title: '출석 추가' }); return; }
    if (!date) { window.dialogManager.alert('날짜를 선택하세요.', { title: '출석 추가' }); return; }
    window.$('h-resolve').innerHTML = '';
    window.$('h-add-hint').textContent = '';
    addHistAttendance({ name: name, date: date, time: time })
      .then(function (res) {
        if (res.ok && !res.need_resolution) {
          window.dialogManager.toast(res.name + '님 출석 추가 완료 (' + date + ' ' + time + ')');
          window.$('h-name').value = '';
          loadList();
        } else if (res.need_resolution) {
          histAmbiguous = res.ambiguous;
          renderHistResolve(res);
        } else {
          window.dialogManager.alert(res.msg || '추가 실패', { title: '출석 추가 실패' });
        }
      });
  }

  /** 보고서 생성 (이 날짜 기준). */
  function onReport() {
    var date = window.$('h-date').value || window.utils.todayISODate();
    var wd = window.utils.weekdayLabel(date);
    var label = (wd === '일') ? '일요일' : (wd === '수') ? '수요일' : '기타(' + wd + '요일)';
    window.dialogManager.confirm(date + ' (' + label + ') 기준 보고서를 생성하시겠습니까?', { title: '보고서 생성', okLabel: '생성' }, function () {
      window.api.getReport('/api/admin/report?date=' + encodeURIComponent(date))
        .then(function (html) {
          var blob = new Blob([html], { type: 'text/html;charset=utf-8' });
          var url = URL.createObjectURL(blob);
          window.open(url, '_blank');
          setTimeout(function () { URL.revokeObjectURL(url); }, 60000);
        })
        .catch(function (e) {
          window.dialogManager.alert(
            (e && e.message) || '보고서를 불러올 수 없습니다.',
            { title: '보고서 생성' });
        });
    });
  }

  /** 현재 시간 확인. */
  function onTimeCheck() {
    window.api.getTime()
      .then(function (res) {
        var t = res.internet_utc ? '인터넷(UTC): ' + res.internet_utc : '인터넷 시간을 가져올 수 없습니다';
        window.$('h-time-hint').textContent = '컴퓨터(로컬): ' + res.system_local + '  |  ' + t;
      });
  }

  /** 인터넷 시간 동기화. */
  function onTimeSync() {
    window.dialogManager.confirm('컴퓨터의 시스템 시간을 인터넷 시간으로 동기화합니다.\n(관리자 권한 필요) 계속할까요?', { title: '시간 동기화', okLabel: '동기화' }, function () {
      window.$('h-time-hint').textContent = '동기화 중...';
      window.api.syncTime()
        .then(function (res) {
          if (res.ok) window.$('h-time-hint').textContent = '동기화 완료. 설정된 UTC: ' + res.set_utc + ' | 현재 로컬: ' + res.local_now;
          else window.$('h-time-hint').textContent = res.msg || '동기화 실패';
        });
    });
  }

  /**
   * 모듈 초기화 — 기록/시간 버튼 이벤트 등록.
   */
  function init() {
    window.$('btn-h-load').addEventListener('click', loadList);
    window.$('btn-h-add').addEventListener('click', onAdd);
    window.$('btn-h-report').addEventListener('click', onReport);
    window.$('btn-time-check').addEventListener('click', onTimeCheck);
    window.$('btn-time-sync').addEventListener('click', onTimeSync);
  }

  window.historyManager = {
    init: init,
    loadTab: loadTab,
    loadList: loadList
  };
})();
