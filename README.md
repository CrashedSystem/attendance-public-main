# 충성교회 주일 출석 자동화 (키오스크)

주일 예배 출석을 키오스크(전체 화면 브라우저)로 자동화하는 시스템.
Python Flask + SQLite, 데이터는 `군종.db`에 저장됩니다.

## 실행 방법

1. `start_kiosk.bat` 실행
   - 내부: `pythonw app.py`로 서버 시작 → Chrome/Edge 키오스크 모드로 `localhost:5000` 접속
2. 종료: 키오스크 창에서 `Alt+F4` → 서버는 `taskkill /f /im pythonw.exe`

## 프로젝트 구조

- `app.py` — Flask 서버 (출석 기록/관리)
- `consecutive_absence.py` — 결석 연속 확인
- `excel_adapter.py` — 엑셀 연동
- `create_db.py` — DB 초기화
- `static/` — 키오스크 UI (index.html / kiosk.js / kiosk.css / fonts)
- `군종.db.schema` — 빈 테이블 형식만 갖춘 DB 템플릿 (Git 추적 대상)

## 출석 데이터 보안 (중요)

- 실제 교인 데이터가 담긴 `군종.db`와 백업(`군종.db.bak_*`)은 **Git에 올리지 않음** (`.gitignore`로 제외, 로컬에만 보관)
- 원본은 `C:\충성교회\자동화\백업\출석DB\`에 별도 백업해 둠
- 새 환경에서는 `군종.db.schema`를 `군종.db`로 복사해 사용: `copy 군종.db.schema 군종.db`
- 주기적으로 원본 DB를 `백업\출석DB`에 복사해 두는 것을 권장

## Git 유지보수 규칙

- **브랜치**: `main`(안정) → 수정은 `dev` 또는 `feat-<이름>` 브랜치에서
- **커밋 메시지** (한국어 접두어):
  - `feat:` 새 기능 / `fix:` 버그 수정 / `refactor:` 개선 / `docs:` 문서
- **push**: `git push` / **pull**: `git pull`
- **제외 파일**: `.chrome_profile/`(브라우저 캐시), `__pycache__/`, `*.db`(실데이터)는 커밋하지 않음

## 출석 데이터 백업

```bash
copy 군종.db "C:\충성교회\자동화\백업\출석DB\군종.db.bak_YYYYMMDD"
```