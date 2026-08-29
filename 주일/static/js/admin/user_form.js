/* ================================================================
   admin/user_form.js — 사용자 등록/수정 폼
   ================================================================ */
(function () {
  'use strict';

  var editingId = null;
  var metaTeams = [];
  var metaAffiliations = [];
  var affToTeam = {};
  var teamToAff = {};
  var isSyncing = false;

  /**
   * 팀/소속 메타데이터 및 매핑 로드 후 드롭다운 갱신.
   * @param {Function} [cb] - 완료 콜백
   */
  function loadTeamsAndAffiliations(cb) {
    window.api.getTeamsAffiliations()
      .then(function (res) {
        metaTeams = res.teams || [];
        metaAffiliations = res.affiliations || [];
        affToTeam = res.mapping || {};
        teamToAff = {};
        for (var aff in affToTeam) {
          teamToAff[affToTeam[aff]] = aff;
        }
        populateDropdowns();
        if (cb) cb();
      });
  }

  /**
   * 로드된 팀/소속 메타데이터 반환.
   * @returns {{teams:Array, affiliations:Array, affToTeam:Object, teamToAff:Object}}
   */
  function getMeta() {
    return {
      teams: metaTeams,
      affiliations: metaAffiliations,
      affToTeam: affToTeam,
      teamToAff: teamToAff
    };
  }

  /** 소속/팀 드롭다운 채우기 (현재 선택 유지). */
  function populateDropdowns() {
    var affSelect = window.$('f-affiliation');
    var teamSelect = window.$('f-team');

    var currentAff = affSelect.value;
    var currentTeam = teamSelect.value;

    affSelect.innerHTML = '<option value="">선택하세요</option>';
    metaAffiliations.forEach(function (aff) {
      var opt = document.createElement('option');
      opt.value = aff;
      opt.textContent = aff;
      affSelect.appendChild(opt);
    });

    teamSelect.innerHTML = '<option value="">선택하세요</option>';
    metaTeams.forEach(function (team) {
      var opt = document.createElement('option');
      opt.value = team;
      opt.textContent = team;
      teamSelect.appendChild(opt);
    });

    affSelect.value = currentAff;
    teamSelect.value = currentTeam;
  }

  /** 소속 → 팀 자동 동기화. */
  function onAffChange() {
    if (isSyncing) return;
    isSyncing = true;
    var aff = window.$('f-affiliation').value;
    var teamSelect = window.$('f-team');
    if (!aff) {
      teamSelect.value = '';
    } else if (affToTeam[aff]) {
      teamSelect.value = affToTeam[aff];
    }
    isSyncing = false;
  }

  /** 팀 → 소속 자동 동기화. */
  function onTeamChange() {
    if (isSyncing) return;
    isSyncing = true;
    var team = window.$('f-team').value;
    var affSelect = window.$('f-affiliation');
    if (!team) {
      affSelect.value = '';
    } else if (teamToAff[team]) {
      affSelect.value = teamToAff[team];
    }
    isSyncing = false;
  }

  /** 신규 등록 폼 열기 — 모든 입력 초기화. */
  function openNew() {
    editingId = null;
    loadTeamsAndAffiliations();
    window.$('form-title').textContent = '신규 등록';
    ['f-name', 'f-baptism', 'f-affiliation', 'f-team', 'f-prev-church', 'f-phone', 'f-discharge', 'f-birthday', 'f-note']
      .forEach(function (f) { window.$(f).value = ''; });
    window.$('f-chaplain').checked = false;
    window.screenManager.show('screen-user-form');
  }

  /**
   * 수정 폼 열기 — 기존 사용자 데이터 채우기.
   * @param {number} id - 사용자 id
   */
  function open(id) {
    editingId = id;
    loadTeamsAndAffiliations();
    window.api.getUsers()
      .then(function (users) {
        var u = users.filter(function (x) { return x.id === id; })[0];
        if (!u) return;
        window.$('form-title').textContent = '수정 - No.' + id + ' ' + u.name;
        window.$('f-name').value = u.name || '';
        window.$('f-baptism').value = u.baptism || '';
        window.$('f-affiliation').value = u.affiliation || '';
        window.$('f-team').value = u.team || '';
        window.$('f-prev-church').value = u.prev_church || '';
        window.$('f-phone').value = u.phone || '';
        window.$('f-discharge').value = u.discharge_date || '';
        window.$('f-birthday').value = u.birthday || '';
        window.$('f-note').value = u.note || '';
        window.$('f-chaplain').checked = !!u.is_chaplain;
        window.screenManager.show('screen-user-form');
      });
  }

  /** 저장 처리 — 입력 검증 후 POST/PUT. */
  function save() {
    var payload = {
      name: window.$('f-name').value.trim(),
      baptism: window.$('f-baptism').value.trim(),
      affiliation: window.$('f-affiliation').value.trim(),
      team: window.$('f-team').value.trim(),
      prev_church: window.$('f-prev-church').value.trim(),
      phone: window.$('f-phone').value.trim(),
      discharge_date: window.$('f-discharge').value.trim(),
      birthday: window.$('f-birthday').value.trim(),
      note: window.$('f-note').value.trim(),
      is_chaplain: window.$('f-chaplain').checked ? 1 : 0
    };
    if (!payload.name) { window.dialogManager.alert('이름을 입력하세요.', { title: '입력 확인' }); return; }
    if (payload.birthday) {
      var bm = payload.birthday.match(/^(\d{2})(\d{2})$/);
      if (!bm || parseInt(bm[1], 10) < 1 || parseInt(bm[1], 10) > 12 ||
          parseInt(bm[2], 10) < 1 || parseInt(bm[2], 10) > 31) {
        window.dialogManager.alert('생일은 MMDD 형식(예: 0102) 4자리 숫자로 입력하세요.', { title: '입력 확인' }); return;
      }
    }
    window.api.saveUser(payload, editingId)
      .then(function (res) {
        if (res.ok) { window.authManager.openAdmin(); }
        else window.dialogManager.alert(res.msg || '저장 실패', { title: '저장 실패' });
      });
  }

  /**
   * 모듈 초기화 — 폼 관련 이벤트 등록.
   */
  function init() {
    window.$('f-affiliation').addEventListener('change', onAffChange);
    window.$('f-team').addEventListener('change', onTeamChange);
    window.$('btn-add-user').addEventListener('click', openNew);
    window.$('btn-form-cancel').addEventListener('click', function () { window.authManager.openAdmin(); });
    window.$('f-birthday').addEventListener('input', function () {
      this.value = this.value.replace(/\D/g, '').slice(0, 4);
    });
    window.$('btn-form-save').addEventListener('click', save);
  }

  window.userFormManager = {
    init: init,
    open: open,
    openNew: openNew,
    loadTeamsAndAffiliations: loadTeamsAndAffiliations,
    getMeta: getMeta
  };
})();
