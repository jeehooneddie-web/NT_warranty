@echo off
title DMS AutoStart

REM Wait for network
timeout /t 15 /nobreak > nul

REM Start Chrome with debug port
netstat -an | find ":9222" > nul 2>&1
if %errorlevel% neq 0 (
    start "" "C:\Program Files\Google\Chrome\Application\chrome.exe" --remote-debugging-port=9222 --user-data-dir="%TEMP%\chrome_dms" "https://bmwdms.co.kr/"
    timeout /t 5 /nobreak > nul
)

REM Start trigger server (cloudflared runs inside)
cd /d "%~dp0"
start /min "" py trigger_server.py
