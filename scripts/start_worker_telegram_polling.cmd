@echo off
REM NG-HEADER: Nombre de archivo: start_worker_telegram_polling.cmd
REM NG-HEADER: Ubicación: scripts/start_worker_telegram_polling.cmd
REM NG-HEADER: Descripción: Script para iniciar el worker de Telegram con hot-reload (watchmedo)
REM NG-HEADER: Lineamientos: Ver AGENTS.md

setlocal ENABLEDELAYEDEXPANSION

REM Resolve repo root from this script's location
set "ROOT=%~dp0..\"
set "VENV=%ROOT%.venv\Scripts"
set "LOG_DIR=%ROOT%logs"
if not exist "%LOG_DIR%" mkdir "%LOG_DIR%" >NUL 2>&1
set "LOG_FILE=%LOG_DIR%\worker_telegram_polling.log"

REM Verificar que TELEGRAM_BOT_TOKEN esté configurado
if not defined TELEGRAM_BOT_TOKEN (
    echo [ERROR] TELEGRAM_BOT_TOKEN no está configurado. Configurar en .env
    echo [ERROR] TELEGRAM_BOT_TOKEN no está configurado. Configurar en .env >> "%LOG_FILE%" 2>&1
    exit /b 1
)

REM Verificar que TELEGRAM_ENABLED esté habilitado
if not defined TELEGRAM_ENABLED set "TELEGRAM_ENABLED=0"
if /i "%TELEGRAM_ENABLED%" neq "1" if /i "%TELEGRAM_ENABLED%" neq "true" if /i "%TELEGRAM_ENABLED%" neq "yes" (
    echo [ERROR] TELEGRAM_ENABLED no está habilitado. Configurar TELEGRAM_ENABLED=1 en .env
    echo [ERROR] TELEGRAM_ENABLED no está habilitado. Configurar TELEGRAM_ENABLED=1 en .env >> "%LOG_FILE%" 2>&1
    exit /b 1
)

echo [WORKER] Iniciando Telegram Polling Worker con hot-reload
echo [WORKER] Token: %TELEGRAM_BOT_TOKEN:~0,10%...
echo [WORKER] Iniciando Telegram Polling Worker con hot-reload >> "%LOG_FILE%" 2>&1

REM Configurar PYTHONPATH para que Python encuentre los módulos del proyecto
set "PYTHONPATH=%ROOT%"

REM Cambiar al directorio raíz
cd /d "%ROOT%"

REM Ejecutar con watchmedo para hot-reload automático
echo [HOT-RELOAD] Monitoreando cambios en workers/, services/, ai/
"%VENV%\watchmedo.exe" auto-restart --directory=./workers --directory=./services --directory=./ai --pattern=*.py --recursive -- "%VENV%\python.exe" workers\telegram_polling.py

endlocal
exit /b %ERRORLEVEL%
