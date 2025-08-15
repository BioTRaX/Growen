@echo off
setlocal
set "ROOT=%~dp0.."
cd /d "%ROOT%\frontend"

if not exist "package.json" (
  echo [ERROR] No existe frontend\package.json
  echo Verifique que la carpeta frontend este correcta.
  dir /b
  pause
  exit /b 1
)

if not exist "node_modules" (
  echo [INFO] Instalando dependencias del frontend...
  npm install
)

echo [INFO] Lanzando frontend (Vite)...
npm run dev

echo [INFO] Frontend finalizado.
pause
endlocal
