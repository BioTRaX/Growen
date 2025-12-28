@echo off
REM NG-HEADER: Nombre de archivo: start_worker_catalog.cmd
REM NG-HEADER: Ubicación: scripts/start_worker_catalog.cmd
REM NG-HEADER: Descripción: Script para iniciar el worker de productos canónicos (catalog_jobs)
REM NG-HEADER: Lineamientos: Ver AGENTS.md

cd /d "%~dp0\.."
call .venv\Scripts\activate.bat

echo [%date% %time%] Iniciando Catalog Worker...
python -m dramatiq services.jobs.catalog_jobs --queues catalog --processes 1 --threads 2
