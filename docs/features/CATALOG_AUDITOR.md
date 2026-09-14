<!-- NG-HEADER: Nombre de archivo: CATALOG_AUDITOR.md -->
<!-- NG-HEADER: Ubicación: docs/features/CATALOG_AUDITOR.md -->
<!-- NG-HEADER: Descripción: Arquitectura, operación y resolución del auditor autónomo de catálogo. -->
<!-- NG-HEADER: Lineamientos: Ver AGENTS.md -->

# Auditor autónomo de catálogo

## Alcance y separación de dominios

El auditor se inicia desde `/admin/auditor-catalogo` o desde una selección de
`/productos`. Es asíncrono, persistente y usa la cola Dramatiq
`catalog_audit`; no forma parte de Enrich ni condiciona su aplicación. Enrich
mantiene su prioridad OpenAI → Ollama y el auditor sólo crea un job Enrich
idempotente cuando el canónico no contiene descripción, datos técnicos,
instrucciones ni magnitudes auditables y la ejecución habilitó
`enrich_missing`.

La identidad combina contenido normalizado, nombre, marca, taxonomía, versión
de reglas y versión del feedback aplicable. Un resultado terminal con la misma
identidad genera `skipped_unchanged` y no vuelve a ejecutar reglas ni Ollama.

## Estados y tratamientos

Los runs recorren `queued → running → waiting_enrich` y terminan en
`completed`, `completed_with_issues`, `failed` o `cancelled`. Sólo puede existir
un run global activo. Los tratamientos son:

- `canonical_required`: abrir Productos y canonizar el interno huérfano.
- `waiting_enrich`: seguir el job Enrich asociado; nunca se crea otro job activo.
- `needs_review`: editar, reauditar, corregir clasificación o aceptar excepción.
- `quarantined`: corregir/restaurar o liberar con motivo administrativo.
- `failed`: reintentar el ítem o reanudar el run.
- `clean`, `auto_fixed` y `skipped_unchanged`: consultar evidencia e historial.

Los canónicos en cuarentena no participan de catálogos públicos ni de las
exportaciones de stock. El listado staff conserva el indicador de auditoría.

## Reglas, modelo local y autocorrección

Primero se clasifica como líquido, sustrato, contenedor, carpa, producto por
peso u otro. Una unidad de volumen no basta para tratar un contenedor como
líquido: `Maceta Soplada 20L` es una regresión automatizada. Las correcciones de
clasificación y excepciones generan feedback versionado.

El modo completo usa el cliente local exclusivo del auditor con
`llama3.1:8b`, temperatura `0`, contexto `4096`, salida máxima `2048`, schema
JSON y concurrencia operativa uno. Daemon, modelo, HTTP, JSON o schema inválidos
fallan cerrado. No se guardan prompts completos.

La autocorrección sólo está disponible para admin y exige auditoría
determinista aprobada, confianza mínima `0,95`, dos dominios de evidencia y
CAS de `content_revision`. Nunca modifica precio, stock, identidad o SKU. Crea
snapshots `catalog_audit_pre_fix` y `catalog_audit_auto_fix`, reaudita una vez y
pone en cuarentena un error crítico persistente; no hay rollback automático.

## API y operación local

- `POST/GET /canonical-products/catalog-audits`
- `GET /canonical-products/catalog-audits/preflight`
- `GET /canonical-products/catalog-audits/{run_id}`
- `POST .../{run_id}/cancel|retry`
- `POST .../{run_id}/items/{item_id}/resolve`

`GET /canonical-products/catalog-audit-report` lee el último run persistido y
nunca inicia trabajo.

```powershell
.\scripts\start-dev.ps1 -McpMode All -WithEnrichmentWorker -WithCatalogAuditWorker
```

El worker también se inicia con `scripts\start_worker_catalog_audit.cmd`.
Validar `/health/catalog-audit-worker`, Redis, el heartbeat de Enrich si se
habilita contenido faltante y Ollama desde la vista. Al iniciar, el proceso
reencola los runs persistidos que continúan activos; mensajes duplicados son
seguros porque cada ejecución vuelve a comprobar su slot y sus ítems.

El 2026-09-14 se aplicó `20260913_catalog_audit_v1` sobre el clon PostgreSQL local de
desarrollo y se reconstruyeron/recrearon ambos workers Compose. Sus healthchecks
y heartbeats quedaron saludables, las colas vacías y una evaluación sintética
del cliente estricto produjo JSON válido con `llama3.1:8b` cargado al 100 % en
GPU. No se inició el run de los 29 canónicos: debe ejecutarse desde la UI. El
despliegue Swarm y la alineación productiva permanecen fuera de este corte.
Compose fija el volumen `growen_dev_pgdata` y las redes `growen_dev_*`; el
volumen externo `growen_pgdata` y las redes overlay `growen_*` son exclusivos de
Swarm y no deben reutilizarse para esta operación local.
