@echo off
cd /d "%~dp0.."
call npm.cmd run test:qa
set "QA_EXIT=%ERRORLEVEL%"
"backend\.venv\Scripts\python.exe" scripts\qa_report.py
if errorlevel 1 exit /b 1
exit /b %QA_EXIT%
