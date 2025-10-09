#!/bin/sh
# NG-HEADER: Nombre de archivo: wait-for.sh
# NG-HEADER: Ubicación: infra/wait-for.sh
# NG-HEADER: Descripción: Espera a host:port disponible sin depender de 'nc' (usa Python socket).
# NG-HEADER: Lineamientos: Ver AGENTS.md
set -e

if [ -z "$1" ]; then
  echo "Uso: $0 host:port [command ...]" >&2
  exit 1
fi

TARGET="$1"
shift

HOST=$(printf "%s" "$TARGET" | awk -F: '{print $1}')
PORT=$(printf "%s" "$TARGET" | awk -F: '{print $2}')
if [ -z "$HOST" ] || [ -z "$PORT" ]; then
  echo "Formato inválido. Use host:port (ej: db:5432)" >&2
  exit 1
fi

# Timeout total opcional por env var (segundos)
: "${WAIT_TIMEOUT:=60}"

echo "[wait-for] Esperando a $HOST:$PORT (timeout=${WAIT_TIMEOUT}s)..."
START_TS=$(date +%s)

while :; do
  python - "$HOST" "$PORT" <<'PY'
import socket, sys
host, port = sys.argv[1], int(sys.argv[2])
s = socket.socket()
s.settimeout(0.8)
try:
    s.connect((host, port))
    sys.exit(0)
except Exception:
    sys.exit(1)
finally:
    try:
        s.close()
    except Exception:
        pass
PY
  CODE=$?
  if [ "$CODE" -eq 0 ]; then
    echo "[wait-for] $HOST:$PORT disponible."
    break
  fi
  NOW=$(date +%s)
  ELAPSED=$((NOW - START_TS))
  if [ "$ELAPSED" -ge "$WAIT_TIMEOUT" ]; then
    echo "[wait-for] Timeout esperando a $HOST:$PORT tras ${ELAPSED}s" >&2
    exit 1
  fi
  sleep 1
done

if [ "$#" -gt 0 ]; then
  exec "$@"
fi
