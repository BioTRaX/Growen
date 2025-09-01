#!/bin/sh
# NG-HEADER: Nombre de archivo: wait-for.sh
# NG-HEADER: Ubicación: infra/wait-for.sh
# NG-HEADER: Descripción: Pendiente de descripción
# NG-HEADER: Lineamientos: Ver AGENTS.md
set -e
host="$1"
shift
while ! nc -z $host >/dev/null 2>&1; do
  echo "Esperando a $host..."
  sleep 1
done
exec "$@"
