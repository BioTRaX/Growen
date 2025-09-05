@echo off
setlocal ENABLEDELAYEDEXPANSION

rem Rutas base del repositorio
set "ROOT=%~dp0"
set "VENV=%ROOT%.venv\Scripts"
if not defined LOG_DIR set "LOG_DIR=%ROOT%logs"
if not exist "%LOG_DIR%" mkdir "%LOG_DIR%"
set "LOG_FILE=%LOG_DIR%\start.log"

rem Limpiar logs antes de empezar (evitar escribir en start.log para no bloquearlo)
echo [INFO] Limpiando logs previos...
if exist "%ROOT%scripts\clear_logs.py" (
  "%ROOT%.venv\Scripts\python.exe" "%ROOT%scripts\clear_logs.py"
)
if exist "%ROOT%tools\clean_crawl_logs.py" (
  "%ROOT%.venv\Scripts\python.exe" -m tools.clean_crawl_logs
)
call :log "[INFO] Logs previos limpiados."

call :log "[INFO] Cerrando procesos previos..."
if exist "%~dp0stop.bat" call "%~dp0stop.bat"
REM pequeÃ±a espera para evitar condiciones de carrera al liberar puertos
timeout /t 1 /nobreak >NUL

call :log "[INFO] Verificando puertos 8000 y 5175..."
for %%P in (8000 5175) do (
  call :wait_port_free %%P 5
  if errorlevel 1 (
    call :log "[ERROR] El puerto %%P esta en uso. Abortando."
    pause
    exit /b 1
  )
)

rem Asegurar Redis en 6379 (necesario para Dramatiq)
call :log "[INFO] Verificando Redis en 127.0.0.1:6379..."
call :check_redis 127.0.0.1 6379 8
if errorlevel 1 (
  call :log "[WARN] Redis no responde. Intentando iniciar contenedor 'growen-redis'..."
  call :docker_start_redis
  call :check_redis 127.0.0.1 6379 15
  if errorlevel 1 (
  call :log "[ERROR] No se pudo establecer Redis. Activando modo RUN_INLINE_JOBS=1 para desarrollo (sin colas)."
  set "RUN_INLINE_JOBS=1"
  ) else (
    call :log "[INFO] Redis estÃ¡ listo en 6379."
  )
) else (
  call :log "[INFO] Redis estÃ¡ listo en 6379."
)

call :log "[INFO] Instalando/verificando dependencias de Python desde requirements.txt..."
"%ROOT%.venv\Scripts\python.exe" -m pip install -r "%ROOT%requirements.txt" >> "%LOG_FILE%" 2>&1
if errorlevel 1 (
  call :log "[ERROR] FallÃ³ la instalaciÃ³n de dependencias de Python. Revisa %LOG_FILE%."
  pause
  exit /b 1
)

call :log "[INFO] Verificando instalaciÃ³n de Playwright..."
"%ROOT%.venv\Scripts\python.exe" -m playwright install chromium >> "%LOG_FILE%" 2>&1
if errorlevel 1 (
    call :log "[WARN] FallÃ³ la instalaciÃ³n del navegador de Playwright (chromium). El crawler podrÃ­a no funcionar."
)

rem Asegurarse de que frontend tenga node_modules (si no, ejecutar npm install)
if not exist "%ROOT%frontend\node_modules" (
  call :log "[INFO] node_modules no encontrado en frontend; ejecutando npm install..."
  pushd "%ROOT%frontend"
  npm install >> "%LOG_FILE%" 2>&1
  if errorlevel 1 (
    call :log "[ERROR] FallÃ³ 'npm install' en el frontend. Revisa %LOG_FILE%."
    pause
    exit /b 1
  )
  popd
)

call :log "[INFO] Ejecutando migraciones..."
call "%~dp0scripts\run_migrations.cmd"
if errorlevel 1 (
  call :log "[ERROR] No se iniciarÃ¡ el servidor debido a errores de migraciÃ³n."
  goto :eof
)

call :log "[INFO] Iniciando backend..."
rem Activar modo DEBUG para backend y devolver info de debug en import
set "LOG_LEVEL=DEBUG"
set "IMPORT_RETURN_DEBUG=1"
start "Growen API" cmd /k "set LOG_LEVEL=%LOG_LEVEL% && set IMPORT_RETURN_DEBUG=%IMPORT_RETURN_DEBUG% && set PATH=%VENV%;%PATH% && "%VENV%\python.exe" -m uvicorn services.api:app --reload --host 127.0.0.1 --port 8000 --loop asyncio --http h11 --log-level debug >> "%LOG_DIR%\backend.log" 2>&1"

call :log "[INFO] Preparando frontend..."
REM Si existe carpeta dist vacÃ­a o VITE_BUILD=1, ejecutamos build para servir desde FastAPI.
if exist "%ROOT%frontend\package.json" (
  pushd "%ROOT%frontend"
  if "!VITE_BUILD!"=="1" (
    call :log "[INFO] Ejecutando build del frontend (VITE_BUILD=1)..."
    npm run build >> "%LOG_DIR%\frontend.log" 2>&1
  ) else (
    REM Si no hay assets, tambiÃ©n build
    if not exist "%ROOT%frontend\dist\assets" (
      call :log "[INFO] Assets no encontrados; ejecutando build del frontend..."
      npm run build >> "%LOG_DIR%\frontend.log" 2>&1
    ) else (
      call :log "[INFO] Frontend ya compilado (dist/assets presente)."
    )
  )
  popd
)

REM Opcional: si el dev server es preferido, descomentar este bloque.
REM call :log "[INFO] Iniciando frontend en modo dev (5175)..."
REM start "Growen Frontend" cmd /k "pushd ""%ROOT%frontend"" && set VITE_PORT=5175 && npm run dev >> "%LOG_DIR%\frontend.log" 2>&1"

rem Iniciar worker de imÃ¡genes (Dramatiq)
if not defined REDIS_URL set "REDIS_URL=redis://localhost:6379/0"
if "%RUN_INLINE_JOBS%"=="1" (
  call :log "[INFO] RUN_INLINE_JOBS=1: no se inicia worker Dramatiq (los triggers correrÃ¡n inline)."
) else (
  call :log "[INFO] Iniciando worker de imagenes (broker: %REDIS_URL%)..."
  start "Growen Images Worker" cmd /k "set REDIS_URL=%REDIS_URL% && call ""%ROOT%scripts\start_worker_images.cmd"""
)

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

:check_redis
REM Uso: call :check_redis <host> <port> <retries>
setlocal EnableDelayedExpansion
set "_H=%~1"
set "_P=%~2"
set "_T=%~3"
if not defined _T set "_T=10"
set /a _I=0
:_cr_loop
set /a _I+=1
REM Quick TCP probe with 250ms timeout (faster than Test-NetConnection)
set "__OK="
for /f %%R in ('powershell -NoProfile -ExecutionPolicy Bypass -Command "$h='%_H%';$p=%_P%;$c=New-Object System.Net.Sockets.TcpClient;$iar=$c.BeginConnect($h,$p,$null,$null);$ok=$iar.AsyncWaitHandle.WaitOne(250); if($ok -and $c.Connected){$c.Close(); 'OK'} else{$c.Close(); 'FAIL'}"') do set "__OK=%%R"
if /I "!__OK!"=="OK" ( endlocal & exit /b 0 )
if !_I! GEQ %_T% (
  endlocal & exit /b 1
)
timeout /t 0 /nobreak >NUL
goto _cr_loop

:docker_start_redis
setlocal EnableDelayedExpansion
where docker >NUL 2>&1
if errorlevel 1 (
  endlocal & exit /b 1
)
for /f %%N in ('docker ps -a --filter "name=^/growen-redis$" --format "{{.Names}}" 2^>NUL') do set "__REDIS_NAME=%%N"
if not defined __REDIS_NAME (
  call :log "[INFO] Creando contenedor redis:7-alpine..."
  docker run -d --name growen-redis -p 6379:6379 redis:7-alpine >> "%LOG_FILE%" 2>&1
) else (
  call :log "[INFO] Iniciando contenedor existente 'growen-redis'..."
  docker start growen-redis >> "%LOG_FILE%" 2>&1
)
endlocal & exit /b 0

