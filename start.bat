@echo off
setlocal
cd /d "%~dp0"

REM (Opcional) matar procesos viejos en 8000 y 5173
for /f "tokens=5" %%a in ('netstat -ano ^| findstr ":8000"') do taskkill /PID %%a /F >NUL 2>&1
for /f "tokens=5" %%a in ('netstat -ano ^| findstr ":5173"') do taskkill /PID %%a /F >NUL 2>&1

call "%~dp0fix_deps.bat"
if errorlevel 1 (
  echo [ERROR] No se pudieron instalar las dependencias. Abortando.
  pause
  endlocal
  exit /b 1
)

REM Lanzar procesos en ventanas separadas (sin PowerShell)
start "Growen API" "%~dp0scripts\run_api.cmd"
start "Growen Frontend" "%~dp0scripts\run_frontend.cmd"

echo.
echo [INFO] Se lanzaron backend y frontend en ventanas separadas.
echo [INFO] Backend:  http://127.0.0.1:8000/docs
echo [INFO] Frontend: http://127.0.0.1:5173/
echo.
pause
endlocal
