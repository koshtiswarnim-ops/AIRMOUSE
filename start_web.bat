@echo off
title AIRMOUSE AI - Web Server Launcher
cd /d "%~dp0"
echo Starting AIRMOUSE AI Localhost Web Server...
echo Open your browser at: http://localhost:5000
".venv\Scripts\python.exe" web_server.py
pause
