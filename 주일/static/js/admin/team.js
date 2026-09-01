/* ================================================================
   admin/team.js — 팀/소속 관리 탭
   (소속 일괄 이동, 이름 변경, 임시 소속, 팀 생성/변경/삭제, 새신우 기간)
   ================================================================ */
(function () {
  'use strict';

  /** 팀/소속 관리 드롭다운 채우기. */
  function populateTeamAdmin() {
    var meta = window.userFormManager.getMeta();
    var affSel = window.$('tm-move-aff');
    var teamSel = window.$('tm-move-team');
    var oldSel = window.$('tm-rename-old');
    var delSel = window.$('tm-delete-team');
    var affOldSel = window.$('am-rename-old');
    [affSel, teamSel, oldSel, delSel, affOldSel].forEach(function (sel) {
      sel.innerHTML = '<option value="">선택하세요</option>';
    });
    meta.affiliations.forEach(function (a) {
      var opt = document.createElement('option');
      opt.value = a; opt.textContent = a;
      affSel.appendChild(opt);
      var o2 = document.createElement('option');
      o2.value = a; o2.textContent = a;
      affOldSel.appendChild(o2);
    });
    meta.teams.forEach(function (t) {
      var o1 = document.createElement('option'); o1.value = t; o1.textContent = t;
      var o2 = document.createElement('option'); o2.value = t; o2.textContent = t;
      var o3 = document.createElement('option'); o3.value = t; o3.textContent = t;
      teamSel.appendChild(o1);
      oldSel.appendChild(o2);
      delSel.appendChild(o3);
    });
  }

  /** 팀 관리 탭 로드 — 메타데이터 + 새신우 기간 조회. */
  function loadTab() {
    window.userFormManager.loadTeamsAndAffiliations(populateTeamAdmin);
    window.api.getNewbieDays()
      .then(function (res) {
        window.$('tm-newbie-days').value = res.days;
        window.$('tm-newbie-hint').textContent = '비고의 새신우 태그가 ' + res.days + '일 후 자동 삭제됩니다';
      });
    window.api.getSundayDetailThreshold()
      .then(function (res) {
        window.$('tm-sunday-threshold').value = res.sundayDetailThreshold;
        window.$('tm-sunday-hint').textContent = '일요일 전체 출석자가 ' + res.sundayDetailThreshold + '명 미만이면 통합 보고서에 상세 명단을 표시합니다';
      });
  }

  /** 팀/소속 변경 후 명단 및 드롭다운 갱신. */
  function refreshAfterTeamChange() {
    window.rosterManager.load();
    window.userFormManager.loadTeamsAndAffiliations(populateTeamAdmin);
  }

  /** 소속 일괄 이동. */
  function onTeamMove() {
    var aff = window.$('tm-move-aff').value;
    var team = window.$('tm-move-team').value;
    if (!aff || !team) { window.dialogManager.alert('소속과 이동할 팀을 모두 선택하세요.', { title: '팀 이동' }); return; }
    window.dialogManager.confirm("'" + aff + "' 소속 전체를 '" + team + "'(으)로 이동하시겠습니까?", { title: '팀 이동', okLabel: '이동' }, function () {
      window.api.teamsBulkMove(aff, team)
        .then(function (res) {
          if (res.ok) {
            window.dialogManager.toast("'" + aff + "' 소속 " + res.moved + "명 → '" + team + "' 이동 완료");
            refreshAfterTeamChange();
          } else window.dialogManager.alert(res.msg || '이동 실패', { title: '팀 이동 실패' });
        });
    });
  }

  /** 소속 이름 변경. */
  function onAffRename() {
    var oldName = window.$('am-rename-old').value;
    var newName = window.$('am-rename-new').value.trim();
    if (!oldName || !newName) { window.dialogManager.alert('변경할 소속과 새 이름을 모두 입력하세요.', { title: '소속 이름 변경' }); return; }
    window.dialogManager.confirm("'" + oldName + "' 소속을 '" + newName + "'(으)로 변경하시겠습니까?", { title: '소속 이름 변경', okLabel: '변경' }, function () {
      window.api.affRename(oldName, newName)
        .then(function (res) {
          if (res.ok) {
            window.dialogManager.toast("'" + oldName + "' 소속 → '" + newName + "' 변경 완료");
            window.$('am-rename-new').value = '';
            refreshAfterTeamChange();
          } else window.dialogManager.alert(res.msg || '변경 실패', { title: '소속 이름 변경 실패' });
        });
    });
  }

  /** 임시 소속 추가. */
  function onAffCreate() {
    var name = window.$('am-create-name').value.trim();
    window.api.affCreate(name)
      .then(function (res) {
        if (res.ok) {
          window.dialogManager.toast("'" + res.name + "' 소속이 추가되었습니다.");
          window.$('am-create-name').value = '';
          refreshAfterTeamChange();
        } else window.dialogManager.alert(res.msg || '추가 실패', { title: '임시 소속 추가 실패' });
      });
  }

  /** 팀 이름 변경. */
  function onTeamRename() {
    var oldName = window.$('tm-rename-old').value;
    var newName = window.$('tm-rename-new').value.trim();
    if (!oldName || !newName) { window.dialogManager.alert('변경할 팀과 새 이름을 모두 입력하세요.', { title: '팀 이름 변경' }); return; }
    window.dialogManager.confirm("'" + oldName + "' 팀을 '" + newName + "'(으)로 변경하시겠습니까?", { title: '팀 이름 변경', okLabel: '변경' }, function () {
      window.api.teamRename(oldName, newName)
        .then(function (res) {
          if (res.ok) {
            window.dialogManager.toast("'" + oldName + "' 팀 → '" + newName + "' 변경 완료");
            window.$('tm-rename-new').value = '';
            refreshAfterTeamChange();
          } else window.dialogManager.alert(res.msg || '변경 실패', { title: '팀 이름 변경 실패' });
        });
    });
  }

  /** 새 팀 생성. */
  function onTeamCreate() {
    var name = window.$('tm-create-name').value.trim();
    if (!name) { window.dialogManager.alert('새 팀 이름을 입력하세요.', { title: '새 팀 생성' }); return; }
    window.api.teamCreate(name)
      .then(function (res) {
        if (res.ok) {
          window.dialogManager.toast("'" + name + "' 팀이 생성되었습니다.");
          window.$('tm-create-name').value = '';
          window.userFormManager.loadTeamsAndAffiliations(populateTeamAdmin);
        } else window.dialogManager.alert(res.msg || '생성 실패', { title: '새 팀 생성 실패' });
      });
  }

  /** 팀 삭제. */
  function onTeamDelete() {
    var name = window.$('tm-delete-team').value;
    if (!name) { window.dialogManager.alert('삭제할 팀을 선택하세요.', { title: '팀 삭제' }); return; }
    window.dialogManager.confirm("'" + name + "' 팀을 삭제하시겠습니까?", { title: '팀 삭제', okLabel: '삭제', destructive: true }, function () {
      window.api.teamDelete(name)
        .then(function (res) {
          if (res.ok) {
            window.dialogManager.toast("'" + name + "' 팀이 삭제되었습니다.");
            window.$('tm-delete-team').value = '';
            window.userFormManager.loadTeamsAndAffiliations(populateTeamAdmin);
          } else window.dialogManager.alert(res.msg || '삭제 실패', { title: '팀 삭제 실패' });
        });
    });
  }

  /** 새신우 유지 기간 설정. */
  function onNewbieDays() {
    var days = parseInt(window.$('tm-newbie-days').value, 10);
    if (!days || days < 1 || days > 365) { window.dialogManager.alert('1~365 사이의 숫자를 입력하세요.', { title: '새신우 유지 기간' }); return; }
    window.dialogManager.confirm('새신우 유지 기간을 ' + days + '일로 변경하시겠습니까?', { title: '새신우 유지 기간', okLabel: '변경' }, function () {
      window.api.setNewbieDays(days)
        .then(function (res) {
          if (res.ok) {
            window.dialogManager.toast('새신우 유지 기간이 ' + res.days + '일로 변경되었습니다.');
            loadTab();
          } else window.dialogManager.alert(res.msg || '저장 실패', { title: '새신우 유지 기간' });
        });
    });
  }

  /** 일요일 상세 명단 표시 기준 설정. */
  function onSundayThreshold() {
    var threshold = parseInt(window.$('tm-sunday-threshold').value, 10);
    if (!threshold || threshold < 1 || threshold > 999) { window.dialogManager.alert('1~999 사이의 숫자를 입력하세요.', { title: '일요일 상세 명단 기준' }); return; }
    window.dialogManager.confirm('일요일 전체 출석자가 ' + threshold + '명 미만이면 통합 보고서에 상세 명단을 표시합니다. 변경하시겠습니까?', { title: '일요일 상세 명단 기준', okLabel: '변경' }, function () {
      window.api.setSundayDetailThreshold(threshold)
        .then(function (res) {
          if (res.ok) {
            window.dialogManager.toast('일요일 상세 명단 기준이 ' + res.sundayDetailThreshold + '명으로 변경되었습니다.');
            loadTab();
          } else window.dialogManager.alert(res.msg || '저장 실패', { title: '일요일 상세 명단 기준' });
        });
    });
  }

  /**
   * 모듈 초기화 — 팀/소속 관리 버튼 이벤트 등록.
   */
  function init() {
    window.$('btn-team-move').addEventListener('click', onTeamMove);
    window.$('btn-aff-rename').addEventListener('click', onAffRename);
    window.$('btn-aff-create').addEventListener('click', onAffCreate);
    window.$('btn-team-rename').addEventListener('click', onTeamRename);
    window.$('btn-team-create').addEventListener('click', onTeamCreate);
    window.$('btn-team-delete').addEventListener('click', onTeamDelete);
    window.$('btn-newbie-days').addEventListener('click', onNewbieDays);
    window.$('btn-sunday-threshold').addEventListener('click', onSundayThreshold);
  }

  window.teamManager = {
    init: init,
    loadTab: loadTab,
    populateTeamAdmin: populateTeamAdmin,
    refreshAfterTeamChange: refreshAfterTeamChange
  };
})();
