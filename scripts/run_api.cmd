@echo off
setlocal
REM Ubicar raíz del repo (dos niveles arriba desde /scripts)
set "ROOT=%~dp0.."
cd /d "%ROOT%"

if not exist ".\.venv\Scripts\activate.bat" (
  echo [ERROR] No existe .venv\Scripts\activate.bat
  echo Cree el venv: python -m venv .venv
  echo Active: .\.venv\Scripts\activate.bat
  echo Instale deps: pip install -e .
  pause
  exit /b 1
)

call ".\.venv\Scripts\activate.bat"
echo [INFO] Lanzando backend (Uvicorn)...
uvicorn services.api:app --host 127.0.0.1 --port 8000 --reload --log-level debug --access-log

echo [INFO] Backend finalizado.
pause
endlocal
