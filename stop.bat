@echo off
setlocal
cd /d "%~dp0"

set "KILLCOUNT=0"
for /f "tokens=5" %%a in ('netstat -ano ^| findstr ":8000"') do (
  taskkill /PID %%a /F >NUL 2>&1
  set /a KILLCOUNT+=1
)
if %KILLCOUNT% EQU 0 (
  echo [INFO] No se encontro proceso en puerto 8000
) else (
  echo [INFO] Se cerraron %KILLCOUNT% proceso(s) del puerto 8000
)

set "KILLCOUNT=0"
for /f "tokens=5" %%a in ('netstat -ano ^| findstr ":5173"') do (
  taskkill /PID %%a /F >NUL 2>&1
  set /a KILLCOUNT+=1
)
if %KILLCOUNT% EQU 0 (
  echo [INFO] No se encontro proceso en puerto 5173
) else (
  echo [INFO] Se cerraron %KILLCOUNT% proceso(s) del puerto 5173
)

echo Hecho.
pause
endlocal
