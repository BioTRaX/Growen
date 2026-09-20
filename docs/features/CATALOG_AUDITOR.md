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
La tabla del auditor presenta `canonical_name` como identidad principal y el
ID canónico como referencia secundaria. `product_detail_id` apunta al menor
`Product.id` interno vinculado por equivalencia y habilita la navegación a la
ficha; cuando no existe vínculo la UI informa **Sin ficha interna vinculada** y
no construye una URL con el ID canónico.

En `/productos`, un administrador puede usar **Aceptar revisión** sobre un
`needs_review` que conserve `catalog_audit_run_id` y
`catalog_audit_item_id`. La acción exige una nota de al menos tres caracteres,
invoca `accept_exception` y deja el producto en `clean` con usuario, fecha y
feedback trazables. No aplica correcciones propuestas por IA ni inicia una
reauditoría. Los colaboradores no ven la acción y el backend responde 403 si
intentan invocarla directamente.

## Reglas, modelo local y autocorrección

Primero se clasifica como líquido, sustrato, contenedor, carpa, producto por
peso u otro. Una unidad de volumen no basta para tratar un contenedor como
líquido: `Maceta Soplada 20L` es una regresión automatizada. Las correcciones de
clasificación y excepciones generan feedback versionado.

El modo completo usa el cliente local exclusivo del auditor con
`llama3.1:8b`, temperatura `0`, contexto `4096`, salida máxima `2048`, schema
JSON y concurrencia operativa uno. Daemon, modelo, HTTP, JSON o schema inválidos
fallan cerrado. Una respuesta que no sea JSON se reintenta una sola vez; un
segundo resultado inválido conserva `invalid_json` y exige intervención. No se
guardan prompts completos.

La autocorrección sólo está disponible para admin y exige auditoría
determinista aprobada, confianza mínima `0,95`, dos dominios de evidencia y
CAS de `content_revision`. Nunca modifica precio, stock, identidad o SKU. Crea
snapshots `catalog_audit_pre_fix` y `catalog_audit_auto_fix`, reaudita una vez y
pone en cuarentena un error crítico persistente; no hay rollback automático.

## API y operación local

- `POST/GET /canonical-products/catalog-audits`
- `GET /canonical-products/catalog-audits/preflight`
- `GET /canonical-products/catalog-audits/summary`
- `GET /canonical-products/catalog-audits/{run_id}`
- `POST .../{run_id}/cancel|retry`
- `POST .../{run_id}/items/{item_id}/resolve`

El detalle de una corrida agrega por ítem `canonical_name` y
`product_detail_id`. `GET /products` agrega
`catalog_audit_run_id`/`catalog_audit_item_id` desde el puntero persistido al
último ítem. Ambos contratos se resuelven con consultas agrupadas, sin una
consulta adicional por fila.

`GET /canonical-products/catalog-audit-report` lee el último run persistido y
nunca inicia trabajo.

El endpoint `summary` es de monitoreo ligero: no ejecuta el preflight de Ollama
ni inicia trabajo. Devuelve estado del runtime, disponibilidad de Redis,
mensajes listos/programados, runs agrupados por estado, estados de ítems,
cobertura y los diez runs más recientes. Lo consumen el Dashboard técnico y el
detalle de `catalog_audit_worker` en Workers.
El worker confirma `running` y `auditing` antes de llamar a Ollama para que el
progreso de una evaluación larga sea observable desde otra sesión.

Las rutas del auditor se registran antes de
`/canonical-products/{canonical_id}`. Esta precedencia es parte del contrato:
evita que `catalog-audits`, `preflight` o `summary` se validen erróneamente como
identificadores enteros.

```powershell
.\scripts\start-dev.ps1 -McpMode All -WithEnrichmentWorker -WithCatalogAuditWorker
```

El worker también se inicia con `scripts\start_worker_catalog_audit.cmd`.
Validar `/health/catalog-audit-worker`, Redis, el heartbeat de Enrich si se
habilita contenido faltante y Ollama desde la vista. Al iniciar, el proceso
reencola los runs persistidos que continúan activos; mensajes duplicados son
seguros porque cada ejecución vuelve a comprobar su slot y sus ítems.
Al reanudar un run terminado sólo vuelven a `pending` los ítems `failed` o
`cancelled`; se elimina su referencia al job Enrich fallido, se recalculan los
contadores y cada nuevo intento usa una clave de solicitud distinta. Un job
Enrich `review_required` sin campos aplicables se clasifica como
`needs_review`, no como fallo técnico.
La clave Enrich incorpora el número persistido de intento: cambia después de
un fallo, pero permanece determinista ante redelivery concurrente del mismo
mensaje.
En Windows el módulo instala `WindowsSelectorEventLoopPolicy` antes de crear
sesiones Psycopg; sin esa política el broker puede consumir el mensaje mientras
el run permanece `queued` por incompatibilidad del event loop.

El smoke Dev del 2026-09-14 verificó login real, inicio y segundo inicio `noop`,
health, resumen a través del proxy Vue y un run del canónico 3 con transición
`queued → running → completed`. El resultado fue `clean`, clase `container` y
score 100. Una repetición sin cambios terminó `skipped_unchanged` y referenció
el primer ítem, sin volver a auditar el contenido. El run global continúa como
acción explícita desde la UI.

En desarrollo, Administración → Workers usa siempre ese launcher local para
`catalog_audit_worker`; no ejecuta Compose. El estado combina el árbol Dramatiq
y el heartbeat: master e hijos cuentan como una sola instancia. La respuesta
expone modo, PID y raíz. Un consumidor de otro worktree o roots múltiples dejan
el servicio `degraded` y bloquean inicio y detención; un proceso propio con
heartbeat vencido también queda `degraded`, pero puede detenerse de forma
segura. El servicio Compose permanece sólo para integración explícita y no fija
`container_name`, por lo que proyectos y worktrees quedan aislados.

El 2026-09-14 se aplicó `20260913_catalog_audit_v1` sobre el clon PostgreSQL local de
desarrollo y se reconstruyeron/recrearon ambos workers Compose. Sus healthchecks
y heartbeats quedaron saludables, las colas vacías y una evaluación sintética
del cliente estricto produjo JSON válido con `llama3.1:8b` cargado al 100 % en
GPU. No se inició el run de los 29 canónicos: debe ejecutarse desde la UI. El
manifiesto Swarm declara el worker aislado con concurrencia uno y el secreto
externo `openai_api_key` para Enrich.

El despliegue productivo del 2026-09-14 validó la restauración del backup
`pre-catalog-audit-20260914-133328.dump` en una PostgreSQL aislada, aplicó la
fase `Migration` hasta `20260913_catalog_audit_v1` y luego la fase
`Application`. Los 18 servicios convergieron 1/1, el endpoint de health del
worker informó broker y heartbeat saludables, y una generación desde el
contenedor confirmó `llama3.1:8b` con contexto 4096 al 100 % GPU. El run de los
29 canónicos no se inició: continúa siendo una acción explícita desde la UI.
Compose fija el volumen `growen_dev_pgdata` y las redes `growen_dev_*`; el
volumen externo `growen_pgdata` y las redes overlay `growen_*` son exclusivos de
Swarm y no deben reutilizarse para esta operación local. Las advertencias que
indican que `growen_pgdata` o `growen_redis_data` conservan labels antiguos no
autorizan a recrearlos, relabelarlos ni eliminarlos: son volúmenes productivos
montados por Swarm.

## Piloto completo del 2026-09-17

Se ejecutó una auditoría real de los 29 canónicos en el entorno local con
Redis, Dramatiq, Enrich, MCP Web Search y Ollama. El run
`6934ff45cb834257bc558cc8090ca65a` terminó sin ítems fallidos: 18 `clean`, 10
`needs_review` y 1 `skipped_unchanged`. No aparecieron huérfanos ni
cuarentenas. Los diez hallazgos quedaron clasificados como revisión manual y no
se aplicó ninguna recomendación automática. Tras reconciliar el camino
`review_required`, el resumen persistido informa 29 auditados y 0 pendientes.

La primera repetición consolidó las fichas que Enrich había modificado durante
el run inicial: 10 se reutilizaron y 19 se reevaluaron. La repetición estable
final `f9e26158f46c48398a51d1a51bae1a2b` reutilizó los 29 resultados sin
duplicar jobs ni feedback: 19 quedaron `skipped_unchanged` y los 10 hallazgos
conservaron `needs_review`, su evidencia y el estado
`completed_with_issues`.

También se ejercitó una corrección sin cambio material y su restauración sobre
el canónico 11. Quedaron versiones `catalog_audit_pre_fix`,
`catalog_audit_manual_fix`, `catalog_audit_pre_restore` y
`catalog_audit_restore`, y la reauditoría posterior terminó trazada. Los
snapshots convierten `Decimal` a texto exacto antes de persistir JSONB; esto
evita el error 500 encontrado durante el primer intento sin modificar la huella
auditable.

El run real se creó con una sesión HTTP admin y CSRF contra el mismo endpoint
que consume Vue. El componente Vue ofrece **Reanudar fallidos** también cuando
el run terminó como `completed_with_issues`. El inicio de una nueva corrida
mediante clic autenticado se difirió expresamente hasta que ingresen productos
nuevos; no bloquea el cierre del piloto actual.

El 2026-09-20 se completó un smoke autenticado y aislado de las superficies de
lectura y resolución. Como admin, `/admin/auditor-catalogo` mostró los 29
canónicos con nombre legible y enlaces internos válidos; `/productos/18`
resolvió la ficha por `Product.id`, y `/productos` mostró los 29 resultados y
10 acciones **Aceptar revisión**. El diálogo validó la nota, explicó que la
acción no aplica correcciones de IA y se canceló sin enviar feedback. Como
colaborador no apareció ninguna acción de aceptación y una invocación directa
con sesión y CSRF válidos respondió `403`. Los usuarios sintéticos se
eliminaron al terminar. Posteriormente, la revisión humana aceptó los 10 casos
con sus notas. Una consulta de sólo lectura dentro del contenedor PostgreSQL
confirmó 29 punteros canónicos en estado `clean`, 10 feedbacks activos de tipo
`exception` y 10 acciones `accept_exception`. No se aplicaron correcciones de
IA. Esta evidencia corresponde al entorno local y no equivale a producción
verificada.

MCP Web Search valida su JWT con `MCP_WEB_SEARCH_SECRET_KEY` según audiencia,
en lugar de caer en la clave MCP genérica. La rotación conserva la clave previa
específica del servicio y acepta `MCP_SECRET_KEY[_FILE]` como contrato de
compatibilidad para los contenedores Compose/Swarm. Permanece como deuda
separada un cierre tardío de
clientes async observado en el worker Enrich (`Event loop is closed`), aunque
no impidió completar los jobs del piloto.
