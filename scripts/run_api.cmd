@echo off
cd /d "%~dp0\.."

if not exist ".venv\Scripts\activate.bat" (
  echo [ERROR] No existe .venv\Scripts\activate.bat
  echo Cree el venv: python -m venv .venv
  echo Active: .venv\Scripts\activate.bat
  echo Instale deps: pip install -e .
  pause
  exit /b 1
)

call ".venv\Scripts\activate.bat"

REM aplicar migraciones antes de iniciar
python -m alembic upgrade head || (
  echo [ERROR] Fallo al aplicar migraciones
  pause
  exit /b 1
)

echo [INFO] Lanzando backend (Uvicorn)...
uvicorn services.api:app --host 127.0.0.1 --port 8000 --reload --log-level info --access-log

echo [INFO] Backend finalizado.
pause
