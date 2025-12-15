@echo off
setlocal ENABLEDELAYEDEXPANSION

REM Resolve repo root from this script's location
set "ROOT=%~dp0..\"
set "VENV=%ROOT%.venv\Scripts"
set "LOG_DIR=%ROOT%logs"
if not exist "%LOG_DIR%" mkdir "%LOG_DIR%" >NUL 2>&1
set "LOG_FILE=%LOG_DIR%\worker_telegram_polling.log"

REM Verificar que TELEGRAM_BOT_TOKEN esté configurado
if not defined TELEGRAM_BOT_TOKEN (
    echo [ERROR] TELEGRAM_BOT_TOKEN no está configurado. Configurar en .env >> "%LOG_FILE%" 2>&1
    exit /b 1
)

REM Verificar que TELEGRAM_ENABLED esté habilitado
if not defined TELEGRAM_ENABLED set "TELEGRAM_ENABLED=0"
if /i "%TELEGRAM_ENABLED%" neq "1" if /i "%TELEGRAM_ENABLED%" neq "true" if /i "%TELEGRAM_ENABLED%" neq "yes" (
    echo [ERROR] TELEGRAM_ENABLED no está habilitado. Configurar TELEGRAM_ENABLED=1 en .env >> "%LOG_FILE%" 2>&1
    exit /b 1
)

echo [WORKER] Iniciando Telegram Polling Worker >> "%LOG_FILE%" 2>&1
echo [WORKER] Token: %TELEGRAM_BOT_TOKEN:~0,10%... >> "%LOG_FILE%" 2>&1

REM Configurar PYTHONPATH para que Python encuentre los módulos del proyecto
set "PYTHONPATH=%ROOT%"

REM Cambiar al directorio raíz y ejecutar el worker
cd /d "%ROOT%"

REM Use cmd /c to execute Python with proper quoting; keep this window open (caller uses cmd /k)
"%VENV%\python.exe" workers\telegram_polling.py 1>>"%LOG_FILE%" 2>&1

endlocal
exit /b %ERRORLEVEL%

