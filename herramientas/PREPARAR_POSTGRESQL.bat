@echo off
cd /d "%~dp0..\backend"
".venv\Scripts\python.exe" preparar_local.py
pause
