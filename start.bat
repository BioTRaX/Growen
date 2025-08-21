@echo off
setlocal ENABLEDELAYEDEXPANSION

set ROOT=%~dp0
set SCRIPTS=%ROOT%scripts
set VENV=%ROOT%.venv\Scripts
if not defined LOG_DIR set LOG_DIR=%ROOT%logs

if not exist "%LOG_DIR%" mkdir "%LOG_DIR%"

echo [INFO] Cerrando procesos previos...
if exist "%SCRIPTS%\stop.bat" call "%SCRIPTS%\stop.bat"
timeout /t 5 /nobreak >NUL

echo [INFO] Verificando puertos 8000 y 5173...
for %%P in (8000 5173) do (
  netstat -ano | findstr :%%P >NUL
  if !ERRORLEVEL! EQU 0 (
    echo [ERROR] El puerto %%P esta en uso. Abortando.
    pause
    exit /b 1
  )
)

echo [INFO] Instalando dependencias...
call "%SCRIPTS%\fix_deps.bat"
if !ERRORLEVEL! NEQ 0 (
  echo [ERROR] Fallo la instalacion de dependencias
  pause
  exit /b 1
)

echo [INFO] Ejecutando migraciones...
pushd "%ROOT%"
call "%VENV%\python.exe" -m alembic upgrade head
if !ERRORLEVEL! NEQ 0 (
  echo [ERROR] Fallo al aplicar migraciones
  popd
  pause
  exit /b 1
)
popd

echo [INFO] Iniciando backend...
start "Growen API" cmd /k "\"%VENV%\\python.exe\" -m uvicorn services.api:app --host 127.0.0.1 --port 8000 > \"%LOG_DIR%\\backend.log\" 2>&1"

echo [INFO] Iniciando frontend...
pushd "%ROOT%frontend"
start "Growen Frontend" cmd /k "npm run dev > \"%LOG_DIR%\\frontend.log\" 2>&1"
popd

endlocal
