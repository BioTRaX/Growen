@echo off
setlocal ENABLEDELAYEDEXPANSION

REM ── Ir a la raíz del repo (ruta de este .bat)
cd /d "%~dp0"

REM ── Verificar venv
if not exist ".\.venv\Scripts\activate.bat" (
  echo [WARN] No existe .venv. Cree el entorno primero: python -m venv .venv
  echo        Luego: .\.venv\Scripts\activate.bat && pip install -e .
  pause
  goto :eof
)

REM ── Activar venv
call ".\.venv\Scripts\activate.bat"

REM ── Verificar .env y variables básicas
if not exist ".env" (
  echo [ERROR] Falta .env (copie .env.example a .env y complete DB_URL/IA).
  pause
  goto :eof
)

for /f "usebackq tokens=1,2 delims==" %%A in (".env") do (
  if /I "%%A"=="DB_URL" set DB_URL=%%B
  if /I "%%A"=="OLLAMA_MODEL" set OLLAMA_MODEL=%%B
)

if "%DB_URL%"=="" (
  echo [ERROR] Falta DB_URL en .env
  pause
  goto :eof
)
if "%OLLAMA_MODEL%"=="" (
  echo [WARN] Falta OLLAMA_MODEL en .env
)

REM ── Iniciar backend en ventana nueva
start "Growen API" cmd /k "uvicorn services.api:app --reload"

REM ── Frontend: instalar deps si faltan y levantar Vite
pushd frontend
if not exist "node_modules" (
  echo [INFO] Instalando dependencias frontend...
  npm install
)
echo [INFO] Iniciando frontend...
npm run dev
popd
