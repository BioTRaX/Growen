@echo off
setlocal

echo Cerrando backend (puerto 8000)...
set FOUND_BACKEND=
for /f "tokens=5" %%a in ('netstat -ano ^| findstr ":8000"') do (
    taskkill /PID %%a /F >nul 2>&1
    set FOUND_BACKEND=1
)
if not defined FOUND_BACKEND (
    echo No se encontró proceso en puerto 8000.
)

echo Cerrando frontend (puerto 5173)...
set FOUND_FRONTEND=
for /f "tokens=5" %%a in ('netstat -ano ^| findstr ":5173"') do (
    taskkill /PID %%a /F >nul 2>&1
    set FOUND_FRONTEND=1
)
if not defined FOUND_FRONTEND (
    echo No se encontró proceso en puerto 5173.
)

pause
