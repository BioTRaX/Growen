@echo off
setlocal ENABLEDELAYEDEXPANSION
set ERROR_FLAG=0

REM ── Ir a la raíz del repo (ruta de este .bat)
cd /d "%~dp0"

REM ── Verificar venv
if not exist ".\.venv\Scripts\activate.bat" (
  echo [WARN] No existe .venv. Cree el entorno primero: python -m venv .venv
  echo        Luego: .\.venv\Scripts\activate.bat && pip install -e .
  pause
  goto :eof
)

REM ── Activar venv
call ".\.venv\Scripts\activate.bat"

REM ── Verificar .env y variables básicas
if not exist ".env" (
  echo [ERROR] Falta .env (copie .env.example a .env y complete DB_URL/IA).
  pause
  goto :eof
)

for /f "usebackq tokens=1,2 delims==" %%A in (".env") do (
  if /I "%%A"=="DB_URL" set DB_URL=%%B
  if /I "%%A"=="OLLAMA_MODEL" set OLLAMA_MODEL=%%B
)

if "%DB_URL%"=="" (
  echo [ERROR] Falta DB_URL en .env
  pause
  goto :eof
)
if "%OLLAMA_MODEL%"=="" (
  echo [WARN] Falta OLLAMA_MODEL en .env
)

REM ── Iniciar backend si el puerto está libre
netstat -ano | findstr ":8000" >nul
if %errorlevel%==0 (
  echo [ERROR] Puerto 8000 ocupado. No se inicia backend.
  set ERROR_FLAG=1
) else (
  echo [INFO] Iniciando backend...
  start "Growen API" cmd /k "uvicorn services.api:app --reload"
  timeout /t 5 /nobreak >nul
  curl --silent --fail http://localhost:8000/docs >nul 2>&1
  if %errorlevel%==0 (
    echo [OK] Backend en línea
  ) else (
    echo [ERROR] Backend no responde
    set ERROR_FLAG=1
  )
)

REM ── Frontend: instalar deps si faltan
set FRONTEND_DIR=%~dp0frontend
if not exist "%FRONTEND_DIR%\node_modules" (
  echo [INFO] Instalando dependencias frontend...
  pushd "%FRONTEND_DIR%"
  npm install
  popd
)

REM ── Iniciar frontend si el puerto está libre
netstat -ano | findstr ":5173" >nul
if %errorlevel%==0 (
  echo [ERROR] Puerto 5173 ocupado. No se inicia frontend.
  set ERROR_FLAG=1
) else (
  echo [INFO] Iniciando frontend...
  start "Growen Frontend" cmd /k "cd /d ^"%FRONTEND_DIR%^" && npm run dev"
  timeout /t 5 /nobreak >nul
  curl --silent --fail http://localhost:5173/ >nul 2>&1
  if %errorlevel%==0 (
    echo [OK] Frontend en línea
  ) else (
    echo [ERROR] Frontend no responde
    set ERROR_FLAG=1
  )
)

if %ERROR_FLAG%==1 (
  echo.
  echo [INFO] Ocurrieron errores. Presione una tecla para continuar.
  pause
)
