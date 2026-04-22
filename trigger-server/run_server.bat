@echo off
chcp 65001 > nul
title DMS 트리거 서버

cd /d "%~dp0"

echo.
echo  =============================================
echo    DMS 트리거 서버
echo  =============================================
echo.

REM 패키지 확인
python -c "import flask, flask_cors, selenium" 2>nul
if %errorlevel% neq 0 (
    echo  패키지 설치 중...
    pip install flask flask-cors selenium
)

REM cloudflared 설치 확인
where cloudflared > nul 2>&1
if %errorlevel% neq 0 (
    echo.
    echo  [주의] cloudflared 가 없습니다.
    echo  아래 URL에서 다운로드 후 PATH에 추가하세요:
    echo  https://github.com/cloudflare/cloudflared/releases/latest
    echo.
    echo  cloudflared 없이 로컬(같은 WiFi)에서만 사용하려면 Enter를 누르세요.
    pause > nul
    echo.
    echo  서버 URL: http://[PC IP]:5001
    echo  PC IP 확인: ipconfig
    echo.
    python trigger_server.py
    pause
    exit /b 0
)

echo  Flask 서버 시작 중...
start /b python trigger_server.py

timeout /t 2 /nobreak > nul

echo  Cloudflare 터널 시작 중...
echo.
echo  ─────────────────────────────────────────────
echo  아래 표시되는 https://xxxx.trycloudflare.com
echo  URL을 대시보드 DMS 설정에 입력하세요.
echo  ─────────────────────────────────────────────
echo.
cloudflared tunnel --url http://localhost:5001

pause
