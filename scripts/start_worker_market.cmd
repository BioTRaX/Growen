@echo off
setlocal ENABLEDELAYEDEXPANSION

REM Resolve repo root from this script's location
set "ROOT=%~dp0..\"
set "VENV=%ROOT%.venv\Scripts"
set "LOG_DIR=%ROOT%logs"
if not exist "%LOG_DIR%" mkdir "%LOG_DIR%" >NUL 2>&1
set "LOG_FILE=%LOG_DIR%\worker_market.log"

if not defined REDIS_URL set "REDIS_URL=redis://localhost:6379/0"

echo [WORKER] starting Dramatiq market worker (broker: %REDIS_URL%) >> "%LOG_FILE%" 2>&1

REM Use cmd /c to execute Python with proper quoting; keep this window open (caller uses cmd /k)
"%VENV%\python.exe" -m dramatiq workers.market_scraping --processes 1 --threads 2 --queues market 1>>"%LOG_FILE%" 2>&1

endlocal
exit /b %ERRORLEVEL%
