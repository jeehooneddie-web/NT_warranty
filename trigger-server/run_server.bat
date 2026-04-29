@echo off
title DMS Trigger Server

cd /d "%~dp0"

py -c "import flask, flask_cors, selenium" 2>nul
if %errorlevel% neq 0 (
    echo Installing packages...
    py -m pip install flask flask-cors selenium
)

echo Starting DMS Trigger Server...
py trigger_server.py

pause
