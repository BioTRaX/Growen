@echo off
setlocal ENABLEDELAYEDEXPANSION

rem Directorios
set "ROOT=%~dp0.."
if not defined LOG_DIR set "LOG_DIR=%ROOT%\logs"
if not exist "%LOG_DIR%" mkdir "%LOG_DIR%"
set "LOG_FILE=%LOG_DIR%\stop.log"

rem Validar dependencias
where python >NUL 2>&1
if %ERRORLEVEL% NEQ 0 call :log "[WARN] python no esta instalado"
where npm >NUL 2>&1
if %ERRORLEVEL% NEQ 0 call :log "[WARN] npm no esta instalado"

call :log "[INFO] Cerrando procesos uvicorn y vite..."
for /f "tokens=2 delims=," %%p in ('tasklist /FI "IMAGENAME eq python.exe" /FO CSV ^| findstr /I "uvicorn"') do taskkill /PID %%~p /F >NUL 2>&1
for /f "tokens=2 delims=," %%p in ('tasklist /FI "IMAGENAME eq node.exe"   /FO CSV ^| findstr /I "vite"') do taskkill /PID %%~p /F >NUL 2>&1
call :log "[INFO] Procesos finalizados"

endlocal
exit /b 0

:log
set "ts=!DATE! !TIME!"
>>"%LOG_FILE%" echo [!ts!] %~1
echo [!ts!] %~1
exit /b 0

