/* ================================================================
   components/report.js — 보고서 / 내보내기 / 서버 종료 버튼
   ================================================================ */
(function () {
  'use strict';

  /**
   * 보고서 HTML을 PIN 헤더와 함께 가져와 새 탭에서 연다.
   * @param {string} path - 보고서 경로 (/api/report)
   */
  function openReport(path) {
    window.api.getReport(path)
      .then(function (html) {
        var blob = new Blob([html], { type: 'text/html;charset=utf-8' });
        var url = URL.createObjectURL(blob);
        window.open(url, '_blank');
        setTimeout(function () { URL.revokeObjectURL(url); }, 60000);
      })
      .catch(function (e) {
        window.dialogManager.alert(
          (e && e.message) || '보고서를 불러올 수 없습니다.',
          { title: '보고서 보기' });
      });
  }

  /** 종합 보고서 열기. */
  function onReport() {
    openReport('/api/report');
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
    window.$('btn-export-teams').addEventListener('click', onExportTeams);
    window.$('btn-shutdown').addEventListener('click', onShutdown);
  }

  window.reportManager = {
    init: init
  };
})();
