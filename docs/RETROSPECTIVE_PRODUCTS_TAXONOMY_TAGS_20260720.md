<!-- NG-HEADER: Nombre de archivo: RETROSPECTIVE_PRODUCTS_TAXONOMY_TAGS_20260720.md -->
<!-- NG-HEADER: Ubicación: docs/RETROSPECTIVE_PRODUCTS_TAXONOMY_TAGS_20260720.md -->
<!-- NG-HEADER: Descripción: Retrospectiva técnica de taxonomía plana, tags y QA agéntico en Productos Vue. -->
<!-- NG-HEADER: Lineamientos: Ver AGENTS.md -->

# Retrospectiva técnica — Taxonomía plana y tags en Productos

Fecha de corte: 2026-07-20.

## 1. Contexto

La sesión comenzó con un reporte sobre el alta inline de categorías en `/productos`. La primera lectura interpretó erróneamente que faltaba un botón visible; la falla real era que el autocomplete no aceptaba texto y, por lo tanto, nunca podía ofrecer `Agregar “…”`. El alcance luego evolucionó desde reemplazar categorías por tags hasta la decisión final: conservar categoría y subcategoría como dos clasificaciones planas requeridas por canónicos y exportaciones, y hacer convivir tags múltiples como enriquecimiento opcional del producto.

## 2. Observaciones

### Entregas contrastadas con el repositorio

- `categories.kind` separa `category` y `subcategory`; `parent_id` queda sólo como compatibilidad.
- `products.subcategory_id` y `canonical_batch_job_items.tag_names` persisten la nueva taxonomía y los tags del batch.
- Los selectores Vue usan un modelo estable, `v-model:search` y una opción sintética creable; categoría y subcategoría se consultan por tipo y admiten el mismo nombre.
- Tags se normalizan sin distinguir mayúsculas, se deduplican y se gestionan en alta individual, detalle, selección masiva y filas del wizard.
- El worker une tags comunes y particulares y crea las relaciones dentro de la misma transacción que el canónico y la equivalencia.
- La búsqueda de catálogo incluye tags manteniendo AND entre términos; las tres tools MCP de Productos devuelven `tags: list[str]`.
- Las exportaciones de stock y TiendaNegocio forman explícitamente `Categoría > Subcategoría`.
- El borrador masivo pasó a v3 y migra borradores v2 con listas de tags vacías.

### Evidencia de validación producida

- Vue: 57 pruebas aprobadas, `vue-tsc` aprobado y build de producción aprobado.
- Backend focal: categorías 3/3, batch 7/7, sesión y CSRF real para tags 1/1, MCP 19/19, canónicos/exportación 4/4 y módulo de features de producto 3/3 luego de corregir auditoría.
- Python: `compileall` aprobado.
- PostgreSQL: upgrade incremental aprobado, head único `20260718_product_taxonomy_tags_v1` y cadena limpia aprobada sobre una base temporal eliminada al finalizar.
- La corrida Python consolidada inicial terminó con 36 aprobadas y 2 fallas en `test_product_features_api`; el módulo fallido se corrigió y luego aprobó 3/3. No se volvió a ejecutar la misma selección consolidada completa, por lo que no debe informarse como una corrida final íntegramente verde.

### Límites al cierre

- No se completó un smoke visual autenticado en `/productos`; pruebas de componentes, typecheck, build y HTTP no sustituyen esa evidencia.
- `alembic check` continúa mostrando drift histórico ajeno a esta revisión. El análisis focal no detectó drift en los objetos agregados por `20260718_product_taxonomy_tags_v1`.
- React permanece como fallback y no se cambió tráfico productivo.
- El worktree ya contenía numerosos cambios ajenos; no se ejecutó stage, commit ni push.

## 3. Errores y/u outputs

| Incidente | Causa comprobada | Solución aplicada | Estado residual |
|---|---|---|---|
| Se diagnosticó “falta un botón” | Se interpretó la apariencia en vez de la interacción reportada | Se reformuló el caso como escritura, búsqueda sin resultado y opción `Agregar` | Corregido; conviene pedir evidencia de interacción, no asumir affordance visual |
| El autocomplete no aceptaba texto | El componente dependía de eventos simulados y de un modelo de selección inestable | Modelo numérico estable, `v-model:search` y opción sintética tipada | Corregido y cubierto con Vuetify real |
| TypeScript rechazó `create` | El arreglo fue inferido sólo como categoría/tag normal | Interfaces `CategoryOption` y `TagOption` con `create?: boolean` | Corregido; requiere mantener `vue-tsc` en el gate |
| Pruebas Vuetify fallaron al montarse | Vitest no cargaba auto-imports/CSS de Vuetify y JSDOM carecía de `visualViewport` | Plugin Vuetify en Vitest, dependencia inline y polyfill de navegador en las pruebas | Corregido; los tests de interacción deben montar Vuetify real |
| Un test shallow dejó de respetar el stub | Activar auto-import real cambió la resolución del componente | El test de filtros se migró al mismo harness Vuetify real | Corregido; revisar tests vecinos al cambiar plugins globales |
| `catalog_search` produjo HTTP 500 | Un import local de `Tag`/`ProductTag` sombreó el import de módulo y provocó `UnboundLocalError` | Se eliminó el import local; una prueba con sesión y CSRF real reprodujo y verificó el flujo | Corregido |
| Alta de producto terminó en `PendingRollbackError` | Auditoría intentó serializar `Decimal`; la excepción dejó la sesión fallida | Metadatos numéricos convertidos a `float` y rollback/refresh en la ruta de error | Corregido por la suite focal |
| Tags mockeados en el test MCP incorrecto | Un parche con contexto demasiado amplio coincidió en otro fixture | Se inspeccionó el diff y se corrigió el fixture exacto | Corregido; los parches deben anclarse a símbolos únicos |
| Test de migración esperaba un head anterior | La aserción de la cadena limpia no acompañó la revisión nueva | Se actualizó el head esperado y se agregaron aserciones de columnas e índices | Corregido |
| Un helper de importación cambió de contrato | Se actualizó un consumidor, pero existía otro en intents | `rg` sobre todos los call sites y adaptación de `services/intents/handlers.py` | Corregido; búsqueda de consumidores obligatoria antes de cambiar firmas |
| Pytest excedió el timeout inicial | La selección importaba una superficie API amplia y no emitió salida antes del límite | Se aislaron módulos, se ampliaron límites y se evitó ejecutar pytest en paralelo | Resuelto para diagnóstico; falta rerun consolidado final |
| `npm` fue bloqueado por PowerShell | Política de ejecución impidió cargar `npm.ps1` | Uso de `npm.cmd` en comandos y documentación Windows | Corregido |
| Salida de `alembic check` fue excesiva | El repositorio conserva drift histórico en dominios no relacionados | Se clasificó el reporte por objetos de la revisión y se documentó el drift global por separado | Deuda histórica pendiente |

## 4. Objetivo

Conservar una trazabilidad factual de la entrega y transformar únicamente los obstáculos observados en controles repetibles: validar interacciones Vuetify con componentes reales, buscar todos los consumidores antes de cambiar contratos compartidos, distinguir una migración focal del drift histórico y no declarar validaciones que no se ejecutaron.

## 5. Propuesta de código o pasos

### Ajustes agénticos incorporados

1. Ampliar `vue-module-migration` con un harness Vuetify real, revisión de impacto de plugins globales, búsqueda previa de call sites, uso de `npm.cmd` y smoke mediante navegador disponible.
2. Ampliar `database-migrations` para clasificar `alembic check` por objetos propios de la revisión, mantener el drift histórico como deuda separada y exigir que el test fresh valide head y objetos concretos.
3. Mantener un prompt de arranque para cortes de Productos que indique: comportamiento observable fallido, taxonomía elegida, rol de prueba, ruta Vue, head Alembic, disponibilidad del worker y alcance de cambios preexistentes.
4. No crear un agente nuevo para este flujo. Los fallos fueron de contrato, entorno y validación dentro de un worktree compartido; otro escritor habría aumentado el riesgo de colisiones. Un análisis paralelo de sólo lectura sólo se justifica si el usuario solicita explícitamente delegación y existe un alcance aislado.

### Pendientes operativos

1. Ejecutar smoke autenticado como staff: escribir categoría y subcategoría inexistentes, comprobar `Agregar`, crearlas y verificar persistencia tras recargar.
2. Repetir la selección Python consolidada que antes produjo 36 aprobadas y 2 fallas, para obtener una evidencia final única después de los fixes.
3. Resolver el drift Alembic histórico en revisiones separadas y focales; no mezclarlo con taxonomía/tags.

## 6. Criterios de aceptación

- Las tareas, incidentes y soluciones se contrastaron con componentes, modelos, migración, tests y documentación actuales.
- Cada afirmación de calidad distingue entre una corrida completa, una corrida focal y una validación pendiente.
- Los errores de interpretación, tipado, runtime, auditoría, migraciones y entorno tienen causa y solución registradas.
- Las skills y guías afectadas se actualizaron sin crear herramientas no justificadas por la sesión.
- Se corrigió documentación desactualizada sobre jerarquía y se mantuvo visible el smoke pendiente.
- Se documentaron los cambios y se actualizaron `README.md`, `Roadmap.md`, `CHANGELOG.md` y documentos bajo `docs/` relacionados.
