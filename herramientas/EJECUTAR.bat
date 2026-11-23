@echo off
cd /d "%~dp0..\backend"
if not exist ".env" (
 echo Primero ejecuta PREPARAR_POSTGRESQL.bat, en esta misma carpeta, para configurar la API.
 pause
 exit /b 1
)
set "SHELFVISION_TRAIN_PYTHON=%~dp0..\backend\.venv-train\Scripts\python.exe"
set "YOLO_CONFIG_DIR=%~dp0..\backend\data\training\ultralytics_config"
set "MPLCONFIGDIR=%~dp0..\backend\data\training\mpl_config"
echo REGOVA API: http://127.0.0.1:8011
echo Documentacion: http://127.0.0.1:8011/api/docs
".venv\Scripts\python.exe" -m uvicorn app.main:app --host 127.0.0.1 --port 8011 --workers 1 --log-level info
pause
