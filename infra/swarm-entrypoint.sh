#!/usr/bin/env sh
# NG-HEADER: Nombre de archivo: swarm-entrypoint.sh
# NG-HEADER: Ubicación: infra/swarm-entrypoint.sh
# NG-HEADER: Descripción: Adapta secretos Docker Swarm a variables heredadas sin imprimirlos.
# NG-HEADER: Lineamientos: Ver AGENTS.md
set -eu

load_secret() {
  variable="$1"
  file_variable="${variable}_FILE"
  eval "secret_file=\${$file_variable:-}"
  if [ -n "$secret_file" ]; then
    [ -f "$secret_file" ] || { echo "secret_file_unreadable: $variable" >&2; exit 1; }
    secret_value="$(sed -e 's/[\r\n]*$//' "$secret_file")"
    export "$variable=$secret_value"
  fi
}

load_secret DB_PASS
load_secret POSTGRES_PASSWORD
load_secret SECRET_KEY
load_secret INTERNAL_SERVICE_TOKEN
load_secret MCP_PRODUCTS_SECRET_KEY
load_secret MCP_WEB_SEARCH_SECRET_KEY
exec "$@"
