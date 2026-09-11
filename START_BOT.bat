@echo off
title CookieRun Classic Bot
cd /d "%~dp0\src"
start "" pythonw run_app.py
exit /b