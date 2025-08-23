@echo off
setlocal ENABLEDELAYEDEXPANSION

set "ROOT=%~dp0.."
set "LOGDIR=%ROOT%\logs\migrations"
if not exist "%LOGDIR%" mkdir "%LOGDIR%"
for /f "tokens=1-2 delims=/ " %%a in ("%date% %time%") do set TS=%%a_%%b
set TS=%TS::=%
set "MIGLOG=%LOGDIR%\alembic_!TS!.log"

"%ROOT%\.venv\Scripts\python.exe" -m alembic -c "%ROOT%\alembic.ini" upgrade head --raiseerr -x log_sql=1 > "%MIGLOG%" 2>&1
if errorlevel 1 (
  echo Error al aplicar migraciones. Ver %MIGLOG%
  exit /b 1
)

echo Migraciones aplicadas con exito. Log: %MIGLOG%
exit /b 0
