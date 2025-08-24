@echo off
setlocal EnableExtensions
chcp 65001 >nul

for %%I in ("%~dp0..") do set "ROOT=%%~fI"
pushd "%ROOT%"

if exist .venv\Scripts\activate.bat call .venv\Scripts\activate.bat

if not exist "%ROOT%\logs\migrations" mkdir "%ROOT%\logs\migrations"

REM Nombre de log sin espacios en hora/fecha
set "_ts=%date:~-4%%date:~3,2%%date:~0,2%_%time:~0,2%%time:~3,2%%time:~6,2%"
set "_ts=%_ts: =0%"
set "LOG=logs\migrations\alembic_%_ts%.log"

echo [INFO] Ejecutando migraciones... > "%LOG%"

REM Si se pasa /sql o -sql, activar echo SQL (equivalente a -x log_sql=1 en Alembic moderno)
set "EXTRA="
if /I "%~1"==/sql set "EXTRA=-x log_sql=1"
if /I "%~1"==-sql set "EXTRA=-x log_sql=1"

alembic upgrade head %EXTRA% >> "%LOG%" 2>&1
if errorlevel 1 (
  echo [ERROR] Fallo al aplicar migraciones. Ver "%LOG%"
  popd
  exit /b 1
) else (
  echo [OK] Migraciones aplicadas. >> "%LOG%"
)

popd
exit /b
