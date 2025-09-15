<!-- NG-HEADER: Nombre de archivo: MIGRATIONS_NOTES.md -->
<!-- NG-HEADER: Ubicación: docs/MIGRATIONS_NOTES.md -->
<!-- NG-HEADER: Descripción: Notas técnicas sobre fixes recientes en migraciones Alembic -->
<!-- NG-HEADER: Lineamientos: Ver AGENTS.md -->
# Notas de migraciones (Ajustes Sept 2025)

## Contexto del problema
Durante la reinstalación del entorno se detectaron dos bloqueos principales al ejecutar `alembic upgrade head`:
1. Abort por lógica estricta en la migración `20241105_auth_roles_sessions` cuando `ADMIN_PASS` era un placeholder.
2. Error `psycopg.errors.StringDataRightTruncation: value too long for type character varying(32)` al intentar insertar revisiones largas en la tabla `alembic_version`.

## Causas raíz
- Alembic crea por defecto la tabla `alembic_version` con `VARCHAR(32)`. Las revisiones combinadas (naming descriptivo) excedieron ese límite.
- La migración de auth forzaba un `RuntimeError` si encontraba `ADMIN_PASS` con valor placeholder, deteniendo toda la cadena incluso cuando el entorno de desarrollo ya había provisto un valor válido en `.env` (pero no era leído a tiempo por no usar `override=True` en dotenv en ciertas ejecuciones previas).

## Soluciones aplicadas
### 1. Robustecimiento de `env.py`
- Se añadió `load_dotenv(..., override=True)` para asegurar que las variables del archivo `.env` reemplacen cualquier variable previa en el proceso.
- Se implementó `_ensure_alembic_version_column` con la siguiente lógica:
  - Si la tabla `alembic_version` no existe, se crea manualmente con `version_num VARCHAR(255)`.
  - Si existe y la longitud es `< 64`, se altera a `VARCHAR(255)`.
- Se configuró `version_table_column_type=String(255)` en ambos modos (`offline` y `online`) para futuras inicializaciones limpias.
- Logging extendido: archivo por ejecución en `logs/migrations/`, DB_URL ofuscado, historial de heads y revisiones recientes.

### 2. Migración `20241105_auth_roles_sessions`
- Eliminado el `RuntimeError` por placeholder; reemplazado por:
  - Carga explícita de `.env` dentro de la migración.
  - Fallback a password segura predefinida solo para entorno de desarrollo si el placeholder persiste.
  - Hash Argon2 generado con import local protegido (manejo defensivo si `passlib` no está disponible).

### 3. Scripts auxiliares
- `scripts/check_admin_user.py`: inspección rápida para confirmar creación del usuario admin después de migraciones.
- `scripts/seed_admin.py`: si no existe admin, lo crea de forma idempotente; advierte si se usa un placeholder.

## Flujo recomendado post-clone
```bash
# 1. Configurar .env (DB_URL, ADMIN_USER, ADMIN_PASS, SECRET_KEY, etc.)
# 2. Crear y activar venv
pip install -e .
# 3. Ejecutar migraciones
alembic upgrade head
# 4. Verificar usuario admin (opcional)
python scripts/check_admin_user.py
# 5. Sembrar manualmente si fuera necesario
python scripts/seed_admin.py
```

## Verificación rápida
- La tabla `alembic_version` debe mostrar `version_num` definido como `character varying(255)`:
```sql
\d alembic_version;
```
- El usuario admin debe existir:
```sql
SELECT id, identifier, role FROM users WHERE role='admin';
```

## Lecciones aprendidas
- Evitar abortar migraciones por configuración no crítica: preferir warnings y fallbacks.
- Ampliar temprano estructuras de control (como `alembic_version`) cuando se adoptan convenciones de nombres verbosos.
- Asegurar `override=True` en carga de variables para entornos reproducibles.

## Próximos posibles refinamientos
- Añadir test automatizado que valide la longitud de `alembic_version.version_num` en pipelines CI sobre DB temporal.
- Exponer health check que confirme estado migracional (`current_rev == head`).
- Implementar util CLI `ng migrations status` para mostrar delta entre `current` y `head`.

---
Documentado el: 2025-09-13

## Scripts auxiliares adicionales (Sept 2025)

Se incorporó un conjunto de scripts para diagnosticar y resolver estados irregulares de Alembic (múltiples heads, stamping manual, etc.).

### Resumen de scripts

- `scripts/debug_migrations.py`: Reporte detallado (`alembic current`, `heads`, `history`). Marca advertencia si detecta más de un head.
- `scripts/check_schema.py`: Dump de columnas clave y listado de filas en `alembic_version` (puede mostrar múltiples revisiones si la tabla quedó corrupta/ramificada).
- `scripts/stamp_head_manual.py`: Ahora acepta `TARGET_HEAD` (env). Normaliza múltiples filas a una sola. Uso excepcional: preferir `alembic merge`.
- `scripts/merge_heads_and_stamp.py` (nuevo): Consolida múltiples heads hacia un merge ya creado sin regenerar archivo.

### Uso típico ante error "Version table 'alembic_version' has more than one head present"

1. Crear (si no existe) la migración de merge:
  ```bash
  alembic revision --merge -m "merge heads" <head1> <head2>
  ```
2. Ejecutar script de consolidación:
  ```bash
  python scripts/merge_heads_and_stamp.py --target <revision_merge>
  ```
3. Verificar estado:
  ```bash
  alembic heads   # Debe mostrar sólo el merge
  alembic current # Debe coincidir con el merge
  ```
4. (Solo recuperación manual) Stamping directo:
  ```bash
  set TARGET_HEAD=<revision_merge>
  python scripts/stamp_head_manual.py
  ```

### Consideraciones

- Evitar stamping manual antes de aplicar realmente los cambios de esquema (verificar con `check_schema.py`).
- `merge_heads_and_stamp.py` no genera el archivo de merge; exige que exista para mantener historial auditable.
- Tras consolidar, cualquier nueva migración debe apuntar al único head resultante.

---
Actualización complementaria: 2025-09-13 (segunda entrada del día)
