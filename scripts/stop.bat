@echo off
setlocal EnableExtensions

REM Matar procesos que usen los puertos 8000 (API) y 5173 (Vite)
for /f "tokens=5" %%P in ('netstat -ano ^| findstr :8000') do taskkill /PID %%P /F >nul 2>&1
for /f "tokens=5" %%P in ('netstat -ano ^| findstr :5173') do taskkill /PID %%P /F >nul 2>&1

REM Matar procesos huérfanos típicos
taskkill /IM node.exe /F >nul 2>&1
taskkill /IM python.exe /F >nul 2>&1

exit /b
