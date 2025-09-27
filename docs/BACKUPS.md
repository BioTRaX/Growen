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

## Restauración y adaptación a HEAD (Sept 2025)

Esta sección documenta el procedimiento recomendado para tomar un backup histórico (ej. `auto_20250926_210426.dump`) y adaptarlo al estado de schema HEAD actual (todas las migraciones Alembic aplicadas) sin riesgo para la base “productiva”.

### Script de soporte `restore_adapt_dump.py`

Se agregó el script `scripts/restore_adapt_dump.py` que automatiza:

1. Detección de formato del dump (custom `PGDMP` vs SQL plano).
2. Creación (o reutilización) de una base temporal.
3. Restauración del dump.
4. Ejecución de `alembic upgrade head` (opcional con `--no-upgrade`).
5. Ajuste de secuencias (`setval`) post-migración.
6. Auditoría opcional (`--audit`) con scripts existentes (`check_schema.py`, `debug_migrations.py`).
7. Export de un nuevo dump migrado (`--export`).

### Ejemplo de uso

```powershell
# Variables de entorno mínimas (ejemplo)
$env:PGHOST = "127.0.0.1"
$env:PGPORT = "5432"   # O el puerto mapeado en docker-compose
$env:PGUSER = "postgres"
$env:PGPASSWORD = "postgres"

python scripts/restore_adapt_dump.py `
   --dump backups/pg/auto_20250926_210426.dump `
   --temp-db growen_restore_tmp `
   --export `
   --audit
```

Resultado esperado:
- DB temporal `growen_restore_tmp` creada con datos restaurados.
- Migraciones Alembic aplicadas hasta HEAD.
- Secuencias ajustadas para evitar colisiones de PK.
- Dump migrado adicional en `backups/pg/*_migrated_YYYYMMDD_HHMMSS.dump`.

### Flags útiles

- `--reuse-temp`: no elimina la DB temporal si ya existe (permite reintentar pasos fallidos de migración).
- `--no-upgrade`: solo restaura sin aplicar migraciones (inspección previa).
- `--no-fix-sequences`: omite ajuste de secuencias (si se desea manejar manualmente).
- `--export-tag etiqueta`: personaliza sufijo del archivo exportado.

### Estrategia de “swap”

Una vez validada la DB temporal: 
1. Detener servicios que escriben en la base productiva.
2. Hacer último backup de la base actual (vacía o corrupta) por trazabilidad.
3. (Opcional) Renombrar: `ALTER DATABASE growen RENAME TO growen_old;` (si no hay conexiones).
4. Crear base destino limpia `growen` y restaurar el dump migrado final (`pg_restore -d growen -j 4 nuevo_dump_migrated.dump`).
5. Verificar `alembic current` == HEAD y correr smoke tests (`python scripts/test_login_flow.py` y/o `pytest -q tests/test_parse_remito_sample_pdf.py::test_parse_remito_example_pdf`).
6. Ejecutar `python scripts/check_admin_user.py` para garantizar usuario admin.

### Problemas comunes y mitigación

| Problema | Causa típica | Mitigación |
|----------|--------------|------------|
| Falla migración por NOT NULL | Datos históricos con NULL | Crear valor por defecto antes, reintentar upgrade |
| UNIQUE constraint violation | Duplicados en datos antiguos | Normalizar (merge/eliminar) filas duplicadas antes de reintentar |
| Error enum value missing | Migración asume enum extendido | `ALTER TYPE <enum> ADD VALUE IF NOT EXISTS 'valor';` y reintentar |
| Secuencias desfasadas | Insert lanza duplicate key | Reejecutar script con ajuste de secuencias o usar bloque DO manual |

### Checklist de aceptación (post-restauración)

- `alembic current` muestra un único head y coincide con HEAD del repositorio.
- Secuencias sincronizadas (inserción de prueba en tablas con PK serial/identity sin error).
- Usuario admin válido (`scripts/check_admin_user.py`).
- Auditoría de schema (`scripts/audit_schema.py --url <DB_URL>`) sin objetos marcados como missing.
- Logs de arranque de la API sin tracebacks relevantes.
- Dump migrado adicional almacenado y backup original conservado sin modificación.

### Notas de auditoría

Se recomienda conservar ambos archivos:
- Original: `auto_YYYYMMDD_HHMMSS.dump`
- Migrado: `auto_YYYYMMDD_HHMMSS_migrated_*.dump`

Esto permite reproducir pasos en caso de que se descubra una inconsistencia posterior.

### Futuras mejoras sugeridas

- Detección automática de duplicados previos a UNIQUE y generación de reporte.
- Integrar auditoría de enums antes de aplicar migraciones.
- Añadir modo `--dry-run` que ejecute migraciones dentro de un snapshot (cuando se use en entornos con soporte a `CREATE DATABASE ... TEMPLATE`).

