@echo off
setlocal enabledelayedexpansion

REM Raíz del repo (carpeta del script)
set "ROOT=%~dp0.."
REM Normalizar barra final
for %%I in ("%ROOT%") do set "ROOT=%%~fI"

REM Carpeta de logs
set "LOGDIR=%ROOT%\logs\migrations"
if not exist "%LOGDIR%" mkdir "%LOGDIR%"

REM Timestamp seguro usando WMIC (formato yyyymmdd_HHMMSS)
for /f %%i in ('wmic os get localdatetime ^| find "."') do set "TS=%%i"
set "TS=%TS:~0,8%_%TS:~8,6%"
REM TODO: si WMIC no está disponible, usar date /t y time /t como fallback.

set "MIGLOG=%LOGDIR%\alembic_%TS%.log"

REM Resolver Python del venv
set "PYTHON=%ROOT%\.venv\Scripts\python.exe"
if not exist "%PYTHON%" (
  echo [ERROR] No se encontró Python del entorno virtual en "%PYTHON%"
  exit /b 1
)

REM Ejecutar migraciones con opciones GLOBALES antes del subcomando
echo [INFO] Ejecutando: alembic --raiseerr -x log_sql=1 -c "%ROOT%\alembic.ini" upgrade head
"%PYTHON%" -m alembic --raiseerr -x log_sql=1 -c "%ROOT%\alembic.ini" upgrade head 1>>"%MIGLOG%" 2>&1

if errorlevel 1 (
  echo [ERROR] Fallo al aplicar migraciones. Revise el log:
  echo        "%MIGLOG%"
  exit /b 1
)

echo [INFO] Migraciones aplicadas con éxito. Log:
echo        "%MIGLOG%"
exit /b 0
