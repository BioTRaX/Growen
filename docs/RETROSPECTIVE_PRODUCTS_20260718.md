<!-- NG-HEADER: Nombre de archivo: RETROSPECTIVE_PRODUCTS_20260718.md -->
<!-- NG-HEADER: Ubicación: docs/RETROSPECTIVE_PRODUCTS_20260718.md -->
<!-- NG-HEADER: Descripción: Retrospectiva técnica de la migración de Productos y alta masiva canónica. -->
<!-- NG-HEADER: Lineamientos: Ver AGENTS.md -->

# Retrospectiva técnica — Productos Vue y alta masiva canónica

Fecha de corte: 2026-07-18.

## 1. Contexto

La sesión relevó el módulo Productos heredado en React, definió su migración como dominio modular y ejecutó dos cortes: catálogo operativo en Vue 3 y alta masiva de productos canónicos. Después se recuperaron mutaciones básicas y el alta inline de categorías. React continúa como fallback para las capacidades que aún no alcanzaron paridad.

## 2. Observaciones

### Entregas verificadas

- Navegación agrupada bajo **Productos**, conservando las rutas históricas de Catálogo, Stock e Imágenes y filtrando por roles.
- `/productos` con contratos TypeScript, búsqueda con debounce, filtros persistidos en URL, paginación real, tabla responsive, estados de carga/error/vacío y acceso al detalle e historial.
- Mutaciones staff recuperadas: creación de producto y oferta, edición de stock, edición del precio efectivo y borrado protegido individual/masivo.
- Alta masiva canónica desde una selección de ofertas de proveedor, con máximo de 100 filas, exclusión de filas ya vinculadas y wizard Preparar/Completar/Revisar/Procesar.
- Persistencia de `canonical_batch_jobs` y `canonical_batch_job_items`, idempotencia por `client_request_id`, progreso consultable y resultados parciales por fila.
- Estados persistentes `QUEUED`, `RUNNING`, `COMPLETED`, `PARTIAL`, `FAILED` y estados de ítem `PENDING`, `RUNNING`, `SUCCEEDED`, `FAILED`.
- Creación de canónico y equivalencia dentro de una transacción independiente por ítem; un error individual no revierte los éxitos del lote.
- Generación definitiva de SKU `^[A-Z]{3}_[0-9]{4}_[A-Z0-9]{3}$` mediante `db/sku_generator.py`, con inicialización idempotente, bloqueo `FOR UPDATE`, límite 9999 y unicidad de base como defensa final.
- `POST /canonical-products/sku-preview` como preview no reservante y `GET /canonical-products/batch-jobs/{job_id}` para polling. `GET /catalog/next-seq` queda como compatibilidad heredada y tampoco reserva números.
- Borradores Vue aislados por usuario en `growen.products.mass-canonical.v3:<userId>`, TTL de 30 días, autosave a 300 ms, recuperación de job activo, migración desde v2 y conversión de `mass_cannon_session`.
- Polling con espera progresiva de 1, 2 y 5 segundos, detención al desmontar o alcanzar un estado terminal y reenvío exclusivo de filas fallidas con un nuevo identificador idempotente.
- Selector común `CategoryCreatableSelect.vue`: permite escribir un nombre inexistente, crear y seleccionar categoría o subcategoría como clasificaciones planas independientes. `parent_id` se conserva sólo por compatibilidad.
- Revisión `20260717_canonical_batch_tracking`, posteriormente encadenada por `20260717_sales_customers_v4`; no se creó un segundo head.

### Evidencia de calidad registrada durante la sesión

- Suite Vue final: 18 archivos y 52 pruebas aprobadas.
- Suite focal del selector y contratos HTTP: 2 archivos y 6 pruebas aprobadas.
- `vue-tsc`, build Vite y `git diff --check` aprobados.
- `npm audit --audit-level=high`: 0 vulnerabilidades.
- La ruta `http://127.0.0.1:5176/productos` respondió HTTP 200.
- Las pruebas focales de backend y las pruebas PostgreSQL de migración/concurrencia quedaron aprobadas durante la implementación del batch; `docs/MIGRATIONS_NOTES.md` conserva el detalle de la cadena temporal y las 12 asignaciones concurrentes verificadas.

### Límites al cierre

- No se completó el smoke visual automatizado en Chrome. La extensión no pudo conectarse: faltaban el manifest/registro del host nativo y el directorio de perfil esperado. La respuesta HTTP 200 no reemplaza esa validación visual.
- La consulta directa `GET /categories` sin sesión devolvió 403, comportamiento esperado para un recurso protegido; no se realizó una mutación manual de categoría fuera de una sesión staff.
- Administración independiente de canónicos/equivalencias, detalle enriquecido, operaciones masivas avanzadas, Imágenes y Stock continúan pendientes.
- No se modificó el tráfico productivo ni se retiró React.
- El worktree contenía numerosos cambios previos y directorios no versionados. La implementación preservó ese estado y no ejecutó stage, commit ni push.
- La ampliación posterior de taxonomía plana y tags, con métricas de validación actualizadas e incidentes adicionales, se documenta en `docs/RETROSPECTIVE_PRODUCTS_TAXONOMY_TAGS_20260720.md`.

## 3. Errores y/u outputs

### Vitest recibió `--run` dos veces

Evidencia: `npm.cmd test -- --run ...` terminó con `Expected a single value for option "--run", received [true, true]`.

Causa: el script `test` de `frontend-vue/package.json` ya ejecuta `vitest --run`; el argumento adicional duplicó una opción singular.

Corrección: ejecutar `npm.cmd test -- <rutas>` sin repetir `--run`. La regla quedó incorporada en `docs/TESTING.md`.

### Error de inferencia TypeScript en la opción sintética “Agregar”

Evidencia: `vue-tsc` informó que la propiedad `create` no existía en el tipo inferido del arreglo de categorías.

Causa: `Array.map()` infirió únicamente la forma de `ProductCategory` ampliada con `displayTitle`; al insertar después la variante sintética, TypeScript no amplió automáticamente la unión.

Corrección: declarar el arreglo como `CategoryOption[]`, donde `create?: boolean` forma parte del contrato. Después aprobaron `typecheck`, pruebas y build. Este caso demuestra que Vitest no sustituye a `vue-tsc` para componentes Vue tipados.

### `npm audit` bloqueado por el entorno restringido

Evidencia: el endpoint de auditoría npm falló y npm tampoco pudo escribir su log en el cache global del usuario.

Causa: acceso de red restringido y directorio de cache fuera de las raíces de escritura del workspace.

Corrección: repetir únicamente `npm.cmd audit --audit-level=high` con autorización elevada y alcance mínimo. Resultado final: 0 vulnerabilidades.

### Chrome no disponible para el smoke solicitado

Evidencia: el runtime devolvió `Browser is not available: extension`; el diagnóstico encontró Chrome instalado, pero sin host nativo registrado ni manifest y sin el perfil esperado por la extensión.

Corrección aplicada: no se sustituyó silenciosamente Chrome por otra superficie. Se conservaron pruebas, typecheck, build, auditoría y verificación HTTP, y se informó que la validación visual seguía pendiente. La reparación requiere reinstalar el plugin/extensión desde su interfaz; el agente no debe instalar ni modificar el host nativo.

### Búsquedas y diff sobre un worktree grande

Evidencia: búsquedas `rg` globales y listados de estado produjeron salida truncada; el worktree incluía cambios ajenos a Productos.

Causa: alcance demasiado amplio sobre un repositorio con documentación extensa y modificaciones concurrentes.

Corrección: acotar `rg`, `git status` y lecturas a archivos/dominios concretos, editar con `apply_patch` y no normalizar ni revertir archivos ajenos. Las advertencias CRLF/LF no representaron errores de contenido.

### Documentación heredada de preview de SKU

Evidencia: `API_PRODUCTS.md`, `PRODUCTS_UI.md` y `roles-endpoints.md` describían `GET /catalog/next-seq` como preview genérico de “la UI”, mientras Vue ya consumía `/canonical-products/sku-preview`.

Corrección: distinguir explícitamente React heredado de Vue, declarar ambos previews como no reservantes y documentar que sólo `generate_canonical_sku()` asigna el valor definitivo dentro de una transacción.

## 4. Objetivo

Conservar las decisiones del corte y convertir los incidentes reales en controles reutilizables: contratos backend como fuente de verdad, secuencias reservadas sólo durante la transacción definitiva, pruebas Vue que incluyan siempre `vue-tsc`, ejecución correcta de Vitest, preflight honesto del navegador y trabajo focal sobre checkouts compartidos.

## 5. Propuesta de código o pasos

### Ajustes incorporados al conocimiento del repositorio

1. `AGENTS.md` apunta al frontend Vue y mantiene React identificado como fallback.
2. `docs/TESTING.md` incorpora la suite focal de Productos, la sintaxis correcta de Vitest y el control de tipos discriminados.
3. `docs/FRONTEND_DEBUG.md` incorpora el preflight de Chrome, el alcance real de una verificación HTTP y el manejo de auditorías npm bajo sandbox.
4. `API_PRODUCTS.md`, `PRODUCTS_UI.md` y `roles-endpoints.md` distinguen preview legado, preview batch Vue y asignación definitiva.
5. `docs/DEVELOPMENT_WORKFLOW.md` y README vuelven a señalar `scripts/start-dev.ps1` y Vue 5176 como inicio canónico; `start.bat`/React 5173 queda identificado como heredado.
6. Roadmap, README y Changelog enlazan esta retrospectiva y mantienen visibles los módulos pendientes.

### Arquitectura agéntica recomendada

- **Nueva skill creada: `vue-module-migration`.** Se justifica por la repetición del mismo circuito y la ausencia previa de una skill Vue específica. Exige inventario React/contratos, inspección de worktree, componentes por dominio, permisos, tests focales, `vue-tsc`, build, auditoría, smoke en 5176, documentación y preservación del fallback. También advierte que `npm test` ya incluye `--run`.
- **Modificación propuesta a esa skill antes de cualquier browser QA:** preflight de la superficie solicitada y prohibición de reportar HTTP 200 como validación visual. El bloqueo de Chrome fue ambiental y no habría sido resuelto por más lógica de aplicación.
- **Prompt contextual recomendado para futuras migraciones:** incluir el head Alembic efectivo, rutas React/Vue, usuario/rol de prueba, disponibilidad del worker `catalog`, `RUN_INLINE_JOBS`, estado del plugin de navegador y lista de cambios preexistentes que no deben tocarse. Esa información habría reducido exploración y evitado prometer un smoke no disponible.
- **Nuevo agente:** no habría evitado los errores observados de CLI, tipado o Chrome. Un subagente de sólo lectura podría acelerar el inventario React y el contraste documental en futuras fases, pero las ediciones de migración, worker y wizard deben conservar una única coordinación debido al esquema compartido y al worktree sucio.
- **Skill `database-migrations`:** no requiere otra modificación por esta sesión. Su versión actual ya exige head único, revisión focal del autogenerado, pruebas PostgreSQL, rollback y ocultamiento de secretos, controles suficientes para la migración canónica.

## 6. Criterios de aceptación

- Las entregas de Productos, batch canónico y categorías inline se contrastaron con código, migración, tests y documentación actuales.
- Cada error observado tiene evidencia, causa, solución y estado residual.
- La imposibilidad de validar visualmente con Chrome queda declarada y no se presenta como éxito.
- La asignación concurrente y el carácter no reservante de los previews quedan documentados sin ambigüedad.
- Se actualizaron instrucciones de agentes, testing, debugging, contratos, Roadmap, README y Changelog.
- No se registraron credenciales, cookies, IDs de sesión ni URLs con secretos.
