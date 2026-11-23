@echo off
cd /d "%~dp0.."
if not exist "backend\.venv\Scripts\python.exe" (
 echo Primero ejecuta PREPARAR_EQUIPO.bat, en esta misma carpeta.
 pause
 exit /b 1
)
"backend\.venv\Scripts\python.exe" backend\equipo.py iniciar
pause
