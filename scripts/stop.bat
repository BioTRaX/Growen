@echo off
REM cierra uvicorn y vite del proyecto actual
for /f "tokens=2 delims=," %%p in ('tasklist /FI "IMAGENAME eq python.exe" /FO CSV ^| findstr /I "uvicorn"') do taskkill /PID %%~p /F >NUL 2>&1
for /f "tokens=2 delims=," %%p in ('tasklist /FI "IMAGENAME eq node.exe"   /FO CSV ^| findstr /I "vite"') do taskkill /PID %%~p /F >NUL 2>&1
