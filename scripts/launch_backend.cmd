@echo off
setlocal ENABLEDELAYEDEXPANSION

rem Cambiar al root del repo
cd /d "%~dp0\.."
set "ROOT=%CD%"
set "VENV=%ROOT%\.venv\Scripts"
if not defined LOG_DIR set "LOG_DIR=%ROOT%\logs"
if not exist "%LOG_DIR%" mkdir "%LOG_DIR%"

echo [BOOT] Lanzando runserver (cwd=%CD%, py=%VENV%\python.exe) >> "%LOG_DIR%\backend.log" 2>&1
"%VENV%\python.exe" -m services.runserver >> "%LOG_DIR%\backend.log" 2>&1

endlocal
exit /b %ERRORLEVEL%