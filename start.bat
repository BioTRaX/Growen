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
REM pequeña espera para evitar condiciones de carrera al liberar puertos
timeout /t 1 /nobreak >NUL

call :log "[INFO] Verificando puertos 8000 y 5173..."
for %%P in (8000 5173) do (
  call :wait_port_free %%P 5
  if errorlevel 1 (
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
rem Activar modo DEBUG para backend y devolver info de debug en import
set "LOG_LEVEL=DEBUG"
set "IMPORT_RETURN_DEBUG=1"
start "Growen API" cmd /k "set LOG_LEVEL=%LOG_LEVEL% && set IMPORT_RETURN_DEBUG=%IMPORT_RETURN_DEBUG% && "%VENV%\python.exe" -m uvicorn services.api:app --reload --host 127.0.0.1 --port 8000 --loop asyncio --http h11 --log-level debug >> "%LOG_DIR%\backend.log" 2>&1"

call :log "[INFO] Iniciando frontend..."
REM Forzar Vite a usar 5175 en IPv4 para evitar conflictos de permisos/::1
start "Growen Frontend" cmd /k "pushd ""%ROOT%frontend"" && set VITE_PORT=5175 && npm run dev >> "%LOG_DIR%\frontend.log" 2>&1"

endlocal
exit /b 0

:wait_port_free
REM Uso: call :wait_port_free <port> [retries]
setlocal EnableDelayedExpansion
set "_PORT=%~1"
set "_TRIES=%~2"
if not defined _TRIES set "_TRIES=5"
set "_I=0"
:_lp
set /a _I+=1
REM 1) Intentar con PowerShell (exact TCP LISTEN)
set "__COUNT="
for /f %%E in ('powershell -NoProfile -ExecutionPolicy Bypass -Command "@(Get-NetTCPConnection -State Listen -LocalPort %_PORT% -ErrorAction SilentlyContinue).Count"') do set "__COUNT=%%E"
if not defined __COUNT set "__COUNT=0"
if "!__COUNT!"=="0" (
  endlocal & exit /b 0
) else (
  REM Intentar matar propietarios del puerto (PS)
  powershell -NoProfile -ExecutionPolicy Bypass -Command "Get-NetTCPConnection -State Listen -LocalPort %_PORT% -ErrorAction SilentlyContinue | Select-Object -ExpandProperty OwningProcess | Sort-Object -Unique | ForEach-Object { try { Stop-Process -Id $_ -Force -ErrorAction Stop } catch {} }" >NUL 2>&1
  if %_I% GEQ %_TRIES% (
    endlocal & exit /b 1
  )
)

REM 2) Fallback netstat (solo TCP y estado LISTENING/ESCUCHA, puerto exacto)
set "__BUSY=0"
for /f "delims=" %%L in ('netstat -ano -p TCP ^| findstr /R /C:":%_PORT% " ^| findstr /I "LISTENING ESCUCHA"') do set "__BUSY=1"
if "!__BUSY!"=="0" (
  endlocal & exit /b 0
) else (
  REM Matar por netstat si persiste
  for /f "tokens=5" %%I in ('netstat -ano -p TCP ^| findstr /R /C:":%_PORT% " ^| findstr /I "LISTENING ESCUCHA"') do taskkill /PID %%I /F >NUL 2>&1
  if %_I% GEQ %_TRIES% (
    endlocal & exit /b 1
  )
  timeout /t 1 /nobreak >NUL
  goto _lp
)

:log
set "ts=!DATE! !TIME!"
>>"%LOG_FILE%" echo [!ts!] %~1
echo [!ts!] %~1
exit /b 0

