@echo off
setlocal ENABLEDELAYEDEXPANSION
set ERROR_FLAG=0

REM ── Ir a la raíz del repo (ruta de este .bat)
cd /d "%~dp0"

REM ── Crear carpeta de logs y archivo
if not exist "logs" mkdir logs
set LOG_FILE=logs\server.log

REM ── Función para mostrar y registrar mensajes
set LOG_TS=
goto :skiplog
:log
for /f %%i in ('powershell -NoProfile -Command "Get-Date -Format \"yyyy-MM-dd HH:mm:ss\""') do set LOG_TS=%%i
echo %~1
echo [%LOG_TS%] %~1>> "%LOG_FILE%"
exit /b
:skiplog

REM ── Verificar venv
if not exist ".\.venv\Scripts\activate.bat" (
  call :log "[WARN] No existe .venv. Cree el entorno primero: python -m venv .venv"
  call :log "        Luego: .\.venv\Scripts\activate.bat && pip install -e ."
  pause
  goto :eof
)

REM ── Activar venv
call ".\.venv\Scripts\activate.bat"

REM ── Verificar .env y variables básicas
if not exist ".env" (
  call :log "[ERROR] Falta .env (copie .env.example a .env y complete DB_URL/IA)."
  pause
  goto :eof
)

for /f "usebackq tokens=1,2 delims==" %%A in (".env") do (
  if /I "%%A"=="DB_URL" set DB_URL=%%B
  if /I "%%A"=="OLLAMA_MODEL" set OLLAMA_MODEL=%%B
)

if "%DB_URL%"=="" (
  call :log "[ERROR] Falta DB_URL en .env"
  pause
  goto :eof
)
if "%OLLAMA_MODEL%"=="" (
  call :log "[WARN] Falta OLLAMA_MODEL en .env"
)

REM ── Detener servicios previos
call stop.bat -q >nul 2>&1

REM ── Iniciar backend si el puerto está libre
netstat -ano | findstr ":8000" >nul
if %errorlevel%==0 (
  call :log "[ERROR] Puerto 8000 ocupado. No se inicia backend."
  set ERROR_FLAG=1
) else (
  call :log "[INFO] Iniciando backend..."
  start "Growen API" cmd /k "powershell -Command \"uvicorn services.api:app --reload 2^>^&1 ^| Tee-Object -FilePath '%LOG_FILE%' -Append\""
  timeout /t 5 /nobreak >nul
  curl --silent --fail http://localhost:8000/docs >nul 2>&1
  if %errorlevel%==0 (
    echo [OK] Backend en línea
    call :log "START backend: OK"
  ) else (
    echo [ERROR] Backend no responde
    call :log "START backend: ERROR"
    set ERROR_FLAG=1
  )
)

REM ── Frontend: instalar deps si faltan
set FRONTEND_DIR=%~dp0frontend
if not exist "%FRONTEND_DIR%\node_modules" (
  call :log "[INFO] Instalando dependencias frontend..."
  pushd "%FRONTEND_DIR%"
  npm install
  popd
)

REM ── Iniciar frontend si el puerto está libre
netstat -ano | findstr ":5173" >nul
if %errorlevel%==0 (
  call :log "[ERROR] Puerto 5173 ocupado. No se inicia frontend."
  set ERROR_FLAG=1
) else (
  call :log "[INFO] Iniciando frontend..."
  start "Growen Frontend" cmd /k "powershell -Command \"Set-Location -Path '%FRONTEND_DIR%'; npm run dev 2^>^&1 ^| Tee-Object -FilePath '%LOG_FILE%' -Append\""
  timeout /t 5 /nobreak >nul
  curl --silent --fail http://localhost:5173/ >nul 2>&1
  if %errorlevel%==0 (
    echo [OK] Frontend en línea
    call :log "START frontend: OK"
  ) else (
    echo [ERROR] Frontend no responde
    call :log "START frontend: ERROR"
    set ERROR_FLAG=1
  )
)

if %ERROR_FLAG%==1 (
  echo.
  echo [INFO] Ocurrieron errores.
)

pause

goto :eof
