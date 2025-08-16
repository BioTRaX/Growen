@echo off
setlocal enableextensions enabledelayedexpansion

REM Cambiar al directorio del repo (este .bat)
cd /d "%~dp0"

REM 1) Intentar detener procesos previos
if exist "stop.bat" (
  call "stop.bat"
)

REM 2) Esperar 3 segundos para liberar puertos
timeout /t 3 /nobreak >nul

REM 3) Fijar venv si aplica
if exist ".venv\Scripts\activate.bat" (
  call ".venv\Scripts\activate.bat"
)

REM 4) Opcional: fix_deps.bat
if exist "fix_deps.bat" (
  call "fix_deps.bat"
)

alembic -c alembic.ini upgrade head

REM 5) Lanzar API y Front en ventanas separadas
start "Growen API" cmd /c "scripts\run_api.cmd"
start "Growen Frontend" cmd /c "scripts\run_frontend.cmd"

endlocal
