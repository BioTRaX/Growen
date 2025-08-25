@echo off
setlocal EnableExtensions EnableDelayedExpansion
chcp 65001 >nul

REM Detectar raíz del repo (scripts\ está dentro del repo)
for %%I in ("%~dp0..") do set "ROOT=%%~fI"
echo [INFO] ROOT: "%ROOT%"

REM 1) Parar procesos previos
if exist "%ROOT%\scripts\stop.bat" (
  call "%ROOT%\scripts\stop.bat"
  timeout /t 2 /nobreak >nul
)

REM 2) Ejecutar migraciones (con log). Para ver SQL usar: start.bat /sql
set "MIGR_ARG="
if /I "%~1"==/sql set "MIGR_ARG=/sql"
if /I "%~1"==-sql set "MIGR_ARG=/sql"

if exist "%ROOT%\scripts\migrate.bat" (
  call "%ROOT%\scripts\migrate.bat" %MIGR_ARG%
  if errorlevel 1 (
    echo [ERROR] Migraciones fallaron. Abortando arranque.
    exit /b 1
  )
)

REM 3) Lanzar API (Uvicorn) en otra ventana
start "Growen API" cmd /k ^
  "pushd ""%ROOT%"" && ^
   if exist .venv\Scripts\activate.bat (call .venv\Scripts\activate.bat) else (echo [WARN] .venv no encontrado) && ^
   set UVICORN_RELOAD_DELAY=0.25 && ^
   python -m uvicorn services.api:app --reload --host 127.0.0.1 --port 8000 --loop asyncio --http h11"

REM 4) Lanzar Frontend (Vite) en otra ventana
start "Growen Frontend" cmd /k ^
  "pushd ""%ROOT%\frontend"" && ^
   if exist package.json (call npm i --no-fund --loglevel=error) else (echo [ERROR] package.json no encontrado & exit /b 1) && ^
   npm run dev"

exit /b
