/* ================================================================
   components/report.js — 보고서 / 내보내기 / 서버 종료 버튼
   ================================================================ */
(function () {
  'use strict';

  /** 종합 보고서 열기. */
  function onReport() {
    window.location.href = '/api/report';
  }

  /** A4 보고서 열기. */
  function onReportA4() {
    window.location.href = '/api/report/a4';
  }

  /** 팀별 보고서 내보내기. */
  function onExportTeams() {
    window.api.exportTeams()
      .then(function (res) {
        if (res.ok) {
          window.dialogManager.alert('팀별 보고서 파일이 성공적으로 생성 및 내보내기 되었습니다.\n저장 폴더: ' + res.dir, { title: '내보내기 완료' });
        } else {
          window.dialogManager.alert(res.msg || '내보내기 실패', { title: '내보내기 실패' });
        }
      });
  }

  /** 서버 종료 (보고서 저장 후). */
  function onShutdown() {
    window.dialogManager.confirm('웹 보고서를 저장하고 서버를 종료합니다.\n계속할까요?', { title: '서버 종료', okLabel: '종료', destructive: true }, function () {
      window.api.shutdown()
        .then(function (res) {
          if (res.ok) {
            window.dialogManager.alert('웹 보고서가 갱신되었습니다.\n' + res.report + '\n서버를 종료합니다.', { title: '서버 종료' }, function () {
              window.close();
            });
          } else {
            window.dialogManager.alert(res.msg || '보고서 생성 실패', { title: '서버 종료 실패' });
          }
        });
    });
  }

  /**
   * 모듈 초기화 — 보고서/내보내기/종료 버튼 이벤트 등록.
   */
  function init() {
    window.$('btn-report').addEventListener('click', onReport);
    window.$('btn-report-a4').addEventListener('click', onReportA4);
    window.$('btn-export-teams').addEventListener('click', onExportTeams);
    window.$('btn-shutdown').addEventListener('click', onShutdown);
  }

  window.reportManager = {
    init: init
  };
})();
