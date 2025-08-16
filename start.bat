@echo off
setlocal ENABLEDELAYEDEXPANSION

set ROOT=%~dp0
set SCRIPTS=%ROOT%scripts
set VENV=%ROOT%.venv\Scripts

REM Cerrar instancias previas
if exist "%SCRIPTS%\stop.bat" call "%SCRIPTS%\stop.bat"
timeout /t 2 /nobreak >NUL

REM Fix deps
call "%SCRIPTS%\fix_deps.bat"
if %ERRORLEVEL% NEQ 0 (
  echo [ERROR] Fallo la instalacion de dependencias
  pause
  exit /b 1
)

REM Migraciones
pushd "%ROOT%"
call "%VENV%\python.exe" -m alembic upgrade head
if %ERRORLEVEL% NEQ 0 (
  echo [ERROR] Fallo al aplicar migraciones
  popd
  pause
  exit /b 1
)
popd

REM Backend
start "Growen API" cmd /k ""%VENV%\python.exe" -m uvicorn services.api:app --host 127.0.0.1 --port 8000"

REM Frontend
pushd "%ROOT%frontend"
start "Growen Frontend" cmd /k "npm run dev"
popd

endlocal
