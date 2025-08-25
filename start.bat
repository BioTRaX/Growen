@echo off
setlocal ENABLEDELAYEDEXPANSION

rem Rutas base del repositorio
set "ROOT=%~dp0"
set "VENV=%ROOT%.venv\Scripts"
if not defined LOG_DIR set "LOG_DIR=%ROOT%logs"
if not exist "%LOG_DIR%" mkdir "%LOG_DIR%"
set "LOG_FILE=%LOG_DIR%\start.log"

rem Validar dependencias externas
where python >NUL 2>&1
if %ERRORLEVEL% NEQ 0 (
  call :log "[ERROR] python no esta instalado"
  pause
  exit /b 1
)
where npm >NUL 2>&1
if %ERRORLEVEL% NEQ 0 (
  call :log "[ERROR] npm no esta instalado"
  pause
  exit /b 1
)

call :log "[INFO] Cerrando procesos previos..."
if exist "%~dp0stop.bat" call "%~dp0stop.bat"
timeout /t 2 /nobreak >NUL

call :log "[INFO] Verificando puertos 8000 y 5173..."
for %%P in (8000 5173) do (
  netstat -ano | findstr :%%P >NUL
  if !ERRORLEVEL! EQU 0 (
    call :log "[ERROR] El puerto %%P esta en uso. Abortando."
    pause
    exit /b 1
  )
)

call :log "[INFO] Instalando dependencias..."
call "%~dp0fix_deps.bat"
if errorlevel 1 (
  call :log "[ERROR] Fallo la instalacion de dependencias"
  exit /b 1
)

call :log "[INFO] Ejecutando migraciones..."
call "%~dp0scripts\run_migrations.cmd"
if errorlevel 1 (
  call :log "[ERROR] No se iniciará el servidor debido a errores de migración."
  goto :eof
)

call :log "[INFO] Iniciando backend..."
start "Growen API" cmd /k "\"%VENV%\python.exe\" -m uvicorn services.api:app --host 127.0.0.1 --port 8000 >> \"%LOG_DIR%\backend.log\" 2>&1"

call :log "[INFO] Iniciando frontend..."
start "Growen Frontend" cmd /k "pushd \"%ROOT%frontend\" && npm run dev >> \"%LOG_DIR%\frontend.log\" 2>&1"

endlocal
exit /b 0

:log
set "ts=!DATE! !TIME!"
>>"%LOG_FILE%" echo [!ts!] %~1
echo [!ts!] %~1
exit /b 0

