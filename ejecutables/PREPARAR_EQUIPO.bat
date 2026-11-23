@echo off
cd /d "%~dp0.."
echo PREPARACION INICIAL DE REGOVA - hacer antes de la presentacion.
echo Requiere Python 3.13 x64 y PostgreSQL instalados. Puede necesitar internet.
where py >nul 2>nul
if not errorlevel 1 (
 py -3.13 backend\equipo.py preparar
) else (
 python backend\equipo.py preparar
)
pause
