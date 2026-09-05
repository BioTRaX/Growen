<!-- NG-HEADER: Nombre de archivo: MIGRATIONS_NOTES.md -->
<!-- NG-HEADER: Ubicación: docs/MIGRATIONS_NOTES.md -->
<!-- NG-HEADER: Descripción: Notas técnicas sobre fixes recientes en migraciones Alembic -->
<!-- NG-HEADER: Lineamientos: Ver AGENTS.md -->

# Notas de migraciones

## 2026-09-05 — Permisos MeLi extensos (`20260905_meli_scopes_text`)

Validación: 12 pruebas aprobadas (OAuth, gateway, upgrade incremental con datos y downgrade protegido, cadena completa en PostgreSQL temporal). Aplicada al entorno local: head `20260905_meli_scopes_text`, columna `scopes` confirmada como `text`, gateway reconstruido con readiness HTTP 200 y callback público incompleto HTTP 422. `alembic check` sigue reportando drift global (por ejemplo `sku_sequences`, defaults y constraints de usuarios); no se corrigió deriva ajena a este cambio. La autorización real posterior al despliegue quedó confirmada el 2026-09-05: cuenta activa con scopes de 505 caracteres y ambos tokens cifrados persistidos.

La revisión incremental convierte únicamente `meli_accounts.scopes` de `VARCHAR(500)` a `TEXT`, conservando datos y nulabilidad. Los permisos funcionales actuales de MeLi pueden superar 500 caracteres; el callback obtenía tokens pero fallaba al insertar la cuenta. No se modifica la revisión histórica ni se recortan permisos. El downgrade toma un lock exclusivo y rechaza la reversión si existe algún valor mayor a 500 caracteres, evitando pérdida de datos. Esta migración no corrige el drift histórico ajeno a MeLi.

## 2026-08-31 — Mercado Libre transaccional (`20260831_meli_sync_v1`)

La revisión posterior a `20260828_market_pipeline_v2` crea `meli_accounts`, `meli_oauth_states`, `meli_notifications`, `meli_item_links` y `meli_sync_jobs`. Los tokens y verificadores se guardan únicamente como ciphertext; las notificaciones conservan un sobre mínimo y los jobs forman el outbox de la cola `meli_sync`. El downgrade se bloquea cuando alguna tabla contiene datos para evitar perder autorizaciones o trazabilidad; con tablas vacías elimina índices y tablas en orden inverso. Aplicar `alembic upgrade head` antes de iniciar gateway o worker. La cadena completa desde una base PostgreSQL temporal vacía alcanzó `20260831_meli_sync_v1` el 2026-08-31 y aprobó las tablas/constraints críticas.

## 2026-08-28 — `20260828_market_pipeline_v2`

Revisión incremental posterior a `20260816_chat_rollout_v1`. Agrega a `market_update_items` la etapa persistente y los contadores de competidores existentes, fuentes descubiertas, confirmadas y en cuarentena; `market_update_source_results.operation` distingue validación de extracción.

Durante el upgrade, cualquier item previo todavía `queued|running` se cierra como `failed/completed` con `stale_before_pipeline_v2` y se reconcilian los contadores de su cabecera. No se reencola automáticamente porque el trabajo anterior no posee un lease recuperable. El downgrade está bloqueado: eliminaría cobertura y resultados auditables. Validar con `alembic heads` y `tests/test_migrations_fresh_postgres.py`; el head esperado es `20260828_market_pipeline_v2`.

## 2026-08-27 — auditoría y limpieza de compatibilidad

La base local quedó verificada en `20260816_chat_rollout_v1`, con un único
registro de versión observado y sin la tabla histórica `market_sources`.
Los campos legacy de `products` se conservan deliberadamente durante el ciclo
de rollback React. No se creó una migración destructiva ni se reescribieron
revisiones históricas.

Se retiró el código inalcanzable posterior a los retornos de los adaptadores de
enriquecimiento en `services/routers/catalog.py`. Los endpoints adaptadores y
el alias ORM `MarketSource` permanecen hasta completar la migración de sus
consumidores y el ciclo de deprecación documentado.

## 2026-08-16 — `20260816_chat_rollout_v1`

Revisión lineal desde `20260726_canonical_knowledge_v1`. Crea el singleton `chat_rollout_state`, eventos y checks sin prompts, respuestas, IDs ni secretos. El registro inicial es `disabled/paused`, con autoavance apagado. El downgrade aborta si existe trazabilidad o el estado dejó su valor inicial.

El upgrade incremental local aprobó y `alembic current` coincide con el head único `20260816_chat_rollout_v1`. La prueba PostgreSQL limpia exige este head; queda pendiente ejecutarla con `MIGRATION_TEST_POSTGRES_URL`. El drift histórico de `alembic check` sigue fuera de alcance.

## 2026-08-15 — verificación del estado local

`alembic heads` y `alembic current` coinciden en el head único
`20260726_canonical_knowledge_v1`. `scripts/audit_schema.py --json` aprobó todas
sus verificaciones y la base local contiene las tablas Chat/RAG/Telegram de la
cadena `20260722_chat_*`. No hay identidades, updates, fuentes RAG ni trazas Chat,
y el conteo de sesiones legacy `telegram:<id-numérico>` es cero.

`alembic check` continúa fallando por drift histórico amplio entre metadata y
esquema —incluye tablas, tipos, defaults, índices y FKs ajenos al cambio Chat—.
No se debe autogenerar una revisión masiva para “resolverlo”: primero hay que
clasificar cada diferencia, corregir metadata/migraciones históricas por dominio
y volver a ejecutar el check sobre una base PostgreSQL desechable desde cero.

## 2026-07-26 — Base de Conocimiento Canónica

`20260726_canonical_knowledge_v1` desciende de `20260725_canonical_enrichment_v2`, crea el inventario completo de conocimiento y transforma `market_sources` en `canonical_knowledge_market_profiles`. Cada fuente genera activo, ubicación, etiqueta `market` y capacidades `price|availability|offers`; los IDs se preservan y las FKs históricas continúan válidas.

El downgrade está bloqueado. PostgreSQL vacío alcanzó head con `vector`; el upgrade local conservó 1 perfil, 6 observaciones, 3 resultados y 1 alerta sin huérfanos. Backup: `backups/pg/pre_canonical_knowledge_20260726_1911.dump`.
## 2026-07-25 — contenido canónico y Enrich v2

`20260725_canonical_enrichment_v2` desciende linealmente de `20260722_chat_observability_v3`. Agrega contenido/revisión a `canonical_products`, crea jobs, fuentes y versiones, y aplica un backfill conservador: sólo valores legacy únicos pasan al canónico; cada alternativa se conserva como versión candidata.

La revisión elimina `products.market_price_reference`. Su downgrade está bloqueado porque los valores nunca fueron confiables ni recuperables; Mercado conserva su campo canónico. Desde la revisión siguiente, su configuración técnica vive en perfiles de la Base de Conocimiento, no en fuentes propias. `Product.is_enriching` y los demás campos legacy continúan temporalmente sólo para rollback React.

La validación sobre bases PostgreSQL desechables alcanzó el nuevo head y confirmó tablas/columna. Un upgrade incremental con dos descripciones contradictorias dejó `content_revision=0`, no aplicó descripción y creó dos versiones candidatas. El primer recorrido desde cero falló antes de esta revisión porque el historial RAG requiere `CREATE EXTENSION vector`; tras crearla, el upgrade completo fue exitoso. Este prerrequisito histórico se documenta y no se mezcla con la revisión Enrich v2.

El despliegue local real confirmó que `vector` ya existía y avanzó la base desde
`20260722_chat_observability_v3` hasta el head nuevo. `scripts/audit_schema.py`
aprobó 16 verificaciones; una consulta focal confirmó la tabla de jobs,
`canonical_products.content_revision` y la ausencia de
`products.market_price_reference`. Ver
`docs/ENRICH_V2_DEPLOYMENT_SMOKE_20260725.md`.

## 2026-07-22 — cadena de Chat segura

La cadena lineal parte de `20260721_market_observability_v1` y terminó en el head único de ese corte; hoy forma parte del head posterior `20260726_canonical_knowledge_v1`:

1. `20260722_chat_identity_security_v1`: identidades externas cifradas/HMAC, solicitudes de vínculo, deduplicación Telegram y sesiones opacas.
2. `20260722_chat_rag_policy_v2`: scopes y vigencia en `knowledge_sources`, versión de contenido e índice full-text PostgreSQL. Las fuentes preexistentes quedan `disabled` y restringidas a `admin/web` hasta clasificación explícita.
3. `20260722_chat_observability_v3`: `chat_runs`, `chat_tool_events` y `chat_feedback_events` sin contenido conversacional.

El downgrade se bloquea si existen identidades, updates, políticas RAG o trazabilidad porque implicaría pérdida de evidencia o reglas de acceso. Validación requerida: `alembic heads`, upgrade incremental sobre PostgreSQL con pgvector, constraints/índices y `alembic check`; cualquier drift histórico ajeno debe documentarse, no incorporarse silenciosamente.

La primera revisión amplía `alembic_version.version_num` de 32 a 64 caracteres antes de registrar su ID. La ampliación no se revierte: conservarla evita que un downgrade intente truncar el revision ID activo.

Las sesiones legacy se inspeccionan con `.\.venv\Scripts\python.exe scripts\migrate_legacy_telegram_sessions.py` y sólo se convierten con `--apply`. El script es transaccional y nunca muestra IDs.

## 2026-07-21 — `20260721_market_observability_v1`

Revisión focal posterior a `20260718_product_taxonomy_tags_v1`. Crea `market_alerts`, `market_update_jobs`, `market_update_items` y `market_update_source_results`; amplía fuentes e historial con validación, auditoría y referencias al trabajo originador. `source_type` pasa del enum PostgreSQL cerrado a `VARCHAR(16)` con check `static|dynamic|manual`, lo que permite el backfill manual dentro de una única revisión transaccional.

El índice parcial `uq_market_update_items_active_product` impide dos items `queued|running` para el mismo producto; el servicio complementa la garantía con advisory locks por producto. El backfill sólo crea fuente/observación manual cuando existe una referencia legacy. El downgrade está bloqueado porque eliminaría trazabilidad o podría perder alertas.

Verificación: upgrade incremental local a head y cadena completa sobre PostgreSQL temporal aprobados; la prueba valida tablas, columnas e índice parcial. La revisión no incorpora el drift histórico ajeno que continúa reportando `alembic check`.

## 2026-07-18 — `20260718_product_taxonomy_tags_v1`

Revisión posterior a `20260718_admin_jsonb_v2`. Agrega `categories.kind`, `products.subcategory_id` y `canonical_batch_job_items.tag_names`; incorpora índices únicos funcionales por `kind + lower(name)` y `lower(tags.name)`. Migra raíces a `category`, descendientes a `subcategory` y mueve productos asociados a una categoría hija hacia `subcategory_id`, resolviendo su raíz histórica para `category_id`.

El preflight aborta si detecta colisiones normalizadas y no fusiona registros. El downgrade también aborta si existen subcategorías planas o tags batch que perderían significado. Orden de despliegue: Alembic, API/worker, Vue y MCP Products.

Verificación local: upgrade incremental `20260718_admin_jsonb_v2` → `20260718_product_taxonomy_tags_v1`, head único y cadena completa aprobada sobre una base PostgreSQL temporal vacía, eliminada al finalizar.

`alembic check` conserva drift histórico ya documentado en Mercado, defaults, proveedores e índices legacy; el reporte filtrado no detectó operaciones nuevas sobre `categories.kind`, `products.subcategory_id`, `canonical_batch_job_items.tag_names` ni los índices normalizados de esta revisión.

Para revisiones futuras, la salida de `alembic check` debe clasificarse por objeto: primero los objetos creados o modificados por la revisión y luego el drift histórico ajeno. La prueba de PostgreSQL vacío debe verificar tanto el head esperado como columnas, índices y constraints del cambio. Una rerun focal posterior a un fix no debe reportarse como si se hubiera repetido toda la selección consolidada.

## 2026-07-18 — `20260718_admin_operations_v1` y `20260718_admin_jsonb_v2`

Revisión posterior a `20260717_sales_customers_v4`. Agrega `drive_sync_runs/items`, `scheduler_settings/runs`, `knowledge_index_tasks`, `catalog_generation_runs/events`, `chat_message_feedback`, `ai_prompt_versions/evaluations` y metadatos de clasificación/revisión en `chat_sessions`.

La segunda revisión alinea los metadatos con `JSONBCompat` sobre PostgreSQL. Ambas son focales y no modifican tablas comerciales de otras ramas. El downgrade se bloquea porque eliminaría o degradaría historial operativo y feedback: el rollback del frontend se hace por runtime. Validar con `alembic heads`, `tests/test_migrations_fresh_postgres.py` y PostgreSQL con la extensión `vector`.

Verificación local: la cadena desde una base PostgreSQL vacía alcanzó `20260718_admin_jsonb_v2` y aprobó `tests/test_migrations_fresh_postgres.py`. `alembic check` sigue reportando drift histórico no introducido por estas revisiones —principalmente Mercado, proveedores, defaults e índices legacy— y se conserva como trabajo separado en `Roadmap.md`.

## 2026-07-17 — `20260717_canonical_batch_tracking`

Revisión posterior a `c923732e1cab`. Agrega `canonical_batch_jobs` y `canonical_batch_job_items` para persistir idempotencia, progreso y errores parciales del alta masiva canónica. La migración sincroniza `sku_sequences.next_seq` con los SKU históricos válidos antes de habilitar el generador transaccional común.

El downgrade elimina exclusivamente las dos tablas de seguimiento; no elimina productos canónicos ni retrocede secuencias. Antes del despliegue se debe aplicar la migración, luego actualizar API/worker y finalmente Vue. La prueba PostgreSQL de cadena limpia valida las tablas y asignaciones simultáneas del mismo prefijo.

Verificación local: upgrade del esquema de desarrollo aprobado, auditoría con 16 checks correctos y cadena limpia sobre PostgreSQL temporal aprobada, incluyendo 12 asignaciones concurrentes sin SKU duplicados.

## 2026-07-17 — `c923732e1cab` historial de precios sin archivo

La confirmación de una compra validada fallaba con HTTP 409 después de preparar stock y productos porque PostgreSQL conservaba `supplier_price_history.file_fk NOT NULL`, mientras el modelo ya permitía `NULL` y la confirmación registra historial por `purchase_id`/`purchase_line_id` sin archivo de proveedor.

- `upgrade()` cambia exclusivamente `supplier_price_history.file_fk` a nullable y es idempotente.
- `downgrade()` restaura `NOT NULL` sólo si no existen filas sin archivo; en caso contrario aborta con un mensaje accionable para evitar pérdida de trazabilidad.
- La prueba PostgreSQL de cadena limpia verifica la nulabilidad y espera el nuevo head.
- `scripts/audit_schema.py` audita este contrato y carga `.env` cuando no se pasa `--url`.
- `scripts/check_schema.py` anonimiza la contraseña de `DB_URL`.

Verificación local: 13 pruebas Python aprobadas, 1 integración PostgreSQL opt-in omitida, 32 pruebas Vue aprobadas, build Vue aprobado, migración aplicada y auditoría PostgreSQL con 11 checks correctos.

## 2026-07-16 — `20260716_purchase_ingestion_v2`

Revisión posterior a `20260714_schema_integrity`. Agrega metadatos documentales a compras y adjuntos, importes/confianza por línea, referencias de compra en historial de precios e índices por producto/proveedor/fecha. Las FK históricas de `purchase_lines` cambian de `CASCADE` a `SET NULL` para preservar el remito ante una baja de catálogo.

No recalcula stock ni crea movimientos para compras anteriores. Downgrade elimina las columnas nuevas y restaura las FK anteriores; antes de usarlo debe exportarse la trazabilidad nueva.

Verificación local: PostgreSQL alcanzó el head nuevo. `alembic check` continúa reportando drift histórico ajeno a esta revisión, principalmente en Mercado, defaults e índices legacy.

## 2026-07-14 — Cadena PostgreSQL completa desde base vacía

### Contexto

El primer arranque sobre PostgreSQL vacío fallaba en `cf0f6e70fe89_add_rag_knowledge_tables.py` con `psycopg.errors.UndefinedObject` al ejecutar `DROP INDEX ux_customers_document_number`. La revisión, aunque estaba nombrada como alta de tablas RAG, contenía cientos de operaciones autogeneradas ajenas al objetivo y potencialmente destructivas.

### Correcciones

- `cf0f6e70fe89` se conserva en el grafo como no-op documentado. No cambiaron su `revision`, `down_revision` ni el merge histórico.
- `b2d22a7ce889` permanece como implementación manual de `knowledge_sources` y `knowledge_chunks`.
- `fa50a5cba1bb` continúa fusionando ambas ramas.
- Se agregó `20260714_schema_integrity`, posterior a `a1b2c3d4e5f6`, para garantizar de forma idempotente:
  - índice único parcial `ux_customers_document_number`;
  - constraint `ck_returns_status`;
  - índice `ix_returns_created_at`.
- La migración de integridad valida duplicados de documentos y estados de devolución inválidos antes de crear objetos, con errores accionables en vez de alterar datos silenciosamente.
- `c308b8798a79` reemplazó símbolos Unicode decorativos por etiquetas ASCII para evitar `UnicodeEncodeError` bajo CP1252 en Windows.
- `scripts/audit_schema.py` ahora anonimiza la contraseña de `DB_URL` en su salida.

### Prueba automatizada

`tests/test_migrations_fresh_postgres.py` crea una base temporal con prefijo `growen_migration_test_`, habilita pgvector, ejecuta `alembic upgrade head`, verifica tablas RAG, head, índices y constraints, y elimina la base en `finally`.

```powershell
$env:MIGRATION_TEST_POSTGRES_URL="postgresql+psycopg://<usuario>:<password>@127.0.0.1:5433/growen"
.\.venv\Scripts\python.exe -m pytest tests/test_migrations_fresh_postgres.py -v -p no:randomly
```

No incorporar esa URL al repositorio; debe provenir del entorno local o de secretos de CI.

### Resultado verificado

- Test sobre base temporal vacía: aprobado.
- Base local vacía migrada con `alembic upgrade head`: aprobada.
- Único head y revisión actual: `20260714_schema_integrity`.
- Tablas públicas resultantes: 53.
- `scripts/audit_schema.py`: 10 checks, sin objetos faltantes.

### 2025-09-27 Unificación fallback admin

Se unificó el fallback de password del usuario `admin` a `admin1234` en:
- Migración `20241105_auth_roles_sessions.py` (anteriormente mencionaba `admin123`).
- Script `scripts/seed_admin.py` (ya usaba `admin1234`).
- Configuración `agent_core.config.Settings` (antes `dev-admin-pass`).

Motivo: eliminar confusión que causaba intentos de login fallidos según qué componente hubiese creado el usuario primero. El fallback solo aplica en entorno `dev` cuando `ADMIN_PASS` mantiene el placeholder `REEMPLAZAR_ADMIN_PASS`. En otros entornos el arranque falla explícitamente.

Acción recomendada: definir siempre `ADMIN_PASS` explícito en `.env` para evitar dependencia de contraseñas públicas de desarrollo.

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

## Oct 2025 — Nueva columna products.is_enriching

- Se agregó la migración `20251025_add_products_is_enriching` que introduce la columna `products.is_enriching BOOLEAN NOT NULL DEFAULT false`.
- Motivo: el modelo `db.models.Product` ya exponía el campo, y endpoints de catálogo lo seleccionaban en queries. Sin la columna, `/products` devolvía 500 (`UndefinedColumn`).
- Acción: ejecutar `alembic upgrade head` contra la base del stack Docker (ver `.env` → `DB_URL=postgresql+psycopg://...@127.0.0.1:5433/growen`).
- Nota: la migración incluye guardas `information_schema` para evitar error si la columna ya existiera.

## Sept 2025 — Índices de rendimiento

- Se añadió la migración `20250922_supplier_products_internal_variant_idx` que crea `ix_supplier_products_internal_variant_id`.
- Motivo: acelerar lookups y vinculaciones por `internal_variant_id` durante importaciones y operaciones masivas.
- La migración usa utilidades idempotentes (`has_column`, `index_exists`) para evitar errores si ya existía.

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

## 2025-09-26 `20250926_add_purchase_line_meta`

Se agrega columna `meta` (JSON nullable) a `purchase_lines` para almacenar trazabilidad de autocompletado:

- Snapshot único `meta.enrichment` por ejecución (se sobreescribe).
- Incluye: `algorithm_version`, `timestamp`, `fields` modificados (con `original`) y estadísticas agregadas (`with_outlier`, `price_enriched`).
- No requiere backfill; en downgrade simplemente se elimina la columna.

Motivación: habilitar UI para resaltar campos enriquecidos y permitir auditoría mínima sin inspeccionar logs.

## 2025-09-26 `20250926_stock_ledger_and_sales_indexes`

Cambios introducidos para el módulo Ventas / Clientes:

- Creación de tabla `stock_ledger` (movimientos de inventario):
  - Campos: id, product_id, source_type (sale|return|annul), source_id, delta (int, positivo=ingresa, negativo=egresa), balance_after, created_at (timezone aware ideal futuro), meta (JSON con referencias ej. sale_line_id).
  - Uso: registrar decrementos al confirmar ventas y aumentos al anular o registrar devoluciones.
- Índices de rendimiento agregados:
  - `ix_sales_sale_date` para filtros por fecha en listados y reportes.
  - `ix_sales_customer_id` para historial por cliente.
  - `ix_sale_lines_product_id` para agregados por producto / reportes top-products.
  - `ix_returns_created_at` y `ix_return_lines_product_id` para consultas de devoluciones y neteo futuro.
- Índice único parcial (PostgreSQL) sobre `customers(document_number)` ignorando NULL, garantizando unicidad sólo cuando el documento se informa.
  - En motores sin soporte (ej. SQLite) crea índice normal no único y la validación recae en capa aplicación.
- Persistencia de campos por línea de venta `subtotal`, `tax`, `total` para acelerar reportes (desnormalización controlada).
- Lógica de confirmación ahora:
  - Recalcula totales.
  - Bloquea (HTTP 409) si existen líneas con estado `SIN_VINCULAR`.
  - Registra movimiento negativo en `stock_ledger` por cada línea.
- Anulación de venta invalida cache de reportes (antes sólo confirmaciones / devoluciones lo hacían).
- Rate limiting (30/min) para POST /sales introducido (no afecta schema, se documenta por impacto operativo).

Notas de compatibilidad:
- Si existían ventas previas sin `subtotal/tax/total` en líneas, se rellenarán al tocar `_recalc_totals` (confirmación, patch o línea agregada). No se fuerza backfill inmediato.
- Para entornos multi-worker se recomienda mover ledger + cache a backend compartido (Redis / DB transaccional).

Downgrade:
- Eliminar tabla `stock_ledger` y los índices agregados.
- NOTA: Perderá histórico de movimientos; considerar export previo si se requiere auditoría.

---

## 2025-09-27 Hotfix Idempotencia (stock_ledger, returns, sales)

### Contexto
Se detectó un estado histórico inconsistente con múltiples migraciones duplicadas / variantes para `stock_ledger` y luego errores en cadena al aplicar `alembic upgrade head`:

- `DuplicateTable` en `stock_ledger` (v2 vs variantes previas marcadas luego como deprecated).
- `DuplicateTable` en `returns` (la tabla ya existía por ejecución previa parcial).
- `DuplicateColumn` en `sales.sale_kind` (columna ya aplicada en un ciclo anterior).

Objetivo: permitir que la base alcance el head sin intervención manual, preservando datos existentes.

### Acciones aplicadas
1. Migración `20250926_stock_ledger_and_sales_indexes_v2.py` modificada para ser idempotente:
  - Inspección previa de tablas e índices mediante `sa.inspect`.
  - Creación condicional de cada índice (`try/except` defensivo) y del índice parcial único en `customers` (usa `IF NOT EXISTS` en PostgreSQL, índice simple fallback en otros motores).
2. Migración `20250926_returns_module.py` ajustada con:
  - Early noop si `returns` y `return_lines` ya existen (evita transacción abortada por duplicados).
  - Creación condicional de tablas, índices y constraint `ck_returns_status` (envoltura `try/except`).
3. Se identificó siguiente bloqueo (`DuplicateColumn` en `20250926_add_sale_kind_and_line_idx.py`), pendiente de idempotentizar (ver Próximos pasos).

### Riesgos / Consideraciones
- El early noop de `returns_module` no reconstruye el constraint `ck_returns_status` si faltara; se recomienda verificación posterior (`pg_catalog.pg_constraint`).
- Estos parches reducen la señal de errores “reales” porque silencian duplicados; mitigación: agregar script de auditoría de integridad de migraciones.
- Downgrade de las migraciones parchadas permanece best-effort; en escenarios mixtos podría dejar residuos si ya existían objetos parcialmente.

### Próximos pasos recomendados
1. Idempotentizar `20250926_add_sale_kind_and_line_idx.py` (verificar existencia de columna `sale_kind` y índice en `sale_lines.product_id`).
2. Agregar script `scripts/audit_schema.py` que valide:
  - Presencia de constraints claves (`ck_returns_status`).
  - Índices esperados de performance (`ix_stock_ledger_*`, `ix_returns_*`).
3. Documentar convención: nuevas migraciones deben usar helpers de inspección antes de crear tablas/índices/columnas.
4. Evaluar migración de consolidación futura que marque rutas deprecated y deje un único head lineal limpio.

### Notas operativas
- Entornos ya “medio migrados” pueden ahora completar el upgrade sin necesidad de borrar la base.
- Si se requiere limpieza total: drop schema + recrear + correr todas las migraciones en un entorno aislado y comparar salida de `scripts/check_schema.py` para detectar divergencias.

### Relación con SKU Canónico
Este hotfix fue habilitador para continuar con la nueva lógica de SKU canónico (tabla `sku_sequences` + generación transaccional). Sin resolver los duplicados de ledger/returns no era posible validar las pruebas de creación de productos canónicos.

#### Notas adicionales (2025-09-27)
- En entorno SQLite (tests) se incorporó creación perezosa de `sku_sequences` dentro del generador para evitar fallos en bases recién inicializadas.
- Se añadió un `commit` explícito tras incrementar la secuencia para reducir incidencia de `database is locked` en ejecuciones rápidas y paralelas.
- `tests/conftest.py` asegura (si falta) la columna `canonical_sku` y la tabla de secuencias, brindando paridad aproximada con PostgreSQL para el set de pruebas.

---
Actualizado: 2025-09-27

## Plan de consolidación futura (Squash / Cleanup)

Motivación:
- Historial reciente incorporó migraciones parcheadas e inutilizadas ("deprecated") para resolver divergencias (`stock_ledger` variantes, noop returns, etc.). Mantenerlas a largo plazo aumenta ruido y tiempo de revisión.

Objetivo del plan (no ejecutado todavía):
1. Crear rama de mantenimiento `migrations-consolidation`.
2. Generar un snapshot único del esquema actual en una migración nueva `YYYYMMDD_consolidated_base` que re-crea (create_all style) sólo las estructuras vigentes.
3. Marcar todas las migraciones previas a la consolidación como congeladas (sin edits futuros). Documentar SHA final.
4. Incluir en la migración consolidada helpers idempotentes (pattern usado en hotfix) para permitir reinstalación limpia sobre entornos con restos parciales.
5. Probar en entorno fresco:
  - a) `alembic upgrade head` sobre DB vacía.
  - b) Restaurar dump de producción previa al squash + aplicar cadena (conservando historial viejo) → validar que no se rompe.
6. Publicar guía de transición: quienes tengan clones antiguos pueden:
  - Opción A: hacer checkout, terminar de migrar al último head pre-consolidación y luego aplicar la nueva migración merge.
  - Opción B: recrear schema desde cero y reimportar datos (dev only).

Consideraciones técnicas:
- Alembic no recomienda borrar historia; la consolidación se hará agregando una migración que conceptualmente reemplaza a muchas, y un merge para cerrar ramas antiguas.
- No se eliminarán archivos históricos de inmediato; se evaluará archivarlos bajo `db/migrations/_legacy/` tras dos ciclos de releases estables.
- Se añadirá script `scripts/compare_schema_snapshot.py` (pendiente) para asegurar que `Base.metadata` == estado DB después del upgrade consolidado.

Riesgos:

---

## 2025-10-21 — Enriquecimiento IA (fuentes, campos técnicos y trazabilidad)

Se incorporaron tres migraciones nuevas para soportar el flujo de enriquecimiento de productos:

- `20251021_add_product_enrichment_sources.py`: agrega `products.enrichment_sources_url` (String(600), nullable) para exponer la URL pública de un `.txt` con fuentes consultadas por la IA.
- `20251021_add_product_technical_fields.py`: agrega campos técnicos editables en `products` (`weight_kg Numeric(10,3)`, `height_cm/width_cm/depth_cm Numeric(10,2)`, `market_price_reference Numeric(12,2)`).
- `20251021_add_product_enrichment_trace.py`: agrega metadatos de trazabilidad `last_enriched_at DateTime` y `enriched_by Integer (FK users.id ondelete=SET NULL)`.

Consideraciones:
- En entornos de pruebas con SQLite en memoria compartida, se añadió un hotfix en `db/session.py` que verifica columnas y las crea en caliente si la tabla `products` ya existía sin ellas (evita fallos intermitentes al reutilizar el mismo `:memory:` compartido entre tests).
- Los endpoints de enriquecimiento (single, bulk y delete) se apoyan en estas columnas; si la DB no está migrada, las rutas pueden fallar. Asegurar `alembic upgrade head` en despliegues.

Downgrade:
- Cada migración elimina sus columnas respectivas en `downgrade()`. Eliminar `enriched_by` primero remueve el FK (`fk_products_enriched_by_users`).
- Inconsistencias silenciosas si el snapshot omite constraints específicos agregados en parches intermedios (mitigar con auditoría previa y diff db reflection vs metadata).
- Pipelines que referencian revisiones antiguas podrían necesitar update.

Next steps (tracking):
- [ ] Crear script de diff metadata vs live DB.

---

## 2025-09-27 Consolidación inicial (snapshot)

Se agregó la migración `20250927_consolidated_base` que actúa como snapshot del estado estable posterior a la serie de hotfixes e introducción de `sku_sequences` y `canonical_sku`.

Características:
- Usa `Base.metadata.create_all` de forma idempotente (early exit si `products` ya existe) para permitir recreación limpia en una base vacía.
- No elimina migraciones históricas: se mantienen para trazabilidad y auditoría. Esta migración se apoya en `down_revision = 20250927_merge_deprecated_stock_ledger_heads`.
- `downgrade()` es noop para evitar pérdidas de datos (documentado explícitamente).

Riesgos / Consideraciones:
- Si el metadata incluye tablas legacy que deberían excluirse, el snapshot podría reintroducirlas; revisar antes de ampliar modelos.
- Cambios futuros en modelos requieren nuevas migraciones incrementales; no modificar el snapshot retroactivamente.

Próximos pasos tras snapshot:
- Implementar script `scripts/compare_schema_snapshot.py` (pendiente) para validar que una base obtenida vía cadena histórica == base creada directo desde snapshot.
- Evaluar archivado de migraciones deprecated bajo `db/migrations/_legacy/` cuando haya pasado un ciclo estable.

Estado: Primera consolidación creada y aplicada en entorno local.
- [ ] Generar migración snapshot.
- [ ] Ensayar restore + upgrade.

Se documentará progreso en esta sección cuando inicie la rama de consolidación.

---

## 2025-10-10 Migración Postgres 15 → 17.6 (Windows/Docker) — Ejecución real

Contexto: se detectó que el contenedor de Postgres 17.6 no podía iniciar con el volumen inicializado en Postgres 15. Se ejecutó la Opción A (conservar datos) con backup crudo + dump lógico y restauración en 17.6.

Pasos ejecutados (Windows PowerShell + Docker):

- Backup crudo del volumen `growen_pgdata` a `backups/pg/raw-YYYYMMDD-HHMMSS/pgdata.tar` (uso de `alpine:3.19` con `tar`).
- Dump lógico con el contenedor PostgreSQL vigente usando `pg_dump -Fc`:
  - Artefacto resultante verificado en: `backups/pg/raw-20251010-113335/growen_15.dump` (≈190 KB).
- Limpieza de referencias y recreación del volumen:
  - Se eliminaron contenedores que referenciaban el volumen y luego `docker volume rm growen_pgdata`.
  - `docker compose up -d db` (imagen 17.6) para crear volumen limpio y validar health.
- Restauración en PG17.6:
  - Copia del dump al contenedor: `/tmp/growen_15.dump`.
  - `createdb` y `pg_restore -c --no-owner --no-privileges -d growen /tmp/growen_15.dump`.
  - Nota: `pg_restore` imprimió múltiples mensajes "relation ... does not exist" al limpiar (esperable con `-c` en DB recién creada). La restauración completó y el listado `\dt` mostró 45 tablas en `public`.
- Migraciones Alembic:
  - `alembic current` → `20250927_consolidated_base`.
  - `alembic upgrade head` → ya en HEAD, sin cambios pendientes.

Verificaciones clave:

- Postgres dentro del contenedor: `SELECT version()` → `PostgreSQL 17.6`.
- Tabla `alembic_version.version_num` = `20250927_consolidated_base` (coincide con HEAD).
- API: `/health` respondió `{"status":"ok"}` en `http://127.0.0.1:8000/health`.
- Frontend: HTTP 200 en `http://127.0.0.1:5173`.

Notas y consideraciones:

- Los artefactos del backup (crudo y lógico) se conservan bajo `backups/pg/raw-YYYYMMDD-HHMMSS/` para auditoría y eventual rollback.
- Los mensajes "does not exist" de `pg_restore` ocurren al pasar `-c` (clean); se podrían atenuar con `--if-exists`, pero no impidieron la restauración completa.
- Se validó que la variable `alembic_version` tenga `VARCHAR(255)` y que el `env.py` cargue `.env` con `override=True`, mitigando issues históricos documentados en esta página.

## Revisión `20260717_sales_customers_v4`

La revisión es incremental sobre `20260717_canonical_batch_tracking`. Convierte cantidades y stock a `Numeric(14,2)`, agrega costos adicionales persistidos, idempotencia, límite de crédito, snapshots de costo, `stock_reservations` y `customer_account_entries`.

El upgrade conserva los valores existentes y reconstruye la cuenta corriente desde ventas confirmadas/entregadas, pagos y devoluciones. El downgrade aborta si existen datos Fase 4 o cantidades fraccionarias, evitando truncamiento silencioso. Verificar con `alembic heads`, upgrade limpio y upgrade incremental en PostgreSQL antes del despliegue.

Checklist de cierre:

- [x] DB en 17.6, volumen recreado limpio.
- [x] `pg_restore` aplicado, 45 tablas presentes.
- [x] Alembic en HEAD.
- [x] API healthy y Frontend accesible.

Acciones sugeridas post‐migración:

- Ejecutar `scripts/check_admin_user.py` para confirmar usuario admin.
- Opcional: `DISABLE_AUTO_BACKUP=1` en `.env` si no se desea backup automático en dev (ver `docs/BACKUPS.md`).
- Conservar los archivos en `backups/pg/` fuera del repo (almacenamiento seguro) según política.
