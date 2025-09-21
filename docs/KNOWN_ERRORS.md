<!-- NG-HEADER: Nombre de archivo: KNOWN_ERRORS.md -->
<!-- NG-HEADER: Ubicación: docs/KNOWN_ERRORS.md -->
<!-- NG-HEADER: Descripción: Catálogo y guía de patrones de errores conocidos para sincronizar con Notion -->
<!-- NG-HEADER: Lineamientos: Ver AGENTS.md -->

# Errores conocidos — Catálogo y sincronización

Este documento describe cómo mantener el catálogo de errores conocidos y sincronizarlo con la base de Notion "Todos Errores".

## Archivo de catálogo

- Ruta: `config/known_errors.json`
- Estructura:
  - `version`: número entero para referencia
  - `patterns`: lista de objetos con campos:
    - `id` (string, único)
    - `regex` (string, expresión regular para match, IGNORECASE)
    - `servicio` (string, ej. `api`, `frontend`, `worker_images`)
    - `severidad` (Low | Medium | High | Critical)
    - `etiquetas` (array de strings)
    - `titulo` (string, título sugerido)
    - `sugerencia` (string opcional)

Ejemplo mínimo:

- `db-unique-violation`: duplicate key value violates unique constraint

## Sincronización con Notion

1. Variables en `.env`:
   - `NOTION_FEATURE_ENABLED=true`
   - `NOTION_API_KEY=...`
   - `NOTION_ERRORS_DATABASE_ID=...` (ID de la base "Todos Errores")
   - `NOTION_DRY_RUN=0` (para crear páginas reales)
2. Ejecutar CLI:
   - `python -m cli.ng notion sync-known-errors --dry-run` (previsualiza)
   - `python -m cli.ng notion sync-known-errors` (aplica)

La sincronización es idempotente: usa un fingerprint derivado del `id` del patrón para crear o actualizar la tarjeta.

## Propiedades esperadas en Notion

En la base "Todos Errores", crear propiedades:
- Title (title), Estado (select), Severidad (select), Servicio (select), Entorno (select), Sección (select),
- Fingerprint (rich_text), Mensaje (rich_text), Código (rich_text), URL (url),
- FirstSeen (date), LastSeen (date), Etiquetas (multi_select), Stacktrace (rich_text), CorrelationId (rich_text)

Sección admite: Compras | Stock | Productos | General. Ajustar nombres en el código si difieren.

## Buenas prácticas

- Mantener patrones lo más específicos posible (evitar falsos positivos).
- Documentar en `sugerencia` un hint de resolución (en español).
- Validar con `--dry-run` antes de publicar.
