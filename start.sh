#!/usr/bin/env bash
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
( uvicorn services.api:app --host 127.0.0.1 --port 8000 --reload --log-level debug --access-log ) &

cd frontend
if [[ ! -d node_modules ]]; then
  echo "[INFO] Instalando dependencias frontend..."
  npm install
fi
echo "[INFO] Iniciando frontend..."
npm run dev
