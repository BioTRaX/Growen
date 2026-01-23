@echo off
REM NG-HEADER: Nombre de archivo: start_worker_drive_sync.cmd
REM NG-HEADER: Ubicación: scripts/start_worker_drive_sync.cmd
REM NG-HEADER: Descripción: Script para iniciar el worker de Drive Sync con hot-reload (watchmedo)
REM NG-HEADER: Lineamientos: Ver AGENTS.md

setlocal ENABLEDELAYEDEXPANSION

REM Resolve repo root from this script's location
set "ROOT=%~dp0..\"
set "VENV=%ROOT%.venv\Scripts"
set "LOG_DIR=%ROOT%logs"
if not exist "%LOG_DIR%" mkdir "%LOG_DIR%" >NUL 2>&1
set "LOG_FILE=%LOG_DIR%\worker_drive_sync.log"

if not defined REDIS_URL set "REDIS_URL=redis://localhost:6379/0"

echo [WORKER] starting Dramatiq drive_sync worker with hot-reload (broker: %REDIS_URL%)
echo [WORKER] starting Dramatiq drive_sync worker with hot-reload (broker: %REDIS_URL%) >> "%LOG_FILE%" 2>&1

REM Cambiar al directorio raíz
cd /d "%ROOT%"

REM Ejecutar con watchmedo para hot-reload automático
echo [HOT-RELOAD] Monitoreando cambios en workers/, services/
"%VENV%\watchmedo.exe" auto-restart --directory=./workers --directory=./services --pattern=*.py --recursive -- "%VENV%\python.exe" -m dramatiq services.jobs.drive_sync --processes 1 --threads 1 --queues drive_sync

endlocal
exit /b %ERRORLEVEL%
