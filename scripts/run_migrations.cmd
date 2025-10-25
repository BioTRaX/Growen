@echo off
setlocal enabledelayedexpansion

REM Raíz del repo (carpeta padre de /scripts)
set "ROOT=%~dp0.."
for %%I in ("%ROOT%") do set "ROOT=%%~fI"

REM Carpeta de logs
set "LOGDIR=%ROOT%\logs\migrations"
if not exist "%LOGDIR%" mkdir "%LOGDIR%"

REM Timestamp seguro (yyyymmdd_HHMMSS) usando PowerShell (WMIC deprecado)
for /f %%t in ('powershell -NoProfile -Command "Get-Date -Format yyyyMMdd_HHmmss"') do set "TS=%%t"
set "MIGLOG=%LOGDIR%\alembic_%TS%.log"

REM Python del venv
set "PYTHON=%ROOT%\.venv\Scripts\python.exe"
if not exist "%PYTHON%" (
  echo [ERROR] No se encontró Python del entorno virtual en "%PYTHON%"
  exit /b 1
)

REM Chequeo de carpetas clave
if not exist "%ROOT%\db\migrations" (
  echo [ERROR] No existe "%ROOT%\db\migrations"
  echo         Verifique que el repo tenga las migraciones. Abortando.
  exit /b 1
)
if not exist "%ROOT%\db\migrations\env.py" (
  echo [ERROR] No existe "%ROOT%\db\migrations\env.py"
  echo         El arbol de Alembic está incompleto. Abortando.
  exit /b 1
)

REM Cambiar directorio al root del repo (importante para rutas relativas)
pushd "%ROOT%"

echo [INFO] Ejecutando: alembic --raiseerr -x log_sql=1 -c "%ROOT%\alembic.ini" upgrade head
"%PYTHON%" -m alembic --raiseerr -x log_sql=1 -c "%ROOT%\alembic.ini" upgrade head 1>>"%MIGLOG%" 2>&1
set "ERR=%ERRORLEVEL%"

popd

if not "%ERR%"=="0" (
  echo [ERROR] Fallo al aplicar migraciones. Revise el log:
  echo        "%MIGLOG%"
  exit /b %ERR%
)

echo [INFO] Migraciones aplicadas con éxito. Log:
echo        "%MIGLOG%"
exit /b 0
