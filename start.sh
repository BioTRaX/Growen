#!/usr/bin/env bash
# NG-HEADER: Nombre de archivo: start.sh
# NG-HEADER: Ubicación: start.sh
# NG-HEADER: Descripción: Script de arranque (Unix) para el entorno local.
# NG-HEADER: Lineamientos: Ver AGENTS.md
set -euo pipefail

# Ir a la raíz del repo
cd "$(dirname "$0")"

# Verificar venv
if [[ ! -f ".venv/bin/activate" ]]; then
  echo "[ERROR] No existe .venv. Cree el entorno: python3 -m venv .venv"
  exit 1
fi

# Activar venv
source .venv/bin/activate

# Verificar .env y DB_URL
if [[ ! -f ".env" ]]; then
  echo "[ERROR] Falta .env (copie .env.example a .env y complete DB_URL/IA)."
  exit 1
fi
# Cargar variables ignorando comentarios
export $(grep -v '^#' .env | xargs)
if [[ -z "${DB_URL:-}" ]]; then
  echo "[ERROR] Falta DB_URL en .env"
  exit 1
fi
if [[ -z "${OLLAMA_MODEL:-}" ]]; then
  echo "[WARN] Falta OLLAMA_MODEL en .env"
fi

# Backend (background) y Frontend (foreground)
echo "[INFO] Aplicando migraciones de base de datos..."
if ! .venv/bin/python -m alembic upgrade head; then
  echo "[ERROR] Falló la ejecución de migraciones. Abortando inicio."
  exit 1
fi
( uvicorn services.api:app --host 127.0.0.1 --port 8000 --reload --log-level debug --access-log ) &

cd frontend
if [[ ! -d node_modules ]]; then
  echo "[INFO] Instalando dependencias frontend..."
  npm install
fi
echo "[INFO] Iniciando frontend..."
npm run dev
