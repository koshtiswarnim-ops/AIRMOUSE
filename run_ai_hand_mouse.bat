@echo off
title AI Hand Mouse
cd /d "%~dp0"
echo Starting AI Hand Mouse...
echo Controls your Windows cursor across all apps and desktop.
echo Close the window or press ESC/q to exit.
".venv\Scripts\python.exe" ai_hand_mouse.py
pause
