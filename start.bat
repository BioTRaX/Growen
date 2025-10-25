@echo off
REM NG-HEADER: Nombre de archivo: start.bat
REM NG-HEADER: Ubicación: start.bat
REM NG-HEADER: Descripción: Orquestador de arranque local con pre/post flight y validaciones Docker/WSL.
REM NG-HEADER: Lineamientos: Ver AGENTS.md
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

REM Política por defecto: requerir DB en Docker saludable; fallback sólo si ALLOW_SQLITE_FALLBACK=1
set "REQUIRE_DOCKER_DB=%REQUIRE_DOCKER_DB%"
if not defined REQUIRE_DOCKER_DB set "REQUIRE_DOCKER_DB=1"
set "ALLOW_SQLITE_FALLBACK=%ALLOW_SQLITE_FALLBACK%"
if not defined ALLOW_SQLITE_FALLBACK set "ALLOW_SQLITE_FALLBACK=0"

REM Redis opcional por defecto (evitar tocar Docker si no hace falta)
set "REQUIRE_REDIS=%REQUIRE_REDIS%"
if not defined REQUIRE_REDIS set "REQUIRE_REDIS=0"

REM Backoff si DB flappea tras PRE-FLIGHT (segundos de espera antes de tocar Docker)
set "DB_FLAP_BACKOFF_SEC=%DB_FLAP_BACKOFF_SEC%"
if not defined DB_FLAP_BACKOFF_SEC set "DB_FLAP_BACKOFF_SEC=10"

REM === PRE-FLIGHT: diagnóstico antes de iniciar ===
call :log "[INFO] ===== PRE-FLIGHT: diagnóstico inicial ====="
call :preflight_ports
call :docker_snapshot "pre"
call :wsl_snapshot
call :db_precheck
call :log "[INFO] ===== FIN PRE-FLIGHT ====="

call :log "[INFO] Cerrando procesos previos..."
if exist "%~dp0stop.bat" call "%~dp0stop.bat"
REM Intento proactivo de matar procesos que ya escuchan en 8000/5175 antes de las comprobaciones
for %%P in (8000 5175) do (
  powershell -NoProfile -ExecutionPolicy Bypass -Command "Get-NetTCPConnection -State Listen -LocalPort %%P -ErrorAction SilentlyContinue | Select-Object -ExpandProperty OwningProcess | Sort-Object -Unique | ForEach-Object { try { Stop-Process -Id $_ -Force -ErrorAction Stop } catch {} }" >NUL 2>&1
)
REM pequeña espera para evitar condiciones de carrera al liberar puertos
timeout /t 1 /nobreak >NUL

set "AGGRESSIVE_PORT_FREE=%AGGRESSIVE_PORT_FREE%"
if not defined AGGRESSIVE_PORT_FREE set "AGGRESSIVE_PORT_FREE=0"
set "ALLOW_PORT_BUSY=%ALLOW_PORT_BUSY%"
if not defined ALLOW_PORT_BUSY set "ALLOW_PORT_BUSY=0"
call :log "[INFO] Verificando puertos 8000 y 5175 (AGGRESSIVE_PORT_FREE=%AGGRESSIVE_PORT_FREE%, ALLOW_PORT_BUSY=%ALLOW_PORT_BUSY%)..."
for %%P in (8000 5175) do (
  if "%AGGRESSIVE_PORT_FREE%"=="1" (
    call :log "[DEBUG] Modo agresivo: intentando liberar puerto %%P (fase pre-chequeo)"
    powershell -NoProfile -ExecutionPolicy Bypass -Command "Get-Process -Id (@(Get-NetTCPConnection -State Listen -LocalPort %%P -ErrorAction SilentlyContinue | Select -ExpandProperty OwningProcess) | Sort -Unique) 2>$null | ForEach-Object { try { Stop-Process -Id $_.Id -Force -ErrorAction Stop } catch {} }" >NUL 2>&1
    timeout /t 1 /nobreak >NUL
  )
  call :wait_port_free %%P 8
  if errorlevel 1 (
    if "%ALLOW_PORT_BUSY%"=="1" (
      call :log "[WARN] Puerto %%P sigue ocupado pero ALLOW_PORT_BUSY=1 (continuando)."
    ) else (
      call :log "[ERROR] El puerto %%P esta en uso tras reintentos. Abortando. (Sugerencia: set AGGRESSIVE_PORT_FREE=1)"
      goto :fatal
    )
  )
)

rem Asegurar Redis en 6379 (necesario para Dramatiq)
call :log "[INFO] Verificando Redis en 127.0.0.1:6379..."
call :check_redis 127.0.0.1 6379 8
if errorlevel 1 (
  if "%REQUIRE_REDIS%"=="1" (
    call :log "[WARN] Redis no responde y REQUIRE_REDIS=1. Intentando iniciar contenedor 'growen-redis'..."
    rem Asegurar que Docker esté estable antes de usar 'docker run'
    call :ensure_docker 60 3
    if errorlevel 1 (
      call :log "[ERROR] Docker no está listo para iniciar Redis. Activando RUN_INLINE_JOBS=1 (sin colas)."
      set "RUN_INLINE_JOBS=1"
    ) else (
      call :docker_start_redis
    )
    call :check_redis 127.0.0.1 6379 15
    if errorlevel 1 (
      call :log "[ERROR] No se pudo establecer Redis. Activando modo RUN_INLINE_JOBS=1 para desarrollo (sin colas)."
      set "RUN_INLINE_JOBS=1"
    ) else (
      call :log "[INFO] Redis está listo en 6379."
    )
    rem Revalidar engine tras operación de Redis (algunos hosts pierden el pipe en este punto)
    call :ensure_docker 20 2
    if errorlevel 1 (
      call :log "[FATAL] Docker Desktop perdió estabilidad tras operar Redis (named pipe/engine). Abortando para evitar corrupción de estado."
      goto :fatal
    )
  ) else (
    call :log "[INFO] REQUIRE_REDIS=0: se usará RUN_INLINE_JOBS=1 si Redis no está disponible; no se iniciará contenedor."
    set "RUN_INLINE_JOBS=1"
  )
) else (
  call :log "[INFO] Redis está listo en 6379."
)

rem Preflight DB: asegurarse que Postgres esté disponible (o activar fallback SQLite)
set "DB_HOST=127.0.0.1"
set "DB_PORT=5433"
set "DB_FALLBACK_SQLITE=sqlite+aiosqlite:///dev.db"
set "_USE_SQLITE=0"
call :log "[INFO] Verificando Postgres en %DB_HOST%:%DB_PORT%..."
call :check_tcp %DB_HOST% %DB_PORT% 25
if errorlevel 1 (
  if "%PRE_DB_OK%"=="1" (
    call :log "[WARN] Postgres estaba OK en PRE-FLIGHT y ahora no responde. Backoff de %DB_FLAP_BACKOFF_SEC%s antes de tocar Docker..."
    call :check_tcp %DB_HOST% %DB_PORT% %DB_FLAP_BACKOFF_SEC%
    if "%ERRORLEVEL%"=="0" (
      call :log "[INFO] Postgres volvió a responder en %DB_HOST%:%DB_PORT% tras backoff. No se tocará Docker."
    ) else (
      call :log "[WARN] Postgres sigue sin responder tras backoff. Intentando iniciar Docker Desktop y contenedor 'db'..."
      call :ensure_docker 120 3
      if errorlevel 1 (
        if "%REQUIRE_DOCKER_DB%"=="1" (
          call :log "[FATAL] Docker no está disponible y REQUIRE_DOCKER_DB=1. Abortando sin fallback a SQLite."
          goto :fatal
        ) else (
          if "%ALLOW_SQLITE_FALLBACK%"=="1" (
            call :log "[ERROR] Docker no está disponible. Se activará modo local con SQLite: %DB_FALLBACK_SQLITE% (ALLOW_SQLITE_FALLBACK=1)"
            set "DB_URL=%DB_FALLBACK_SQLITE%"
            set "_USE_SQLITE=1"
          ) else (
            call :log "[FATAL] Docker no disponible, y ALLOW_SQLITE_FALLBACK=0. Abortando."
            goto :fatal
          )
        )
      ) else (
        call :docker_up_db
        call :pg_ready_via_compose 60
        if errorlevel 1 (
          if "%REQUIRE_DOCKER_DB%"=="1" (
            call :log "[FATAL] Contenedor 'db' no saludable tras timeout y REQUIRE_DOCKER_DB=1. Abortando."
            goto :fatal
          ) else (
            if "%ALLOW_SQLITE_FALLBACK%"=="1" (
              call :log "[ERROR] Postgres en Docker no quedó saludable. Activando fallback SQLite (ALLOW_SQLITE_FALLBACK=1)."
              set "DB_URL=%DB_FALLBACK_SQLITE%"
              set "_USE_SQLITE=1"
            ) else (
              call :log "[FATAL] Postgres en Docker no quedó saludable y ALLOW_SQLITE_FALLBACK=0. Abortando."
              goto :fatal
            )
          )
        ) else (
          call :log "[INFO] Postgres respondió en %DB_HOST%:%DB_PORT% y el contenedor reporta saludable."
        )
      )
    )
  ) else (
    call :log "[WARN] Postgres no responde en %DB_HOST%:%DB_PORT%. Intentando iniciar Docker Desktop y contenedor 'db'..."
    call :ensure_docker 120 3
    if errorlevel 1 (
      if "%REQUIRE_DOCKER_DB%"=="1" (
        call :log "[FATAL] Docker no está disponible y REQUIRE_DOCKER_DB=1. Abortando sin fallback a SQLite."
        goto :fatal
      ) else (
        if "%ALLOW_SQLITE_FALLBACK%"=="1" (
          call :log "[ERROR] Docker no está disponible. Se activará modo local con SQLite: %DB_FALLBACK_SQLITE% (ALLOW_SQLITE_FALLBACK=1)"
          set "DB_URL=%DB_FALLBACK_SQLITE%"
          set "_USE_SQLITE=1"
        ) else (
          call :log "[FATAL] Docker no disponible, y ALLOW_SQLITE_FALLBACK=0. Abortando."
          goto :fatal
        )
      )
    ) else (
      call :docker_up_db
      call :pg_ready_via_compose 60
      if errorlevel 1 (
        if "%REQUIRE_DOCKER_DB%"=="1" (
          call :log "[FATAL] Contenedor 'db' no saludable tras timeout y REQUIRE_DOCKER_DB=1. Abortando."
          goto :fatal
        ) else (
          if "%ALLOW_SQLITE_FALLBACK%"=="1" (
            call :log "[ERROR] Postgres en Docker no quedó saludable. Activando fallback SQLite (ALLOW_SQLITE_FALLBACK=1)."
            set "DB_URL=%DB_FALLBACK_SQLITE%"
            set "_USE_SQLITE=1"
          ) else (
            call :log "[FATAL] Postgres en Docker no quedó saludable y ALLOW_SQLITE_FALLBACK=0. Abortando."
            goto :fatal
          )
        )
      ) else (
        call :log "[INFO] Postgres respondió en %DB_HOST%:%DB_PORT% y el contenedor reporta saludable."
      )
    )
  )
) else (
  call :log "[INFO] Postgres está listo en %DB_HOST%:%DB_PORT%."
)

call :log "[INFO] Verificando instalación de Playwright..."
"%ROOT%.venv\Scripts\python.exe" -m playwright install chromium >> "%LOG_FILE%" 2>&1
if errorlevel 1 (
  call :log "[WARN] Falló la instalación del navegador de Playwright (chromium). El crawler podría no funcionar."
)

rem Asegurarse de que frontend tenga node_modules (si no, ejecutar npm install)
if not exist "%ROOT%frontend\node_modules" (
  call :log "[INFO] node_modules no encontrado en frontend; ejecutando npm install..."
  pushd "%ROOT%frontend"
  npm install >> "%LOG_FILE%" 2>&1
  if errorlevel 1 (
    call :log "[ERROR] Falló 'npm install' en el frontend. Revisa %LOG_FILE%."
    popd
    goto :fatal
  )
  popd
)
if "%_USE_SQLITE%"=="1" (
  call :log "[INFO] Modo SQLite DEV activado: se omiten migraciones Alembic (solo desarrollo)."
) else (
  call :log "[INFO] Ejecutando migraciones..."
  call "%~dp0scripts\run_migrations.cmd"
  if errorlevel 1 (
    call :log "[ERROR] No se iniciará el servidor debido a errores de migración."
    goto :eof
  )
)

call :log "[INFO] Iniciando backend..."
rem Activar modo DEBUG para backend y devolver info de debug en import
set "LOG_LEVEL=DEBUG"

start "Growen API" cmd /k set LOG_LEVEL=%LOG_LEVEL% ^&^& set IMPORT_RETURN_DEBUG=%IMPORT_RETURN_DEBUG% ^&^& set PATH=%VENV%;%PATH% ^&^& echo [BOOT] Lanzando uvicorn en puerto 8000 ^&^& "%VENV%\python.exe" -m uvicorn services.api:app --reload --host 127.0.0.1 --port 8000 --loop asyncio --http h11 --log-level debug ^>> "%LOG_DIR%\backend.log" 2^>^&1

call :log "[INFO] Preparando frontend..."
REM Si existe carpeta dist vacía o VITE_BUILD=1, ejecutamos build para servir desde FastAPI.
if exist "%ROOT%frontend\package.json" (
  pushd "%ROOT%frontend"
  if "!VITE_BUILD!"=="1" (
    call :log "[INFO] Ejecutando build del frontend (VITE_BUILD=1)..."
        set /a __OKS=0
    npm run build >> "%LOG_DIR%\frontend.log" 2>&1
  ) else (
  REM Si no hay assets, también build
    if not exist "%ROOT%frontend\dist\assets" (
      call :log "[INFO] Assets no encontrados; ejecutando build del frontend..."
        set /a __OKS=0
      npm run build >> "%LOG_DIR%\frontend.log" 2>&1
    ) else (
      call :log "[INFO] Frontend ya compilado (dist/assets presente)."
    )
  )
  popd
)

:wait_port_free
REM Uso: call :wait_port_free <port> [retries]
setlocal EnableDelayedExpansion
set "_PORT=%~1"
set "_TRIES=%~2"
if not defined _TRIES set "_TRIES=5"
set "_I=0"
:_lp
set /a _I+=1
REM 1) Intento con PowerShell (exact TCP LISTEN)
set "__COUNT="
for /f %%E in ('powershell -NoProfile -ExecutionPolicy Bypass -Command "@(Get-NetTCPConnection -State Listen -LocalPort %_PORT% -ErrorAction SilentlyContinue).Count"') do set "__COUNT=%%E"
if not defined __COUNT set "__COUNT=0"
if "!__COUNT!"=="0" (
  endlocal & exit /b 0
) else (
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
  for /f "tokens=5" %%I in ('netstat -ano -p TCP ^| findstr /R /C:":%_PORT% " ^| findstr /I "LISTENING ESCUCHA"') do (
    taskkill /PID %%I /F >NUL 2>&1
  )
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

:fatal
REM Snapshot de estado de Docker y WSL al fallar
call :docker_snapshot "fatal"
call :wsl_snapshot
call :npipe_diag
call :log "[FATAL] Arranque abortado por política de entorno. Revisa mensajes previos en este log para la causa (Docker/DB)."
exit /b 1

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
:ensure_docker
REM Uso: call :ensure_docker [timeout_sec] [stable_checks]
setlocal EnableDelayedExpansion
set "_TO=%~1"
if not defined _TO set "_TO=90"
set "_STABLE=%~2"
if not defined _STABLE set "_STABLE=2"

where docker >NUL 2>&1
if errorlevel 1 (
  call :log "[WARN] Docker CLI no encontrado en PATH. Intentando iniciar Docker Desktop..."
)
for /f "delims=" %%E in ('powershell -NoProfile -ExecutionPolicy Bypass -Command "$p=Get-Process -Name 'Docker Desktop' -ErrorAction SilentlyContinue; if($p){'RUNNING'} else {'STOP'}"') do set "__DSTATE=%%E"
if /I "!__DSTATE!"=="STOP" (
  call :log "[INFO] Iniciando Docker Desktop..."
  powershell -NoProfile -ExecutionPolicy Bypass -Command "$exe=Join-Path $env:ProgramFiles 'Docker\Docker\Docker Desktop.exe'; if(Test-Path $exe){ Start-Process -FilePath $exe } else { exit 2 }" >NUL 2>&1
)
set /a _ELAP=0
set /a __OKS=0
set "__NPIPE_WARNED=0"
:_wait_docker
for /f "tokens=*" %%L in ('docker info 2^>^&1') do set "__DINFO=%%L"
if "%ERRORLEVEL%"=="0" (
  set /a __OKS+=1
  if !__OKS! GEQ %_STABLE% (
    endlocal & exit /b 0
  ) else (
    timeout /t 1 /nobreak >NUL
    set /a _ELAP+=1
    goto _wait_docker
  )
) else (
  set /a __OKS=0
  echo !__DINFO! | findstr /I /C:"dockerDesktopLinuxEngine" /C:"The system cannot find the file specified" >NUL
  if !ERRORLEVEL! EQU 0 (
    if "!__NPIPE_WARNED!"=="0" (
      call :log "[WARN] Docker Desktop named pipe no disponible (posible GUI/WSL en transición). Mensaje: !__DINFO!"
      set "__NPIPE_WARNED=1"
    )
    set "DOCKER_NPIPE_BROKEN=1"
  ) else (
    if !__NPIPE_WARNED! EQU 0 (
      call :log "[DEBUG] Esperando a Docker Desktop (el engine aún no responde)."
      set "__NPIPE_WARNED=1"
    )
  )
  if %_ELAP% GEQ %_TO% (
    endlocal & exit /b 1
  )
  timeout /t 2 /nobreak >NUL
  set /a _ELAP+=2
  goto _wait_docker
)
)
endlocal & exit /b 0

:preflight_ports
setlocal EnableDelayedExpansion
call :log "[INFO] Preflight Puertos: objetivo API 8000, Frontend 5175, DB 5433, Redis 6379"
for %%P in (8000 5175) do (
  set "__BUSY=0"
  for /f "delims=" %%L in ('netstat -ano -p TCP ^| findstr /R /C:":%%P " ^| findstr /I "LISTENING ESCUCHA"') do set "__BUSY=1"
  if "!__BUSY!"=="1" (
    call :log "[WARN] Puerto %%P actualmente en uso (LISTENING)."
  ) else (
    call :log "[INFO] Puerto %%P libre."
  )
)
call :check_tcp 127.0.0.1 5433 1
if "%ERRORLEVEL%"=="0" ( call :log "[INFO] DB 5433 responde (TCP)." ) else ( call :log "[INFO] DB 5433 no responde (TCP)." )
call :check_tcp 127.0.0.1 6379 1
if "%ERRORLEVEL%"=="0" ( call :log "[INFO] Redis 6379 responde (TCP)." ) else ( call :log "[INFO] Redis 6379 no responde (TCP)." )
endlocal & exit /b 0

:docker_snapshot
setlocal EnableDelayedExpansion
set "_TAG=%~1"
where docker >NUL 2>&1
if errorlevel 1 (
  call :log "[WARN] Docker CLI no disponible. Snapshot '%_TAG%' omitido."
  endlocal & exit /b 0
)
call :log "[INFO] Docker snapshot (%_TAG%): docker info"
docker info >> "%LOG_FILE%" 2>&1
call :log "[INFO] Docker snapshot (%_TAG%): docker ps"
docker ps --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}" >> "%LOG_FILE%" 2>&1
endlocal & exit /b 0

:wsl_snapshot
setlocal EnableDelayedExpansion
call :log "[INFO] WSL snapshot: wsl --status"
wsl --status >> "%LOG_FILE%" 2>&1
call :log "[INFO] WSL snapshot: wsl -l -v"
wsl -l -v >> "%LOG_FILE%" 2>&1
endlocal & exit /b 0

:db_precheck
setlocal EnableDelayedExpansion
set "_PRE_DB_OK=0"
call :log "[INFO] Preflight DB: probando 127.0.0.1:5433 y (si aplica) pg_isready en 'db'"
call :check_tcp 127.0.0.1 5433 1
if "%ERRORLEVEL%"=="0" (
  set "_PRE_DB_OK=1"
  call :log "[INFO] Preflight DB: puerto 5433 responde (TCP)."
) else (
  call :log "[INFO] Preflight DB: puerto 5433 no responde (TCP)."
)
where docker >NUL 2>&1
if "%ERRORLEVEL%"=="0" (
  docker compose exec -T db pg_isready -U postgres >> "%LOG_FILE%" 2>&1
) else (
  call :log "[INFO] Preflight DB: docker CLI no disponible; omitido pg_isready."
)
endlocal & set "PRE_DB_OK=%_PRE_DB_OK%" & exit /b 0

:check_tcp
REM Uso: call :check_tcp <host> <port> [retries]
setlocal EnableDelayedExpansion
set "_H=%~1"
set "_P=%~2"
set "_T=%~3"
if not defined _T set "_T=20"
set /a _I=0
:_ct_loop
set /a _I+=1
set "__OK="
for /f %%R in ('powershell -NoProfile -ExecutionPolicy Bypass -Command "$h='%_H%';$p=%_P%;$c=New-Object System.Net.Sockets.TcpClient;$iar=$c.BeginConnect($h,$p,$null,$null);$ok=$iar.AsyncWaitHandle.WaitOne(500); if($ok -and $c.Connected){$c.Close(); 'OK'} else{$c.Close(); 'FAIL'}"') do set "__OK=%%R"
if /I "!__OK!"=="OK" ( endlocal & exit /b 0 )
if !_I! GEQ %_T% (
  endlocal & exit /b 1
)
timeout /t 1 /nobreak >NUL
goto _ct_loop

:ensure_docker
REM Uso: call :ensure_docker [timeout_sec]
setlocal EnableDelayedExpansion
set "_TO=%~1"
if not defined _TO set "_TO=90"
where docker >NUL 2>&1
if errorlevel 1 (
  call :log "[WARN] Docker CLI no encontrado en PATH. Intentando iniciar Docker Desktop..."
)
for /f "delims=" %%E in ('powershell -NoProfile -ExecutionPolicy Bypass -Command "$p=Get-Process -Name 'Docker Desktop' -ErrorAction SilentlyContinue; if($p){'RUNNING'} else {'STOP'}"') do set "__DSTATE=%%E"
if /I "!__DSTATE!"=="STOP" (
  call :log "[INFO] Iniciando Docker Desktop..."
  powershell -NoProfile -ExecutionPolicy Bypass -Command "$exe=Join-Path $env:ProgramFiles 'Docker\\Docker\\Docker Desktop.exe'; if(Test-Path $exe){ Start-Process -FilePath $exe } else { exit 2 }" >NUL 2>&1
)
set /a _ELAP=0
set "__NPIPE_WARNED=0"
:_wait_docker
for /f "tokens=*" %%L in ('docker info 2^>^&1') do set "__DINFO=%%L"
if "%ERRORLEVEL%"=="0" (
  endlocal & exit /b 0
) else (
  echo !__DINFO! | findstr /I /C:"dockerDesktopLinuxEngine" /C:"The system cannot find the file specified" >NUL
  if !ERRORLEVEL! EQU 0 (
    if "!__NPIPE_WARNED!"=="0" (
      call :log "[WARN] Docker Desktop named pipe no disponible (posible GUI/WSL en transición). Mensaje: !__DINFO!"
      set "__NPIPE_WARNED=1"
    )
    set "DOCKER_NPIPE_BROKEN=1"
  ) else (
    if !__NPIPE_WARNED! EQU 0 (
      call :log "[DEBUG] Esperando a Docker Desktop (el engine aún no responde)."
      set "__NPIPE_WARNED=1"
    )
  )
  if %_ELAP% GEQ %_TO% (
    endlocal & exit /b 1
  )
  timeout /t 2 /nobreak >NUL
  set /a _ELAP+=2
  goto _wait_docker
)

:docker_up_db
setlocal EnableDelayedExpansion
where docker >NUL 2>&1
if errorlevel 1 ( endlocal & exit /b 1 )
call :log "[INFO] Levantando contenedor de base de datos (docker compose up -d db)..."
docker compose up -d db >> "%LOG_FILE%" 2>&1
endlocal & exit /b 0

:restart_docker_gui
REM Reinicia solo la GUI de Docker Desktop (no toca el servicio/engine)
setlocal EnableDelayedExpansion
for /f "delims=" %%E in ('powershell -NoProfile -ExecutionPolicy Bypass -Command "$p=Get-Process -Name 'Docker Desktop' -ErrorAction SilentlyContinue; if($p){'RUNNING'} else {'STOP'}"') do set "__DSTATE=%%E"
if /I "!__DSTATE!"=="RUNNING" (
  call :log "[INFO] Reiniciando GUI de Docker Desktop (sin tocar contenedores)..."
  powershell -NoProfile -ExecutionPolicy Bypass -Command "Get-Process -Name 'Docker Desktop' -ErrorAction SilentlyContinue | Stop-Process -Force -ErrorAction SilentlyContinue" >NUL 2>&1
  timeout /t 1 /nobreak >NUL
)
powershell -NoProfile -ExecutionPolicy Bypass -Command "$exe=Join-Path $env:ProgramFiles 'Docker\Docker\Docker Desktop.exe'; if(Test-Path $exe){ Start-Process -FilePath $exe }" >NUL 2>&1
call :log "[INFO] GUI de Docker Desktop lanzada."
endlocal & exit /b 0

:npipe_diag
setlocal EnableDelayedExpansion
for /f %%S in ('powershell -NoProfile -ExecutionPolicy Bypass -Command "$p='\\\\.\\pipe\\dockerDesktopLinuxEngine'; if(Test-Path $p){'OK'} else {'MISSING'}"') do set "__NPIPE=%%S"
if /I "!__NPIPE!"=="OK" (
  call :log "[INFO] NPIPE dockerDesktopLinuxEngine: OK"
) else (
  call :log "[INFO] NPIPE dockerDesktopLinuxEngine: MISSING"
)
endlocal & exit /b 0

