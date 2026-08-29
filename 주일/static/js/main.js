/* ================================================================
   main.js — 앱 진입점 (모듈 초기화 및 부팅)
   ================================================================ */
(function () {
  'use strict';

  /**
   * 앱 초기화 — 모든 모듈의 init 호출 및 초기 화면 구성.
   */
  function init() {
    // 의존성 순서대로 모듈 초기화
    window.dialogManager.init();   // 다이얼로그 DOM 캐시 (다른 모듈이 의존)
    window.themeManager.init();    // 테마 (btn-theme 등록)
    window.screenManager && window.screenManager.init && window.screenManager.init();

    // 공개 기능
    window.checkinManager.init();
    window.searchManager.init();   // 입력 이벤트 + 초기 검색

    // 관리자 기능
    window.authManager.init();     // 키패드 + admin-zone/back
    window.modeManager.init();     // 모드 버튼
    window.rosterManager.init();   // 명단 필터/정렬
    window.userFormManager.init(); // 사용자 폼
    window.bulkManager.init();     // 일괄 출석
    window.teamManager.init();     // 팀/소속 버튼
    window.absenceManager.init();  // 결석 탭
    window.historyManager.init();  // 기록/시간 탭

    // 컴포넌트
    window.tabsManager.init();
    window.reportManager.init();

    // 커스텀 date -> 달력 변환 (동적 요소 감지 포함)
    window.picker.init();

    // 초기 화면 + 주기 갱신
    window.$('today').textContent = window.utils.fmtToday();
    setInterval(function () { window.$('today').textContent = window.utils.fmtToday(); }, 30000);

    // 서버 모드 로드 (loadMode -> clearInput -> 재검색)
    window.modeManager.load();
  }

  // DOM 준비 후 부팅
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();
