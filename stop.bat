@echo off
setlocal

REM ── Modo silencioso para uso desde start.bat
if "%1"=="-q" set QUIET=1

if not exist logs mkdir logs

echo [%date% %time%] Cerrando backend (puerto 8000)... >> logs\server.log
for /f "tokens=5" %%a in ('netstat -ano ^| findstr ":8000"') do taskkill /PID %%a /F

echo [%date% %time%] Cerrando frontend (puerto 5173)... >> logs\server.log
for /f "tokens=5" %%a in ('netstat -ano ^| findstr ":5173"') do taskkill /PID %%a /F

if not defined QUIET pause

