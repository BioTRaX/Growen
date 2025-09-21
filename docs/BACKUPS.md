<!-- NG-HEADER: Nombre de archivo: BACKUPS.md -->
<!-- NG-HEADER: Ubicación: docs/BACKUPS.md -->
<!-- NG-HEADER: Descripción: Guía de backups y restore de la base de datos -->
<!-- NG-HEADER: Lineamientos: Ver AGENTS.md -->

# Backups de base de datos (PostgreSQL)

Este proyecto implementa dos mecanismos:

- Backup automático diario al iniciar la API si el último backup tiene más de 24 horas.
- Backup on-demand desde el Panel de Admin (UI) con descarga del archivo.

Los backups se almacenan en `backups/pg/*.dump` (formato personalizado `pg_dump -Fc`).

## Endpoints

- GET `/admin/backups` (admin): lista backups disponibles.
- POST `/admin/backups/run` (admin + CSRF): crea un backup ahora.
- GET `/admin/backups/download/{filename}` (admin): descarga un backup.

## UI (Admin)

Ir a Admin → Backups. Desde allí se puede:

- Ver la lista de backups.
- Crear un backup inmediato (“Backup ahora”).
- Descargar un backup existente.

## Restore (pg_restore)

Para restaurar un backup `.dump` (formato `-Fc`) en un Postgres vacío o existente:

1. Crear la base si hace falta:
   - `createdb -h 127.0.0.1 -p 5433 -U growen growen`
2. Restaurar:
   - `pg_restore -h 127.0.0.1 -p 5433 -U growen -d growen -c -j 4 backups/pg/backup_YYYYMMDD_HHMMSS.dump`
   - Flags útiles:
     - `-c` para limpiar objetos antes de restaurar.
     - `-j 4` para paralelizar (ajustar según CPU).

Notas Windows/Docker:

- Si está corriendo el contenedor `growen-postgres`, puede usarse `docker exec` con `pg_restore` dentro del contenedor o mapear el puerto (ya mapeado a 5433) y usar herramientas del host.
- El sistema de backups intenta usar `docker exec` si está disponible (y el contenedor existe); de lo contrario usa `pg_dump` del host.

## Variables y requisitos

- Debe existir `DB_URL` apuntando a la base activa (ej.: `postgresql+psycopg://growen:pass@127.0.0.1:5433/growen`).
- Para `pg_dump` en host, tener instalado PostgreSQL client y `pg_dump` en el PATH.
- Para `docker exec`, debe existir el contenedor `growen-postgres`.

## Operación segura

- Evitar `docker compose down -v` en entornos con datos; borra volúmenes.
- Programar backups regulares si se despliega en producción (este mecanismo hace uno al día según arranque/último backup, no es un cron tradicional).
- Versionar y copiar `backups/` a almacenamiento externo si aplica.
