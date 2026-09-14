@echo off
REM NG-HEADER: Nombre de archivo: start_worker_catalog_audit.cmd
REM NG-HEADER: Ubicación: scripts/start_worker_catalog_audit.cmd
REM NG-HEADER: Descripción: Inicia el worker local exclusivo del auditor de catálogo.
REM NG-HEADER: Lineamientos: Ver AGENTS.md
setlocal
cd /d "%~dp0\.."
if not exist ".venv\Scripts\python.exe" (
  echo No se encontro la venv del proyecto.
  exit /b 1
)
set CATALOG_AUDIT_HEARTBEAT_ENABLED=1
".venv\Scripts\python.exe" -m dramatiq services.jobs.catalog_audit_jobs --processes 1 --threads 1 --queues catalog_audit
endlocal
