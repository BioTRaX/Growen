@echo off
REM NG-HEADER: Nombre de archivo: start_worker_telegram_polling.cmd
REM NG-HEADER: Ubicación: scripts/start_worker_telegram_polling.cmd
REM NG-HEADER: Descripción: Inicia Telegram polling con la venv canónica.
REM NG-HEADER: Lineamientos: Ver AGENTS.md

setlocal
set "ROOT=%~dp0..\"
set "VENV=%ROOT%.venv\Scripts"
set "PYTHONPATH=%ROOT%"

if not exist "%VENV%\python.exe" (
    echo [ERROR] No existe la venv del proyecto.
    exit /b 1
)

cd /d "%ROOT%"
echo [WORKER] Iniciando Telegram Polling desde la venv del proyecto
"%VENV%\python.exe" workers\telegram_polling.py

endlocal
exit /b %ERRORLEVEL%
