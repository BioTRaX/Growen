@echo off
setlocal ENABLEDELAYEDEXPANSION

REM Script unificado para iniciar workers de Dramatiq
REM Uso: start_worker_all.cmd [images|market|all]
REM Por defecto inicia todos los workers

set "ROOT=%~dp0..\"
set "VENV=%ROOT%.venv\Scripts"
set "LOG_DIR=%ROOT%logs"
if not exist "%LOG_DIR%" mkdir "%LOG_DIR%" >NUL 2>&1

if not defined REDIS_URL set "REDIS_URL=redis://localhost:6379/0"

set "MODE=%~1"
if "%MODE%"=="" set "MODE=all"

echo [WORKER] Starting Dramatiq worker(s) in mode: %MODE%
echo [WORKER] Redis broker: %REDIS_URL%

if /i "%MODE%"=="images" (
    echo [WORKER] Starting images worker only...
    call "%ROOT%scripts\start_worker_images.cmd"
    goto :end
)

if /i "%MODE%"=="market" (
    echo [WORKER] Starting market worker only...
    call "%ROOT%scripts\start_worker_market.cmd"
    goto :end
)

if /i "%MODE%"=="all" (
    echo [WORKER] Starting combined worker (images + market queues)...
    set "LOG_FILE=%LOG_DIR%\worker_all.log"
    
    echo [WORKER] starting Dramatiq worker for all queues (broker: %REDIS_URL%) >> "!LOG_FILE!" 2>&1
    
    REM Iniciar worker multi-queue: procesa tanto 'images' como 'market'
    "%VENV%\python.exe" -m dramatiq services.jobs.images workers.market_scraping --processes 1 --threads 3 --queues images,market 1>>"!LOG_FILE!" 2>&1
    
    goto :end
)

echo [ERROR] Invalid mode: %MODE%
echo [ERROR] Valid modes: images, market, all
exit /b 1

:end
endlocal
exit /b %ERRORLEVEL%
