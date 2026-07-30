@echo off
REM NG-HEADER: Nombre de archivo: start_worker_enrichment.cmd
REM NG-HEADER: Ubicación: scripts/start_worker_enrichment.cmd
REM NG-HEADER: Descripción: Inicia el worker local dedicado de Enrich v2.
REM NG-HEADER: Lineamientos: Ver AGENTS.md
setlocal
cd /d "%~dp0\.."
if not exist ".venv\Scripts\python.exe" (
  echo No se encontro la venv del proyecto.
  exit /b 1
)
".venv\Scripts\python.exe" -m dramatiq services.jobs.enrichment_jobs --processes 1 --threads 2 --queues enrichment
endlocal
