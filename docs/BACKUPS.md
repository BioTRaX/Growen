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

### Nuevo (Oct 2025): Desactivar backup automático en desarrollo

Si en tu entorno de desarrollo no tienes instaladas las utilidades cliente de PostgreSQL (por ejemplo `pg_dump`) o simplemente quieres evitar el backup automático al arrancar la API, puedes definir:

```
DISABLE_AUTO_BACKUP=1
```

Efectos:
- El arranque no intentará generar backup diario.
- Se evitarán tracebacks de `pg_dump no encontrado` en `backend.log`.
- La respuesta enviada por la función interna de auto-backup incluirá `{ "disabled": true }`.

Cuando reinstales las herramientas de PostgreSQL o habilites nuevamente el mecanismo, elimina la variable o ponla en `0`.

Nota: Si `DISABLE_AUTO_BACKUP` no está activo y no existe `pg_dump`, ahora el sistema registra el fallo sin interrumpir el arranque (return code 127) y limpia archivos incompletos.

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

## Incidente de Restauración y Consolidación (Octubre 2025)

### Resumen ejecutivo
Se detectó pérdida/aparente ausencia de productos en la UI tras incidente. Existían dos bases:

- `growen` con datos completos de negocio (≈92 products + equivalences completas).
- `growen_old` con esquema más avanzado (migraciones posteriores) pero datos truncados (14 products) y tablas adicionales (`variants`, `images`).

Se decidió conservar `growen` como fuente de verdad y aplicar migraciones pendientes hasta `20250927_consolidated_base`, rescatando únicamente la fila/filas útiles de `images` (opcional) y evaluando `variants` (ya presentes en la base principal). No se hizo swap: se migró in-place.

### Timeline resumido
| Paso | Acción |
|------|--------|
| 1 | Identificación de backups y conteos iniciales (products 92 en `growen`). |
| 2 | Creación/uso de script `diagnose_products_visibility.py` (counts, nulls, orphans). |
| 3 | Desarrollo de `compare_products_between_dbs.py` para contrastar `growen_old` vs `growen`. |
| 4 | Detección: `growen_old` más nuevo en Alembic pero con datos incompletos. |
| 5 | Backup previo: `pg_dump -Fc growen` (`growen_pre_migrate_YYYYMMDD_HHMMSS.dump`). |
| 6 | Ejecución `alembic upgrade head` sobre `growen`. |
| 7 | Export selectiva de `variants` / `images` desde `growen_old` (evaluación). |
| 8 | Re‐diagnóstico y validación UI. |
| 9 | Cierre y documentación. |

### Scripts involucrados
- `scripts/restore_adapt_dump.py` (previo, no usado en este flujo directo pero parte de base de procedimientos).
- `scripts/diagnose_products_visibility.py` (diagnóstico consolidado).
- `scripts/compare_products_between_dbs.py` (comparación de datasets y esquema). 

### Decisiones clave
1. No se promueve `growen_old` por escasez de datos críticos.
2. Migración in-place de `growen` hasta HEAD para alinear esquema.
3. Datos sensibles: `products`, `supplier_products`, `product_equivalences` preservados íntegros.
4. Contenido de `variants` ya existente en la base principal (sin reimport masiva) — import selectivo descartado o no necesario.
5. `images`: import puntual condicionada a necesidades reales (estructura validada antes de COPY con columnas explícitas).
6. Registro final en este documento para trazabilidad.

### Fingerprint y verificaciones
- Fingerprint productos (old) usado sólo como indicador: `4a77b64c744f96b1edee7be967edf87f` (no aplicado para canonizar en productivo por diferencias de columnas).
- Post-migración: `diagnose_products_visibility.py` confirmó counts esperados y ausencia de huérfanos críticos.
- UI validó presencia de los ~92 productos y navegación correcta sin errores 500.

### Checklist final (completado)
- [x] Backup pre-migración creado (`growen_pre_migrate_*.dump`).
- [x] Migraciones aplicadas: `alembic current` = `20250927_consolidated_base`.
- [x] Counts núcleo preservados (products 92, supplier_products 92, product_equivalences 92).
- [x] Huérfanos críticos = 0 según diagnóstico.
- [x] Diagnóstico JSON guardado (`diag_after_import.json`).
- [x] Comparación inter-bases archivada (`compare_post_migrate.json`, `compare_final.json`).
- [x] Import puntual de imágenes/variants evaluado (sin duplicar PK; se evitó sobrescritura).
- [x] Secuencias ajustadas tras intentos de import (`setval`).
- [x] UI verificada: datos visibles, sin tracebacks en `backend.log`.
- [ ] Renombrar/archivar `growen_old` (pendiente opcional):
   - `ALTER DATABASE growen_old RENAME TO growen_archive_20251005;`

### Comandos clave (referencia)
```
# Comparación
python scripts/compare_products_between_dbs.py --source-url <old> --target-url <main> --json > compare_post_migrate.json

# Migración a HEAD
alembic upgrade head

# Diagnóstico final
python scripts/diagnose_products_visibility.py --json > diag_after_import.json

# Ajuste secuencias ejemplo
docker exec growen-postgres psql -U growen -d growen -c "SELECT setval(pg_get_serial_sequence('variants','id'), COALESCE((SELECT MAX(id) FROM variants),0)+1, false);"
```

### Recomendaciones post-incidente
- Automatizar iluminación temprana de divergencia (task diaria con fingerprint + counts archivados en log rotado).
- Añadir test de smoke de endpoint `/products` comparando count vs DB antes de deploy.
- Evaluar cifrado/retención de dumps antiguos y limpieza automatizada (TTL configurable).

---
Actualizado: 2025-10-05

