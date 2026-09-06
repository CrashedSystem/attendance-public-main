@echo off
chcp 65001 >nul
cd /d "%~dp0"

echo ============================================
echo  출석 DB 복원 (backups 의 최신 백업으로)
echo ============================================
if not exist "backups\군종_*.db.bak" goto nobackup

for /f "tokens=*" %%f in ('dir /b /o-d backups\군종_*.db.bak') do (
    set "LATEST=%%f"
    goto found
)

:found
echo 복원할 백업: %LATEST%
echo 현재 군종.db 를 backups\로 대체합니다...
copy /y "backups\%LATEST%" "군종.db" >nul
echo.
echo 복원 완료! 이제 서버를 다시 실행(또는 재시작)하세요.
pause
exit /b 0

:nobackup
echo 백업 파일이 없습니다. (backups 폴더 확인)
pause
exit /b 1