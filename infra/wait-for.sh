#!/bin/sh
set -e
host="$1"
shift
while ! nc -z $host >/dev/null 2>&1; do
  echo "Esperando a $host..."
  sleep 1
done
exec "$@"
