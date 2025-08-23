@echo off
setlocal ENABLEDELAYEDEXPANSION

rem Raiz del repo (este .bat vive en /scripts)
set "ROOT=%~dp0.."
set "VENV=%ROOT%\.venv"
if not defined LOG_DIR set "LOG_DIR=%ROOT%\logs"
if not exist "%LOG_DIR%" mkdir "%LOG_DIR%"
set "LOG_FILE=%LOG_DIR%\fix_deps.log"

rem Validar dependencias externas
where python >NUL 2>&1
if %ERRORLEVEL% NEQ 0 (
  call :log "[ERROR] python no esta instalado"
  exit /b 1
)
where npm >NUL 2>&1
if %ERRORLEVEL% NEQ 0 (
  call :log "[ERROR] npm no esta instalado"
  exit /b 1
)

rem --- Python venv + deps backend ---
if not exist "%VENV%\Scripts\python.exe" (
  call :log "[INFO] Creando entorno virtual..."
  python -m venv "%VENV%"
  if %ERRORLEVEL% NEQ 0 exit /b 1
)

call :log "[INFO] Actualizando pip..."
call "%VENV%\Scripts\python.exe" -m pip install --upgrade pip >> "%LOG_FILE%" 2>&1
if %ERRORLEVEL% NEQ 0 exit /b 1

call :log "[INFO] Instalando dependencias backend..."
call "%VENV%\Scripts\pip.exe" install -r "%ROOT%\requirements.txt" >> "%LOG_FILE%" 2>&1
if %ERRORLEVEL% NEQ 0 exit /b 1

rem --- Frontend deps ---
call :log "[INFO] Instalando dependencias frontend..."
pushd "%ROOT%\frontend"
if exist package-lock.json (
  npm ci --no-audit --no-fund >> "%LOG_FILE%" 2>&1
) else (
  npm install --no-audit --no-fund >> "%LOG_FILE%" 2>&1
)
if %ERRORLEVEL% NEQ 0 (
  call :log "[ERROR] Fallo npm install"
  popd
  exit /b 1
)

REM asegurar axios y react-router-dom
call npm ls axios >NUL 2>&1
if %ERRORLEVEL% NEQ 0 npm install --no-audit --no-fund axios >> "%LOG_FILE%" 2>&1

call npm ls react-router-dom >NUL 2>&1
if %ERRORLEVEL% NEQ 0 npm install --no-audit --no-fund react-router-dom >> "%LOG_FILE%" 2>&1

popd

call :log "[INFO] Dependencias listas"

endlocal
exit /b 0

:log
set "ts=!DATE! !TIME!"
>>"%LOG_FILE%" echo [!ts!] %~1
echo [!ts!] %~1
exit /b 0

