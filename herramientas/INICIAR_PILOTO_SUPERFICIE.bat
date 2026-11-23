@echo off
setlocal
set "REGOVA_SURFACE_PILOT=1"
call "%~dp0..\ejecutables\INICIAR_REGOVA.bat"
exit /b %errorlevel%
