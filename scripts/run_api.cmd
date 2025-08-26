@echo off
setlocal ENABLEDELAYEDEXPANSION

rem Rutas base del repositorio
cd /d "%~dp0\.."
set "ROOT=%CD%"
set "SCRIPTS=%ROOT%\scripts"
set "VENV=%ROOT%\.venv\Scripts"
if not defined LOG_DIR set "LOG_DIR=%ROOT%\logs"
if not exist "%LOG_DIR%" mkdir "%LOG_DIR%"
set "LOG_FILE=%LOG_DIR%\run_api.log"

call :log "[DEBUG] ROOT=%ROOT%"
call :log "[DEBUG] VENV=%VENV%"
call :log "[DEBUG] LOG_DIR=%LOG_DIR%"

call :log "[INFO] Cerrando procesos previos..."
if exist "%SCRIPTS%\stop.bat" (
  call "%SCRIPTS%\stop.bat"
  call :log "[DEBUG] ERRORLEVEL=!ERRORLEVEL!"
)
timeout /t 5 /nobreak >NUL

call :log "[INFO] Verificando puerto 8000..."
netstat -ano | findstr :8000 >NUL
set "_PORTCHK=!ERRORLEVEL!"
call :log "[DEBUG] FINDSTR ERRORLEVEL=!_PORTCHK!"
if !_PORTCHK! EQU 0 (
  call :log "[ERROR] El puerto 8000 esta en uso. Abortando."
  pause
  exit /b 1
)

call :log "[INFO] Instalando dependencias..."
call "%SCRIPTS%\fix_deps.bat"
call :log "[DEBUG] ERRORLEVEL=!ERRORLEVEL!"
if !ERRORLEVEL! NEQ 0 (
  call :log "[ERROR] Fallo la instalacion de dependencias"
  pause
  exit /b 1
)

call :log "[INFO] Ejecutando migraciones..."
pushd "%ROOT%"
call "%VENV%\python.exe" -m alembic upgrade head >> "%LOG_FILE%" 2>&1
call :log "[DEBUG] ERRORLEVEL=!ERRORLEVEL!"
if !ERRORLEVEL! NEQ 0 (
  call :log "[ERROR] Fallo al aplicar migraciones"
  popd
  pause
  exit /b 1
)
popd

call :log "[INFO] Iniciando backend..."
start "Growen API" cmd /k ""%VENV%\python.exe" -m services.runserver >> "%LOG_DIR%\backend.log" 2>&1"
call :log "[DEBUG] ERRORLEVEL=!ERRORLEVEL!"

endlocal
exit /b 0

:log
set "ts=!DATE! !TIME!"
>>"%LOG_FILE%" echo [!ts!] %~1
echo [!ts!] %~1
exit /b 0
