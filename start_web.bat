@echo off
title AIRMOUSE AI - Web Server Launcher
cd /d "%~dp0"
echo ================================================================
echo Starting AIRMOUSE AI Localhost Web Server...
echo Opening browser at: http://localhost:5000
echo Alternate address:  http://127.0.0.1:5000
echo ================================================================
start "" http://localhost:5000
".venv\Scripts\python.exe" web_server.py
pause
