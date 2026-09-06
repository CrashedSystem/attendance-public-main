@echo off
chcp 65001 >nul
cd /d "%~dp0"

echo ============================================
echo  kiosk.exe (출석 키오스크 원터치 프로그램) 빌드
echo  - PNG 보고서용 Chromium 을 exe 안에 포함
echo ============================================
echo [1/5] PyInstaller 확인/설치 중...
pip show pyinstaller >nul 2>&1 || pip install pyinstaller
if errorlevel 1 goto fail

echo [2/5] playwright(보고서 PNG용) 확인/설치 중...
pip show playwright >nul 2>&1 || pip install playwright
if errorlevel 1 goto fail

echo [3/5] Chromium 브라우저 설치 중... (약 150~200MB, 최초 1회)
call playwright install chromium
if errorlevel 1 goto fail

set "PWBR=%LocalAppData%\ms-playwright"
if not exist "%PWBR%\" set "PWBR=%USERPROFILE%\AppData\Local\ms-playwright"

echo [4/5] kiosk.exe 빌드 중... (1~3분 소요, 파일 약 200~300MB)
pyinstaller --noconfirm --onefile --noconsole --name kiosk ^
  --add-data "static;static" ^
  --add-data "report_template.html;." ^
  --hidden-import "playwright.sync_api" ^
  --hidden-import "playwright.async_api" ^
  --add-binary "%PWBR%;ms-playwright" ^
  kiosk_main.py
if errorlevel 1 goto fail

echo [5/5] 완료!
echo.
echo    생성 파일 : dist\kiosk.exe    (Chromium 포함 → PNG 보고서까지 원터치 동작)
echo    사용법   : dist\kiosk.exe 복사 후 실행  (군종.db / backups 폴더는 exe 옆에 생성됨)
echo    주의     : 최초 실행 시 압축해제로 10~60초 걸릴 수 있습니다.
echo.
pause
exit /b 0

:fail
echo.
echo 빌드 실패. Python 설치 및 pip 확인 후 다시 시도하세요.
pause
exit /b 1