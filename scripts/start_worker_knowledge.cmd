@echo off
REM NG-HEADER: Nombre de archivo: start_worker_knowledge.cmd
REM NG-HEADER: Ubicación: scripts/start_worker_knowledge.cmd
REM NG-HEADER: Descripción: Inicia el worker local de conocimiento canónico.
REM NG-HEADER: Lineamientos: Ver AGENTS.md
setlocal
cd /d "%~dp0\.."
if not exist ".venv\Scripts\python.exe" (
  echo No se encontro la venv del proyecto.
  exit /b 1
)
".venv\Scripts\python.exe" -m dramatiq services.jobs.knowledge_jobs --processes 1 --threads 1 --queues canonical_knowledge
endlocal
