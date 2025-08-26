@echo off
setlocal EnableExtensions EnableDelayedExpansion

REM Cerrar ventanas lanzadas por start (si existen)
REM Nota: /T mata el árbol (ventana cmd y sus hijos)
for %%T in ("Growen API","Growen Frontend") do (
	taskkill /FI "WINDOWTITLE eq %%~T*" /T /F >nul 2>&1
)

REM Intentar matar por puerto con PowerShell (locale-agnóstico)
for %%P in (8000 5173) do (
	powershell -NoProfile -ExecutionPolicy Bypass -Command "Get-NetTCPConnection -State Listen -LocalPort %%P -ErrorAction SilentlyContinue | Select-Object -ExpandProperty OwningProcess | ForEach-Object { try { Stop-Process -Id $_ -Force -ErrorAction Stop } catch {} }" >nul 2>&1
)

REM Fallback a netstat si PS falló o no existe el cmdlet
for %%P in (8000 5173) do (
	for /f "tokens=5" %%I in ('netstat -ano -p TCP ^| findstr /R ":%%P "') do (
		taskkill /PID %%I /F >nul 2>&1
	)
)

REM Matar procesos huérfanos típicos (por si quedaron desanclados)
taskkill /IM node.exe /F >nul 2>&1
taskkill /IM python.exe /F >nul 2>&1

REM Esperar a que los puertos se liberen (hasta ~8s)
set "__tries=0"
:__waitloop
set /a __tries+=1
set "__busy=0"
for %%P in (8000 5173) do (
	netstat -ano | findstr ":%%P" >nul 2>&1 && set "__busy=1"
)
if "!__busy!"=="1" (
	if !__tries! LSS 8 (
		timeout /t 1 /nobreak >nul
		goto __waitloop
	)
)

exit /b 0
