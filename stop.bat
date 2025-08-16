@echo off
REM Uvicorn (Windows)
taskkill /f /im python.exe /fi "WINDOWTITLE eq Growen API" >nul 2>&1
taskkill /f /im node.exe /fi "WINDOWTITLE eq Growen Frontend" >nul 2>&1

REM Fallback: puertos 8000 y 5173
for /f "tokens=5" %%p in ('netstat -ano ^| findstr /c":8000" ^| findstr LISTENING') do taskkill /f /pid %%p >nul 2>&1
for /f "tokens=5" %%p in ('netstat -ano ^| findstr /c":5173" ^| findstr LISTENING') do taskkill /f /pid %%p >nul 2>&1
