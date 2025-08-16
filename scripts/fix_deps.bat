@echo off
setlocal ENABLEDELAYEDEXPANSION

REM Raíz del repo (este .bat vive en /scripts)
set ROOT=%~dp0..
set VENV=%ROOT%\.venv

REM --- Python venv + deps backend ---
if not exist "%VENV%\Scripts\python.exe" (
  echo [venv] creando entorno...
  py -3 -m venv "%VENV%"
  if %ERRORLEVEL% NEQ 0 exit /b 1
)

call "%VENV%\Scripts\python.exe" -m pip install --upgrade pip
if %ERRORLEVEL% NEQ 0 exit /b 1

call "%VENV%\Scripts\pip.exe" install -r "%ROOT%\requirements.txt"
if %ERRORLEVEL% NEQ 0 exit /b 1

REM --- Frontend deps ---
pushd "%ROOT%\frontend"
if exist package-lock.json (
  call npm ci --no-audit --no-fund
) else (
  call npm install --no-audit --no-fund
)
if %ERRORLEVEL% NEQ 0 (
  echo [ERROR] Fallo npm install
  popd
  exit /b 1
)

REM asegurar axios y react-router-dom
call npm ls axios >NUL 2>&1
if %ERRORLEVEL% NEQ 0 call npm install --no-audit --no-fund axios

call npm ls react-router-dom >NUL 2>&1
if %ERRORLEVEL% NEQ 0 call npm install --no-audit --no-fund react-router-dom

popd
endlocal
exit /b 0
