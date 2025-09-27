<!-- NG-HEADER: Nombre de archivo: CANONICAL_SKU.md -->
<!-- NG-HEADER: Ubicación: docs/CANONICAL_SKU.md -->
<!-- NG-HEADER: Descripción: Especificación de SKU canónico, flags, generación y pruebas -->
<!-- NG-HEADER: Lineamientos: Ver AGENTS.md -->

# SKU Canónico (Especificación y Guía)

## Contexto
El proyecto adopta un formato **canónico obligatorio** para los SKUs internos de productos con el objetivo de:

- Unificar criterios de búsqueda y deduplicación.
- Habilitar generación automática consistente por categoría/subcategoría.
- Reducir conflictos históricos de SKUs arbitrarios (`INT-xxxx`, variaciones libres, etc.).
- Facilitar una futura consolidación de migraciones y auditorías de integridad.

## Formato
Regex formal:
```
^[A-Z]{3}_[0-9]{4}_[A-Z0-9]{3}$
```

Estructura: `PPP_NNNN_SSS`
- `PPP`: Prefijo de 3 letras derivado de `category_name` normalizado.
- `NNNN`: Secuencia incremental (relleno con ceros a 4 dígitos) aislada por prefijo.
- `SSS`: Sufijo de 3 caracteres alfanuméricos derivado de `subcategory_name` (o la categoría si no se provee subcategoría).

Ejemplos válidos:
- `FLO_0001_FER`
- `FLO_0002_FLO` (cuando subcategoría se omite y se replica categoría)
- `NEU_0123_GRO`

Ejemplos inválidos (y motivo):
- `AB_0001_DEF` (prefijo < 3 letras)
- `ABCD_0001_DEF` (prefijo > 3 letras)
- `ABC_001_DEF` (número con menos de 4 dígitos)
- `ABC_0001_DEFG` (sufijo > 3 caracteres)
- `ABC0001DEF` (faltan guiones bajos separadores)

## Flags / Variables de entorno
| Variable | Default | Descripción |
|---------|---------|-------------|
| `CANONICAL_SKU_STRICT` | `1` | Si está activa se exige que `sku` cumpla el patrón cuando se envía explícitamente. |
| `FORCE_CANONICAL` | `0` | Si se activa fuerza generación canónica ignorando un SKU suministrado (para migraciones masivas). |

## Flujo de creación de producto
1. El cliente puede enviar un campo `sku` ya canónico que pase validación.
2. Alternativamente puede solicitar generación automática enviando `generate_canonical = true` junto con:
   - `category_name` (obligatorio para generar).
   - `subcategory_name` (opcional; si falta se reutiliza la categoría para el sufijo).
3. El backend normaliza `category_name` / `subcategory_name` a códigos de 3 caracteres ([A-Z0-9], rellenando o truncando según helper `normalize_code`).
4. Se obtiene / crea fila de secuencia en tabla `sku_sequences` para el prefijo.
5. Se incrementa de forma transaccional y se compone el SKU final.
6. Se persiste en `products.canonical_sku` (columna canónica) y/o se usa como `sku_root` en la respuesta.

## Tabla de secuencias: `sku_sequences`
Campos mínimos:
- `prefix` (PK)
- `current_value` (int)

Garantiza aislamiento por categoría (prefijo). La lógica de incremento:
1. Se selecciona la fila con bloqueo (`SELECT ... FOR UPDATE` en PostgreSQL; en SQLite el bloqueo es a nivel de DB/tabla y se simplifica la semántica).
2. Se incrementa `current_value` y se confirma la transacción.

### Consideraciones de concurrencia
- PostgreSQL: uso de transacciones cortas; ideal mantener operaciones dependientes fuera de la misma transacción para reducir contención si se escala.
- SQLite (entorno de pruebas): los locks eran causa de errores `database is locked`; se mitigó con un `commit` inmediato tras el incremento (ver implementación en `db/sku_generator.py`).

## Fallback / Entorno SQLite
Durante pruebas (SQLite) puede ocurrir que la columna `canonical_sku` o la tabla `sku_sequences` aún no existan (DB limpia). Se implementó:
- Creación perezosa (`CREATE TABLE IF NOT EXISTS`) dentro del generador para `sku_sequences`.
- Ajuste en `tests/conftest.py` que asegura la columna y tabla antes de correr casos.

Esto evita divergencias entre entorno de CI y el esquema objetivo (PostgreSQL).

## Validación y errores
Respuestas esperadas al crear producto:
- 200 / 201: creación (o vinculación si el SKU ya existe con otro supplier y se permite linking).
- 409: conflicto (`duplicate_sku` o `duplicate_supplier_sku`).
- 400: falta `category_name` cuando se solicitó generación (`missing_category_name`).
- 422: formato de SKU inválido en modo estricto.

## Lineamientos para pruebas
1. Usar siempre formato canónico en nuevos tests; evitar patrones legacy (`INT-xxxx`).
2. Para probar duplicados: generar un SKU válido y reenviar exactamente el mismo payload verificando 409.
3. Para aislar secuencias por prefijo: crear productos con categorías distintas y comprobar que los números empiezan en `0001` por prefijo.
4. Evitar dependencias en valores absolutos de secuencia entre tests (riesgo de orden no determinista). Generar valores dinámicos usando categorías únicas si se requiere independencia.
5. Si se necesita cubrir comportamiento pre-consolidación, marcar el test con `@pytest.mark.legacy` y documentar su fecha de retiro planificada.

## Auditoría
El script `scripts/audit_schema.py` valida presencia (o salta en SQLite) de objetos clave. Se recomienda extenderlo para:
- Confirmar existencia de `products.canonical_sku`.
- Confirmar integridad de índices asociados si se agregan (futuro: índice único parcial si aplica).

## Migraciones y consolidación
Se planificó una migración de consolidación que capture el estado estable posterior a la introducción de `sku_sequences` (ver `docs/MIGRATIONS_NOTES.md` sección "Plan de consolidación futura").

## Ejemplos de uso (API)
Crear con SKU explícito válido:
```
POST /catalog/products
{
  "title": "Fertilizante Floración",
  "initial_stock": 5,
  "supplier_id": 1,
  "supplier_sku": "SUP-FLO-01",
  "sku": "FLO_0001_FER"
}
```

Generación automática:
```
POST /catalog/products
{
  "title": "Fertilizante Multipropósito",
  "initial_stock": 0,
  "supplier_id": 1,
  "supplier_sku": "SUP-FLO-02",
  "generate_canonical": true,
  "category_name": "Floración",
  "subcategory_name": "Fertilizantes"
}
```

## Próximos pasos sugeridos
- Índice único en `products.canonical_sku` (si aún no se agregó) garantizando consistencia.
- Endpoint de introspección `/admin/sku/sequences` para monitoreo (opcional).
- Script de backfill para productos legacy sin valor canónico (si existieran).

## Criterios de aceptación (para cambios futuros relacionados)
1. Toda nueva ruta que cree productos debe respetar/generar SKU canónico.
2. Las pruebas no deben depender de secuencias absolutas globales.
3. Documentación (`CANONICAL_SKU.md`, `README.md`) actualizada ante cualquier ajuste de formato/flags.
4. Auditoría (`audit_schema.py`) extendida si se agregan nuevos constraints o índices.

---
Actualizado: 2025-09-27
