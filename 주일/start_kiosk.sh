#!/bin/bash
# 출석 키오스크 원터치 실행 스크립트 (Termux/Linux)
set -e
DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$DIR"

PORT="${KIOSK_PORT:-8665}"
URL="http://127.0.0.1:${PORT}"

echo "[1/3] 필요한 패키지를 확인합니다..."
if ! python3 -c "import flask, openpyxl" >/dev/null 2>&1; then
    echo "      필요한 패키지를 설치합니다... (최초 1회)"
    python3 -m pip install -r requirements.txt
fi

echo "[2/3] 출석 서버를 시작합니다... (${URL})"
echo "      시작 시 backups/ 폴더에 DB 자동 백업(.db.bak)"
python3 app.py &
SRV=$!

# 서버가 뜰 때까지 대기 (최대 20초)
for i in $(seq 1 20); do
    if python3 -c "import urllib.request; urllib.request.urlopen('${URL}', timeout=1)" 2>/dev/null; then
        break
    fi
    sleep 1
done

echo "[3/3] 브라우저를 엽니다..."
if command -v termux-open-url >/dev/null 2>&1; then
    termux-open-url "${URL}"
else
    python3 -c "import webbrowser; webbrowser.open('${URL}')" 2>/dev/null || true
fi

echo ""
echo "서버 실행 중: ${URL}"
echo "종료하려면 Ctrl+C 를 누르세요."
wait $SRV