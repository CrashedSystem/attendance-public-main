/* ================================================================
   admin/import.js — 데이터 가져오기 탭
   (과거 엑셀/CSV 신우 명단·출석 기록을 DB로 변환)
   ================================================================ */
(function () {
  'use strict';

  var token = null;
  var summary = null;

  /** multipart 업로드 (파일) */
  function upload(path, file) {
    var pin = window.authManager.getPin() || '';
    var fd = new FormData();
    fd.append('file', file);
    var headers = pin ? { 'X-Admin-Pin': pin } : {};
    return fetch(path, { method: 'POST', headers: headers, body: fd }).then(function (r) {
      return r.json();
    });
  }

  /** 템플릿 .xlsx 다운로드 */
  function onTemplate() {
    var pin = window.authManager.getPin() || '';
    var headers = pin ? { 'X-Admin-Pin': pin } : {};
    fetch('/api/admin/import/template', { method: 'GET', headers: headers })
      .then(function (r) {
        if (!r.ok) throw new Error('HTTP ' + r.status);
        return r.blob();
      })
      .then(function (blob) {
        var url = URL.createObjectURL(blob);
        var a = document.createElement('a');
        a.href = url;
        a.download = '신우_임포트_템플릿.xlsx';
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        URL.revokeObjectURL(url);
        window.dialogManager.toast('템플릿 다운로드 완료');
      })
      .catch(function () {
        window.dialogManager.alert('템플릿을 받지 못했습니다. 관리자 로그인 상태를 확인하세요.', { title: '템플릿 다운로드' });
      });
  }

  /** 미리보기 요약 렌더링. */
  function renderPreview(res) {
    var box = window.$('imp-preview');
    box.innerHTML = '';
    box.hidden = false;
    box.classList.add('imp-preview');
    var s = res.summary;
    var w = document.createElement('div');
    w.className = 'team-admin-row';
    w.style.flexWrap = 'wrap';
    var label = document.createElement('span');
    label.className = 'team-admin-label';
    label.textContent = '예상 결과';
    w.appendChild(label);

    var chips = document.createElement('span');
    chips.innerHTML =
      '<span class="imp-chip imp-new">새 사용자 ' + s.users_new + '명</span>' +
      '<span class="imp-chip imp-match">기존 매칭 ' + s.users_match + '명</span>' +
      '<span class="imp-chip imp-add">출석 추가 ' + s.attendance_add + '건</span>' +
      '<span class="imp-chip imp-dup">중복 ' + s.attendance_dup + '건</span>' +
      '<span class="imp-chip imp-skip">미매칭 ' + s.attendance_nosuch + '건</span>' +
      (s.bad_rows ? '<span class="imp-chip imp-bad">형식 오류 ' + s.bad_rows + '줄</span>' : '') +
      '<span class="imp-chip imp-env">대상 환경 ' + (s.env === 'dev' ? '개발(dev)' : '운영(commercial)') + '</span>';
    chips.style.display = 'inline-flex';
    chips.style.gap = '6px';
    chips.style.flexWrap = 'wrap';
    w.appendChild(chips);
    box.appendChild(w);

    var rows = [];
    if (s.users_new) rows.push('새 사용자 ' + s.users_new + '명이 등록됩니다 (이름+소속 기준으로 기존 계정과 매칭되지 않은 사람).');
    if (s.users_match) rows.push('기존 사용자 ' + s.users_match + '명과 연결됩니다 (중복 생성 없음).');
    if (s.attendance_dup) rows.push('중복 출석 ' + s.attendance_dup + '건은 건너뜁니다 (같은 날짜·예배에 이미 있음).');
    if (s.attendance_nosuch) rows.push('미매칭 ' + s.attendance_nosuch + '건은 명단에 없는 이름이라 추가되지 않습니다.');
    if (s.bad_rows) rows.push('형식 오류 ' + s.bad_rows + '줄은 날짜/이름이 비어 무시됩니다.');
    if (!rows.length) rows.push('변경 없음 — 새 사용자도 새 출석도 없습니다.');

    var note = document.createElement('div');
    note.className = 'imp-note';
    note.textContent = '· ' + rows.join('\n· ');
    note.style.whiteSpace = 'pre-line';
    note.style.marginTop = '6px';
    note.style.color = 'var(--text-2, #6b7280)';
    note.style.fontSize = '13px';
    box.appendChild(note);

    var applyBtn = window.$('btn-imp-apply');
    applyBtn.disabled = !(s.users_new || s.attendance_add);
  }

  /** 미리보기 요청. */
  function onPreview() {
    var el = window.$('imp-file');
    var inp = el.files && el.files[0];
    if (!inp) { window.dialogManager.alert('파일을 먼저 선택하세요.', { title: '미리보기' }); return; }
    window.$('imp-file-hint').textContent = '';
    token = null;
    summary = null;
    window.dialogManager.toast('파일을 분석하는 중...');
    upload('/api/admin/import/preview', inp).then(function (res) {
      if (!res.ok) { window.dialogManager.alert(res.msg || '미리보기 실패', { title: '미리보기' }); return; }
      token = res.token;
      summary = res.summary;
      renderPreview(res);
      window.dialogManager.toast('분석 완료');
    }).catch(function () {
      token = null;
      summary = null;
      window.$('imp-file-hint').textContent = '서버 접속에 실패했습니다.';
    });
  }

  /** 실제 DB 반영. */
  function onApply() {
    if (!token) { window.dialogManager.alert('파일을 먼저 미리보기 해주세요.', { title: '적용' }); return; }
    var s = summary || {};
    var msg = '위 내용대로 DB에 적용합니다.\n새 사용자 ' + (s.users_new || 0) + '명, 출석 ' + (s.attendance_add || 0) + '건. 계속하시겠습니까?';
    window.dialogManager.confirm(msg, { title: '데이터 적용', okLabel: '적용' }, function () {
      window.api.request('/api/admin/import/commit', {
        method: 'POST',
        body: { token: token }
      }).then(function (res) {
        if (res.ok) {
          token = null;
          summary = null;
          window.$('imp-file').value = '';
          window.$('imp-file-hint').textContent = '적용 완료 — 신규 사용자 ' + res.users_new + '명, 출석 ' + res.attendance_add + '건 추가 (중복 ' + res.attendance_dup + '건 제외)';
          window.dialogManager.toast('데이터 적용 완료');
        } else window.dialogManager.alert(res.msg || '적용 실패', { title: '데이터 적용' });
      });
    });
  }

  /** 파일 변경 시 이름 표시 갱신 + 이전 미리보기 무효화. */
  function onFileChange() {
    var el = window.$('imp-file');
    var inp = el.files && el.files[0];
    var nameEl = window.$('imp-file-name');
    if (inp) {
      var kb = Math.max(1, Math.round(inp.size / 1024));
      nameEl.textContent = inp.name + ' (' + kb.toLocaleString('ko-KR') + ' KB)';
      nameEl.classList.add('has-file');
    } else {
      nameEl.textContent = '선택된 파일 없음';
      nameEl.classList.remove('has-file');
    }
    if (token) {
      token = null;
      summary = null;
      window.$('imp-preview').hidden = true;
      window.$('btn-imp-apply').disabled = true;
      window.$('imp-file-hint').textContent = '';
    }
  }

  /** 탭 로드 — 상태 초기화. */
  function loadTab() {
    var el = window.$('imp-file');
    if (!el.files || !el.files.length) {
      onFileChange();
      window.$('imp-preview').hidden = true;
      window.$('btn-imp-apply').disabled = true;
    }
  }

  /**
   * 모듈 초기화 — 버튼 이벤트 등록.
   */
  function init() {
    window.$('btn-import-template').addEventListener('click', onTemplate);
    window.$('btn-imp-preview').addEventListener('click', onPreview);
    window.$('btn-imp-apply').addEventListener('click', onApply);
    window.$('imp-file').addEventListener('change', onFileChange);
  }

  window.importManager = {
    init: init,
    loadTab: loadTab
  };
})();