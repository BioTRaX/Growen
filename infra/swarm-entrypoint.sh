#!/usr/bin/env sh
# NG-HEADER: Nombre de archivo: swarm-entrypoint.sh
# NG-HEADER: Ubicación: infra/swarm-entrypoint.sh
# NG-HEADER: Descripción: Adapta secretos Docker Swarm a variables heredadas sin imprimirlos.
# NG-HEADER: Lineamientos: Ver AGENTS.md
set -eu

# Los procesos leen directamente las rutas *_FILE. No convertir secretos en
# variables ni argumentos: producción rechaza valores directos por diseño.
exec "$@"
