@echo off
chcp 65001 >nul
cd /d "%~dp0"

set "CHROME="
set "EDGE="

if exist "C:\Program Files\Google\Chrome\Application\chrome.exe" set "CHROME=C:\Program Files\Google\Chrome\Application\chrome.exe"
if exist "C:\Program Files (x86)\Google\Chrome\Application\chrome.exe" set "CHROME=C:\Program Files (x86)\Google\Chrome\Application\chrome.exe"
if exist "%LocalAppData%\Google\Chrome\Application\chrome.exe" set "CHROME=%LocalAppData%\Google\Chrome\Application\chrome.exe"

if exist "C:\Program Files\Microsoft\Edge\Application\msedge.exe" set "EDGE=C:\Program Files\Microsoft\Edge\Application\msedge.exe"
if exist "C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe" set "EDGE=C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"

echo [1/2] 출석 서버를 시작합니다... (개발자 모드)
start "kiosk-server" /min pythonw app.py dev

set tries=0
:wait
set /a tries+=1
>nul 2>&1 powershell -Command "(Invoke-WebRequest -Uri 'http://localhost:5000' -UseBasicParsing -TimeoutSec 3)"
if not errorlevel 1 goto up
if %tries% geq 30 goto fail
ping -n 2 127.0.0.1 >nul
goto wait

:up
echo [2/2] 브라우저를 시작합니다...
if defined CHROME goto launch_chrome
if defined EDGE goto launch_edge
start "" http://localhost:5000
goto done

:launch_chrome
start "" "%CHROME%" --kiosk --start-fullscreen --no-first-run --disable-session-crashed-bubble "--user-data-dir=%~dp0.chrome_profile" http://localhost:5000
goto done

:launch_edge
start "" "%EDGE%" --kiosk --start-fullscreen --no-first-run --disable-session-crashed-bubble "--user-data-dir=%~dp0.chrome_profile" http://localhost:5000
goto done

:fail
echo 서버 시작 실패. Python 설치를 확인하세요.
pause
exit /b 1

:done
echo 완료되었습니다. 창을 닫으려면 아무 키나 누르세요.
pause >nul