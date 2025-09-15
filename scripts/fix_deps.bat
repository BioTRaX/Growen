@echo off
setlocal ENABLEDELAYEDEXPANSION

REM NG-HEADER: Nombre de archivo: fix_deps.bat
REM NG-HEADER: Ubicación: scripts/fix_deps.bat
REM NG-HEADER: Descripción: Prepara entorno (venv + deps backend/frontend) con fallbacks para py launcher
REM NG-HEADER: Lineamientos: Ver AGENTS.md

rem Raiz del repo (este .bat vive en /scripts)
set "ROOT=%~dp0.."
set "VENV=%ROOT%\.venv"
if not defined LOG_DIR set "LOG_DIR=%ROOT%\logs"
if not exist "%LOG_DIR%" mkdir "%LOG_DIR%"
set "LOG_FILE=%LOG_DIR%\fix_deps.log"

call :log "[INFO] Inicio fix_deps.bat"

rem Resolver comando Python (algunos Windows solo tienen 'py')
set "PY_CMD="
where python >NUL 2>&1 && set "PY_CMD=python"
if not defined PY_CMD (
  where py >NUL 2>&1 && set "PY_CMD=py -3.11"
)
if not defined PY_CMD (
  where py >NUL 2>&1 && set "PY_CMD=py -3.12"
)
if not defined PY_CMD (
  call :log "[ERROR] No se encontró Python en PATH ni el launcher 'py'. Instala Python 3.11 y reintenta."
  call :log "[HINT] Descarga: https://www.python.org/downloads/windows/ (marcar 'Add to PATH')."
  exit /b 1
)
call :log "[DEBUG] PY_CMD=%PY_CMD%"

rem Validar npm
where npm >NUL 2>&1
if %ERRORLEVEL% NEQ 0 (
  call :log "[ERROR] npm no está instalado (instala Node.js LTS)."
  exit /b 1
)

rem --- Python venv + deps backend ---
if not exist "%VENV%\Scripts\python.exe" (
  call :log "[INFO] Creando entorno virtual (%VENV%)..."
  %PY_CMD% -m venv "%VENV%"
  if %ERRORLEVEL% NEQ 0 (
    call :log "[ERROR] Falló creación de venv. Verifica Python 3.11 instalado."
    exit /b 1
  )
) else (
  call :log "[INFO] venv existente detectado"
)

call :log "[INFO] Actualizando pip..."
call "%VENV%\Scripts\python.exe" -m pip install --upgrade pip setuptools wheel >> "%LOG_FILE%" 2>&1
if %ERRORLEVEL% NEQ 0 (
  call :log "[ERROR] Falló actualización de pip"
  exit /b 1
)

call :log "[INFO] Instalando dependencias backend (requirements.txt)..."
call "%VENV%\Scripts\python.exe" -m pip install -r "%ROOT%\requirements.txt" >> "%LOG_FILE%" 2>&1
if %ERRORLEVEL% NEQ 0 (
  call :log "[ERROR] Falló instalación backend. Revisar %LOG_FILE%"
  exit /b 1
)

rem --- Frontend deps ---
call :log "[INFO] Instalando dependencias frontend..."
pushd "%ROOT%\frontend" >NUL
if exist package-lock.json (
  npm ci --no-audit --no-fund >> "%LOG_FILE%" 2>&1
) else (
  npm install --no-audit --no-fund >> "%LOG_FILE%" 2>&1
)
if %ERRORLEVEL% NEQ 0 (
  call :log "[ERROR] Falló npm install"
  popd
  exit /b 1
)

REM asegurar axios y react-router-dom (evitar fallos en entornos limpios)
call npm ls axios >NUL 2>&1
if %ERRORLEVEL% NEQ 0 npm install --no-audit --no-fund axios >> "%LOG_FILE%" 2>&1

call npm ls react-router-dom >NUL 2>&1
if %ERRORLEVEL% NEQ 0 npm install --no-audit --no-fund react-router-dom >> "%LOG_FILE%" 2>&1

popd >NUL

call :log "[INFO] Dependencias listas"

endlocal
exit /b 0

:log
set "ts=!DATE! !TIME!"
>>"%LOG_FILE%" echo [!ts!] %~1
echo [!ts!] %~1
exit /b 0

