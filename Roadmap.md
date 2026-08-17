<!-- NG-HEADER: Nombre de archivo: Roadmap.md -->
<!-- NG-HEADER: Ubicación: Roadmap.md -->
<!-- NG-HEADER: Descripción: Hoja de ruta del proyecto, estado actual y pendientes (documentación viva) -->
<!-- NG-HEADER: Lineamientos: Ver AGENTS.md -->

# Roadmap del Proyecto

## Actualización 2026-08-17 — cierre factual de Chat, RAG, Telegram y Vue

- [x] Publicados y verificados en `dev` los commits de backend/RAG/Telegram, Chat Vue y documentación; `origin/dev` quedó en `c66452d` antes de la retrospectiva.
- [x] Registrada la retrospectiva factual en `docs/RETROSPECTIVE_CHAT_RAG_VUE_20260817.md`, con incidentes, soluciones y mejoras de prevención/aceleración.
- [x] Aprobados 66 tests backend focales, 91 tests Vue, typecheck, build, skills y head Alembic único.
- [x] Auditado el alcance de 107 archivos sin patrones de secretos ni `.env` reales.
- [ ] Completar smokes autenticados para los cinco roles y la matriz HTTP/WS/Telegram.
- [ ] Validar aliases/datos canónicos de catálogo y el futuro diagnóstico por imágenes antes de activar Vue o un rollout productivo.

## Actualización 2026-08-17 — RAG cargado y Chat Vue en paridad técnica

- [x] Cargadas 10 fuentes RAG clasificadas en PostgreSQL con embeddings Ollama de 1536 dimensiones.
- [x] Fragmentados los documentos curados para que las citas recuperadas entren en el presupuesto de contexto.
- [x] Aprobada la evaluación por rol, canal e intención: cero fugas, recall@5 y MRR sintéticos 1,00, recall curado 1,00, citas y presupuesto 100 %.
- [x] Integrado RAG y citas en respuestas WebSocket normales y streaming bajo `ChatOrchestrator`.
- [x] Alineados HTTP y WebSocket con el resolver determinista de catálogo y sanitización autoritativa para perfiles públicos.
- [x] Corregido Chat Vue para consumir `data.results`; typecheck, 91 pruebas y build aprobados.
- [x] Smoke guest real aprobado en `/chat`: conexión WebSocket, respuesta general, cero errores de consola y sin citas irrelevantes para smalltalk.
- [ ] Ejecutar smoke visual autenticado en Vue para `guest`, `cliente`, `proveedor`, `colaborador` y `admin` con API/WS reales.
- [ ] Mantener `ready/legacy` hasta completar smokes y errores tipados; React sigue disponible para rollback.

## Actualización 2026-08-17 — normalización Ollama GPU

- [x] Detectada RTX 5070 con 12.227 MiB de VRAM y más de 10 GiB libres; el perfil deja de exigir 16 GiB de RAM libre.
- [x] Definido perfil VRAM prioritaria: contexto 4096, un modelo cargado, una solicitud paralela, Flash Attention y KV cache `q8_0`.
- [x] Agregado preflight reproducible de GPU, RAM, pagefile, disco, daemon y modelos.
- [x] Configurado pagefile de 18 GB; daemon y ambos modelos aprobaron el preflight.
- [x] Confirmados `llama3.1:8b` al `100% GPU` con contexto 4096 y embeddings de 1536 dimensiones.
- [x] Agregado preflight reducido de desarrollo: canary activo sin controlador ni autoavance.
- [x] Guardar `telegram_bot_token` fuera del repositorio y configurar el entorno local.
- [x] Capturar `telegram_canary_user_id` con `/canary` e iniciar `preflight/active` de desarrollo.
- [x] Iniciar y verificar el worker polling con PostgreSQL, Redis y Ollama saludables.
- [x] Corregir el falso positivo que enviaba smalltalk Telegram al intent de producto.
- [x] Alinear el tag Ollama del pipeline real con el modelo instalado `llama3.1:8b`.

## Actualización 2026-08-16 — cierre técnico y rollout de Chat 😎

- [x] WebSocket usa Uvicorn loopback asíncrono; también las aclaraciones pasan por `ChatOrchestrator` con correlación, persistencia y `ChatRun`.
- [x] Ollama usa `httpx` asíncrono y falla cerrado; embeddings `qwen3-embedding:4b` validan exactamente 1536 dimensiones.
- [x] Corpus RAG v1 sintético/curado, centinelas y runner idempotente con evaluaciones por scope, citas y cache versionada.
- [x] Rate limit Redis atómico validado entre dos procesos; polling recupera estados vencidos, conserva offset ante huecos y aplica backpressure.
- [x] Secretos Telegram mediante `*_FILE`; revisión `20260816_chat_rollout_v1` aplicada localmente en `disabled/paused`.
- [x] Build Vue con override, metadata y workflow self-hosted con rollback automático a React/`admin_capped`.
- [x] Bloqueo Ollama resuelto el 2026-08-17.
- [ ] El corpus y su evaluación real ya aprobaron; faltan los smokes autenticados de cinco roles antes de cualquier avance de runtime Vue.

## Actualización 2026-08-15 — Retrospectiva técnica agéntica reutilizable

- [x] Creada la skill canónica `retrospectiva-tecnica-sesion` para verificar entregas, registrar errores y soluciones, reconciliar documentación y preservar conocimiento técnico al cerrar una sesión.
- [x] Restringida su activación al cierre explícito informado por el usuario; completar una tarea o nombrar la skill sin declarar el final del chat ya no dispara la retrospectiva.
- [x] Incorporados dos carriles de mejora: prevención basada en obstáculos reales y aceleración basada en patrones repetibles, incluso cuando la implementación no presentó dificultades.
- [x] Consolidado el descubrimiento desde una única fuente en `.agents/skills/` para Codex, Gemini CLI y GitHub Copilot; los adaptadores históricos de `.agent/skills/` dejaron de ser obligatorios.
- [ ] Aplicar la skill sólo en futuros cierres confirmados por el usuario y ajustar sus criterios si la evidencia revela falsos positivos, omisiones o propuestas con bajo valor reutilizable.

## Actualización 2026-08-15 — Auditoría de Chat 😎, Telegram y RAG

Estado comprobado contra código, manifiesto Vue, PostgreSQL local y pruebas:

- [x] PostgreSQL está en el head único `20260726_canonical_knowledge_v1`; la cadena `20260722_chat_*` ya está incluida y `scripts/audit_schema.py` aprobó sus verificaciones estructurales.
- [x] La base local no contiene fuentes RAG, identidades externas, updates Telegram ni ejecuciones de Chat; tampoco quedan sesiones Telegram con ID numérico en claro.
- [x] La suite focal backend aprobó 50 pruebas y omitió 6; Vue aprobó typecheck, 89 pruebas y build de producción.
- [x] Telegram permanece cerrado por defecto y el worker no está en ejecución. El único servicio operativo durante la auditoría fue PostgreSQL; API, Redis, MCP, Vue y workers estaban apagados.
- [x] `Chat 😎` compila en Vue, pero continúa `ready/legacy`; la configuración Nginx generada no publica `/chat` hacia Vue y React conserva el runtime efectivo.
- [x] Documentada la retrospectiva del saneamiento histórico y creada la skill
  `git-secret-forensics`, separada del flujo ordinario de commit/push.
- [x] Secretos rotados; el entorno permanece sin API keys. Continúan pendientes la purga de referencias históricas de GitHub y la protección automática de secretos.
- [x] Webhook retirado del router de la API y `TELEGRAM_TRANSPORT` restringido a `polling`.
- [x] Pantallas Vue para generar/revocar vínculos propios y aprobar/revocar identidades como segundo administrador; permanecen inactivas por flags.
- [ ] Completar la migración WebSocket al `ChatOrchestrator`: tools, fallback local, respuesta general y streaming ya generan trazabilidad y recargan `User.role`; las respuestas de aclaración legacy aún deben converger.
- [ ] Completar observabilidad: tokens estimados y health seguro del worker ya llegan al dashboard; costo real queda pendiente de usage del proveedor y no se probará hasta configurar uno.
- [ ] Añadir evaluaciones RAG por rol, canal e intención y smoke autenticado por cada rol. `ChatView.vue` ya tiene pruebas de streaming y sanitización de cards.
- [ ] Corregir las conexiones SQLite no devueltas al pool detectadas como warnings en pruebas WebSocket/RAG y resolver el drift histórico reportado por `alembic check` sin mezclarlo con la cadena Chat.
- [ ] Ejecutar rollout gradual sólo después de configurar claves efímeras, clasificar fuentes, probar rate limit distribuido/Redis, verificar logs y completar los gates de seguridad.
- [ ] Implementar `scripts/audit-git-secrets.ps1` con salida redactada, pruebas
  y cobertura de refs, reflogs, stashes y objetos no alcanzables.

Orden de ejecución recomendado: seguridad y secretos → cierre del transporte polling → UI de identidades → orquestador WebSocket y observabilidad → RAG/evaluaciones → paridad Vue → smoke integral → activación gradual y ventana estable.

Retrospectiva forense: `docs/RETROSPECTIVE_TELEGRAM_SECRET_FORENSICS_20260815.md`.

Retrospectiva del avance Chat/Telegram: `docs/RETROSPECTIVE_CHAT_TELEGRAM_20260815.md`.

## Actualización 2026-07-30 — Incidente de credencial Telegram

- [x] Confirmada por GitHub Secret Scanning la publicación del token operativo
  en `workers/telegram_polling.py:56`, commit
  `b4bf96907f05cc772f265400f7d8d60ba3dcf3ac`.
- [x] Token revocado y literal retirado en `dev` por
  `590ef3b8598b6434d7a8474d9a5b02f721cb1bdf`.
- [x] Auditados 631 commits, 137 referencias, reflogs, cero stashes y 433 blobs
  no alcanzables sin reproducir valores sensibles.
- [x] Documentados el `.env` históricamente rastreado, la clave OpenAI local
  pendiente de rotación y el estado de dependencias.
- [x] Integrada la remoción en `main`; `main` y `dev` fueron reescritas con
  `git filter-repo` y publicadas atómicamente con leases explícitos.
- [x] Eliminadas las cuatro ramas Dependabot afectadas y verificadas 130
  referencias de ramas y tags desde una clonación independiente.
- [ ] Solicitar a GitHub Support la purga del objeto histórico todavía
  alcanzable desde diez referencias internas `refs/pull/*`, que no aceptan
  actualización mediante `git push`.
- [ ] Invalidar clones, forks, caches y artefactos, y exigir reclonado limpio a
  los colaboradores.
- [x] Clave OpenAI local rotada e invalidada; no se configuró reemplazo ni API keys.
- [ ] Habilitar GitHub Push Protection y un escáner de secretos obligatorio en
  pre-commit/CI.
- [ ] Actualizar `react-router`/`react-router-dom` y repetir `npm audit`; el
  barrido del 2026-07-30 detectó una vulnerabilidad alta corregible.

Evidencia y plan: `docs/SECURITY_INCIDENT_TELEGRAM_20260730.md`.

## Actualización 2026-07-25 — Detalle canónico Vue y Enrich v2

- [x] Contenido, dimensiones, especificaciones, instrucciones, revisión y trazabilidad viven en `CanonicalProduct`.
- [x] Jobs, fuentes breves y versiones son persistentes, idempotentes y usan revisión optimista.
- [x] `products.market_price_reference` fue retirado; Mercado conserva su modelo canónico, observaciones e histórico como única autoridad monetaria.
- [x] MCP Web Search incorpora lectura HTTPS de HTML/PDF con defensa SSRF, redirects acotados, streaming, MIME y tamaño validados.
- [x] `enrichment_worker` usa cola, heartbeat y health propios; OpenAI/Ollama deben validar el mismo esquema y el eco nunca es aceptable.
- [x] Despliegue local, migración, health y smoke autenticado para `guest`,
  `cliente`, `colaborador` y `admin`.
- [x] `ENRICH_V2_ENABLED=1` efectivo; investigación real con cinco fuentes y
  retries idempotentes.
- [ ] Configurar OpenAI u Ollama y repetir el smoke hasta obtener una propuesta
  válida y aplicar/revisar campos con `content_revision`. Documentar el resultado
  y actualizar cualquier instrucción desactualizada.

Evidencia operativa: `docs/ENRICH_V2_DEPLOYMENT_SMOKE_20260725.md`.
- [x] `/productos/:id` quedó activo en Vue con contenido canónico, inventario vinculado sin duplicados, stock agregado de sólo lectura, Mercado separado y polling cancelable.
- [x] `/productos/:id/imagen` permanece como módulo React independiente para rollback granular.
- [x] Upgrade desde PostgreSQL vacío validado hasta `20260725_canonical_enrichment_v2`; requiere `vector` antes de recorrer el historial RAG.
- [ ] Activar `ENRICH_V2_ENABLED=1` sólo después del smoke autenticado con MCP, Redis, worker y proveedor saludables.
- [ ] Retirar `Product.is_enriching` y los campos técnicos legacy después de un ciclo estable de fallback React.

## Actualización 2026-07-25 — Reconciliación documental de Stock y Mercado

- [x] Contrastados manifiesto, Nginx, vistas Vue, clientes HTTP, permisos y pruebas de Stock y Mercado.
- [x] Confirmado `state: active` y `runtime: vue` para `/stock`, `/stock/shortages` y `/mercado`.
- [x] Creado `docs/STOCK.md` como contrato operativo y definido `docs/API_MARKET.md` como fuente canónica de Mercado.
- [x] Eliminadas afirmaciones `legacy/pending` desactualizadas y marcado el documento de integración React de Mercado como histórico.
- [ ] Ejecutar smoke visual autenticado por rol para ambos módulos.
- [ ] Validar concurrencia real de Stock/Faltantes sobre PostgreSQL.
- [ ] Retirar código React sólo después de los gates y la ventana de estabilidad.

## Actualización 2026-07-22 — Chat multicanal seguro

- [x] Base de identidad Telegram cifrada (AES-GCM), búsqueda HMAC, vínculos revocables y aprobación doble para admin.
- [x] Registro central deny-by-default para roles, canales, capacidades, tools y sanitización pública.
- [x] Polling acotado, idempotente, ordenado por remitente, con backoff, recuperación y health seguro.
- [x] RAG híbrido con scopes previos al ranking, vigencia, versión, cache y citas tipadas.
- [x] Trazabilidad sin contenido en `chat_runs`/`chat_tool_events`, métricas agregadas y archivado a 90 días.
- [x] Módulo Vue `/chat` implementado como `Chat 😎`, conservando React como fallback.
- [x] Migraciones aplicadas en PostgreSQL con las banderas apagadas; head actual `20260726_canonical_knowledge_v1`.
- [ ] Ejecutar smoke multicanal por rol con claves rotadas y datos de prueba clasificados.
- [ ] Clasificar explícitamente todas las fuentes RAG antes de publicar conocimiento.
- [ ] Activar Telegram por etapas y promover Chat Vue sólo tras paridad, dos releases y siete días sin incidente crítico.

## Actualización 2026-07-21 — Mercado observable y migrado a Vue

- [x] Migración focal `20260721_market_observability_v1`: alertas, jobs, items, resultados por fuente, validación, observaciones auditables e histórico de tres años.
- [x] Promedio aritmético de últimas observaciones ARS efectivas; cargas manuales como observaciones y fuente libre auditada.
- [x] API observable con deduplicación por producto, estados terminales, jobs, histórico, revalidación y listado sin N+1.
- [x] Worker Docker dedicado no-root con Chromium, HTTP primero, cuatro consumidores configurables, exclusión por dominio, backoff, heartbeat y control desde Administración.
- [x] Panel administrativo reconciliado con el estado Compose real y health específico de Mercado, evitando falsos “Docker no disponible” por latencia de Docker Desktop.
- [x] Extracción robustecida con prioridad JSON-LD `Product/Offer`, separación nombre canónico/SKU y recarga automática al finalizar jobs.
- [x] `/mercado` activado en Vue con filtros, batch, polling cancelable, detalle de fuentes, observación manual, histórico SVG y ocho bandas accesibles.
- [x] Credencial local de PostgreSQL rotada e invalidada sin exponer el reemplazo; cola Redis obsoleta depurada por IDs exactos.
- [x] Upgrade incremental y limpio a head, build Vue, imagen Docker y smoke job→worker→terminal verificados.
- [ ] Evolución: score de confianza, circuit breaker por dominio, dashboard de cobertura/volatilidad y recomendaciones explicables con aprobación humana.
- [ ] Retirar el fallback React tras un ciclo estable y smoke visual autenticado por ambos roles.
- [x] Retrospectiva técnica publicada con incidentes post-implementación, soluciones y ajustes al diagnóstico agéntico.
- [ ] Incorporar guarda de listener único para la API y estado de invalidación auditable para observaciones erróneas.

## Actualización 2026-07-21 — Retrospectiva de publicación segura en `dev`

- [x] Preservado el worktree completo al crear `dev` desde `main`; 327 archivos se organizaron en cuatro commits atómicos y se publicaron sin modificar `main`.
- [x] Quality gate consolidado aprobado: seguridad/dependencias, 39 pruebas Python, builds React/Vue, 65 pruebas Vue y 5 smokes E2E.
- [x] Corregida la falsa SQLite compartida en Windows: `:memory:` se conserva y `StaticPool` evita convertir la base de tests en una ruta física `file:...`.
- [x] Robustecido el smoke `/compras` con selector semántico y espera compatible con compilación lazy inicial de Vite.
- [x] Publicación auditada sin secretos; el falso positivo `AKIA...` fue trazado a un hash npm `integrity`.
- [x] Skill `git-commit-push` ampliada con escaneo redactado, verificación de remoto, aprobación explícita y comprobación del SHA remoto.
- [ ] Evaluar un `scripts/audit-secrets.ps1` reutilizable que implemente las mismas reglas y pruebas para evitar scanners ad hoc.
- [ ] Migrar los tests heredados de `TestClient` antes de adoptar `httpx2`.

## Actualización 2026-07-20 — Stock Vue activo; retiro React pendiente

- [x] Implementadas `/stock` y `/stock/shortages` en Vue 3 con filtros URL, debounce, cancelación, paginación reemplazable, permisos y estados de error.
- [x] Stock y faltantes admiten `Decimal(14,2)`; el ajuste manual usa `expected_stock`, bloqueo de fila, ledger y auditoría en una transacción.
- [x] XLSX, CSV y PDF comparten selección y filtros; PDF usa ReportLab y TiendaNegocio conserva su contrato.
- [x] Enriquecimiento masivo, completar precios, generación e histórico de catálogos fueron retirados de la nueva vista Stock y ubicados en Productos Vue.
- [x] Quality gates locales: Vue 65/65, backend Stock 12/12 y contrato CSRF aislado aprobado, typecheck y builds Vue/React aprobados.
- [x] Activar `stock` como `active/vue` una vez disponible Productos/Catálogos en Vue.
- [ ] Completar el smoke visual autenticado por rol antes de retirar React.
- [ ] Validar concurrencia real de dos faltantes sobre PostgreSQL; SQLite no permite demostrar el bloqueo pesimista.
- [ ] Tras dos releases estables y siete días sin incidentes críticos, evaluar el retiro de React en un corte separado.

## Actualización 2026-07-20 — Incidente operativo del batch canónico

- [x] Restaurada la publicación loopback de PostgreSQL/Redis sin pérdida de volúmenes y validado el arranque canónico completo.
- [x] Corregido el reintento idempotente de jobs `FAILED` sin ítems procesados y añadida la acción Vue **Reintentar lote**.
- [x] Verificado un lote final `COMPLETED` 10/10 con 10 canónicos y 10 equivalencias.
- [x] Documentada la retrospectiva operativa y el diagrama FigJam del flujo completo.
- [x] Operaciones Compose del panel ejecutadas fuera del event loop, con rollback seguro antes de registrar fallos.
- [x] Incorporados eventos NDJSON del worker `catalog` y referencias `*_log_source_hint` para procesos reutilizados.
- [x] Creada la skill canónica `diagnose-local-services` y ampliada `create-service` con dependencias, red, preflight y observabilidad.
- [x] `start-dev.ps1 -WithCatalogWorker` inicia/verifica Redis+Dramatiq y reconcilia DB si Compose figura activo sin puerto host.
- [x] El worker local de catálogo persiste stdout/stderr en `logs/worker_catalog.log`; el launcher detecta y registra consumidores locales que compiten con Dramatiq Docker.
- [ ] Exponer en la UI un preflight previo al wizard que identifique explícitamente ausencia del consumidor `catalog`.

## Actualización 2026-07-20 — Retrospectiva de taxonomía, tags y QA agéntico

- [x] Compatibilidad entre aislamiento `backend: internal` y desarrollo local: PostgreSQL/Redis conservan bindings loopback mediante la red Compose `host_access`, evitando que el alta de Dramatiq deje inaccesibles `5433` y `6379` al recrear contenedores.
- [x] Recuperación idempotente de lotes canónicos: los jobs `FAILED` sin ítems procesados vuelven a `QUEUED` y se despachan al recuperarse Redis, con cobertura automatizada.

- [x] Contrastada la implementación de taxonomía plana y tags contra modelos, API, worker, Vue, MCP, exportaciones y pruebas.
- [x] Registradas causas y soluciones de los fallos de autocomplete, Vuetify/JSDOM, búsqueda por tags, auditoría de producto y pruebas de migración.
- [x] Actualizadas las skills `vue-module-migration` y `database-migrations` con controles surgidos de incidentes reales.
- [x] Corregida la documentación heredada que todavía describía categorías/subcategorías jerárquicas.
- [ ] Ejecutar smoke visual autenticado como staff y comprobar persistencia después de recargar.
- [ ] Repetir la selección Python consolidada posterior a los fixes y resolver el drift Alembic histórico en revisiones separadas.

## Actualización 2026-07-18 — Taxonomía plana y tags en Productos Vue

- [x] Categoría y subcategoría tipadas como listas planas independientes, con creación inline y mismo nombre permitido entre tipos.
- [x] Tags múltiples en alta individual, detalle, selección masiva y wizard canónico; borradores migrados a v3.
- [x] Worker batch idempotente con persistencia transaccional de tags y equivalencia.
- [x] Búsqueda MCP por tags y contrato `tags: list[str]` en las tres tools de Productos.
- [x] Migración incremental y cadena PostgreSQL limpia validadas en el head `20260718_product_taxonomy_tags_v1`.
- [ ] Completar el smoke visual por rol antes de retirar el fallback React.

## Actualización 2026-07-18 — Panel administrativo Vue y persistencia operativa

- [x] Limpieza de logs alineada con `start-dev.ps1`: previsualización Vue, retención, carpetas dev completas, ejecución activa protegida y scripts canónicos.
- [x] Drive Sync Vue con historial PostgreSQL, detalle por archivo, cancelación cooperativa, reintentos hijos y WebSocket autenticado.
- [x] Scheduler admin con configuración singleton persistente, historial manual/automático y liderazgo mediante advisory lock.
- [x] Conocimiento RAG restringido a admin, tareas persistentes, validación de archivos y prueba semántica.
- [x] Imágenes separadas entre operación del crawler admin y revisión/procesamiento para staff.
- [x] Catálogos con ejecuciones/eventos persistentes, exportación NDJSON/CSV y desbloqueo admin auditado sin purga automática.
- [x] Dashboard técnico Vue de solo lectura y enlaces a módulos responsables.
- [x] Chat Inbox con filtros, asignación, tags, acciones masivas, feedback, clasificación y gobierno reversible de prompts.
- [x] Revisiones Alembic `20260718_admin_operations_v1`/`20260718_admin_jsonb_v2` y contratos de seguridad/CSRF compartidos.
- [ ] Completar dos releases estables y siete días sin incidentes críticos antes de retirar React.
- [ ] Ejecutar el smoke visual por rol y el test fresh PostgreSQL en un host con Docker disponible.

## Actualización 2026-07-18 — QA y conocimiento agéntico de Productos

- [x] Documentada la retrospectiva técnica de catálogo Vue, alta masiva canónica y categorías inline.
- [x] Corregida la documentación para distinguir preview legado, preview batch no reservante y SKU definitivo transaccional.
- [x] Incorporados controles de Vitest, `vue-tsc`, sandbox de auditoría y preflight de Chrome a las guías de trabajo.
- [ ] Completar un smoke visual staff en Chrome cuando el plugin y su host nativo vuelvan a estar disponibles.
- [x] Creada la skill canónica `vue-module-migration` con adaptador legacy y controles de paridad, testing, navegador, documentación y fallback React.

## Actualización 2026-07-17 — Alta masiva canónica Vue

- [x] Wizard Vue de cuatro pasos desde la selección del catálogo, con nombre, categoría, subcategoría, marca opcional y SKU provisional.
- [x] Alta inline buscable de categorías en el producto individual y de categoría/subcategoría planas e independientes dentro del wizard masivo.
- [x] Borradores versionados por usuario, recuperación tras recarga y migración de `mass_cannon_session`.
- [x] Lotes idempotentes y persistentes con polling, progreso, resultados por fila y errores parciales.
- [x] Generación definitiva `XXX_####_YYY` mediante secuencia PostgreSQL bloqueada y vínculo atómico con el producto de proveedor.
- [ ] Siguiente fase: administración independiente de canónicos y equivalencias.
- [ ] Luego: detalle integral, imágenes, activación productiva de Productos/Catálogos y smoke final de Stock.

## Actualización 2026-07-17 — Baseline funcional del portal React

- [x] Inventariadas las rutas productivas, roles, vistas, formularios, acciones y endpoints consumidos por la SPA React.
- [x] Documentado el mapeo a una arquitectura Plugin-based UI con Sidebar + Main Content en `docs/relevamiento_admin.md`.
- [x] Identificadas inconsistencias de permisos visibles, aliases de imágenes, contratos iAVaL legacy y el alcance real de “Adjuntar Excel”.
- [ ] Usar el relevamiento como checklist de paridad por plugin antes de retirar cada dominio React.

## Actualización 2026-07-16 — Compras y primer corte de Productos Vue

- [x] Primer corte funcional de Compras en Vue 3/Vuetify.
- [x] Alta automática y transaccional de productos sin canónico al confirmar.
- [x] Adjuntos PDF/JPG/PNG con hash, deduplicación y descarga del original.
- [x] Movimientos de compras en `stock_ledger` e historial de compras por producto.
- [x] Listado operativo de Productos con navegación agrupada, filtros persistentes, paginación, contratos tipados y permisos equivalentes a React.
- [x] Detalle básico público y extensión de historial de compras para staff.
- [x] Selector buscable y alta rápida de proveedores en Compras; listado `/proveedores` activo en Vue.
- [x] Regresión de sesión corregida para que login, rol y CSRF autoricen mutaciones reales.
- [x] Recuperar alta, edición de stock, precio efectivo y borrado protegido individual/masivo de Productos en Vue.
- [ ] Completar preferencias de columnas y operaciones masivas de precios.
- [ ] Migrar detalle enriquecido, canónicos, equivalencias e imágenes.
- [ ] Resolver drift Alembic histórico no relacionado reportado por `alembic check`.
- [ ] Extender perfiles de remito a proveedores distintos de Santa Planta.

## Actualización 2026-07-17 — QA de sesión y conocimiento agéntico

- [x] Documentada la retrospectiva técnica de Compras, Proveedores y autenticación.
- [x] `no_auth_override` prueba ahora rol y CSRF reales y restaura los overrides sin contaminación.
- [x] Regresión de sesión cubre login, `/auth/me` y una mutación protegida.
- [x] Mocks iAVaL actualizados al contrato `AIRouter.run_async`.
- [x] Documentada la ejecución secuencial de pytest en workspaces compartidos.
- [ ] Migrar los tests síncronos heredados desde `TestClient` antes de adoptar `httpx2`.
- [ ] Ejecutar E2E completo de OCR de imágenes en un host con Tesseract, QPDF, Ghostscript y OCRmyPDF.

## Actualización 2026-07-17 — Legibilidad del detalle de Compras Vue

- [x] Redistribuidas las columnas para priorizar el nombre original y compactar los datos numéricos.
- [x] Incorporado el total neto reactivo y formateado por cada línea del remito.
- [x] Cubierto el cálculo de línea con pruebas unitarias y documentado el comportamiento responsive.

## Actualización 2026-07-17 — Confirmación de Compras y feedback de validación

- [x] La UI diferencia errores bloqueantes de advertencias y elimina el fallo silencioso de `Confirmar` en estado `BORRADOR`.
- [x] La importación deja de inferir bonificaciones desde el nombre comercial y preserva la columna documental.
- [x] Alembic `c923732e1cab` alinea `supplier_price_history.file_fk` nullable con el modelo y desbloquea la transacción de confirmación.
- [x] Compra 1 confirmada de extremo a extremo: 10 productos, 10 movimientos de stock y 10 historiales persistidos.

## Actualización 2026-07-17 — Cierre QA y conocimiento operativo

- [x] Retrospectiva ampliada con los incidentes de validación, confirmación, deriva de esquema y evidencia E2E persistida.
- [x] Guía frontend incorpora correlación navegador/API/PostgreSQL, control de hot reload y verificación posterior de mutaciones.
- [x] Skill `database-migrations` endurecida para descartar deriva autogenerada no relacionada y evitar secretos en outputs.
- [ ] Incorporar un E2E automatizado del ciclo `BORRADOR` → `VALIDADA` → `CONFIRMADA` con verificación de impacto.

Última actualización general: 2026-07-21

Este documento resume el estado actual del proyecto, las funcionalidades ya implementadas y los trabajos pendientes. Debe mantenerse actualizado por cada contribución (humana o de un agente) que cambie comportamiento, endpoints, modelos o UI relevante.

## Contexto
## Actualizaciones recientes

- Base de datos/Migraciones: Se reparó la instalación completa desde PostgreSQL vacío. La revisión RAG autogenerada `cf0f6e70fe89` quedó como no-op, se preservaron la implementación manual `b2d22a7ce889` y el merge `fa50a5cba1bb`, y se agregó `20260714_schema_integrity` para garantizar índices y constraints omitidos por ramas históricas. Se incorporó una prueba PostgreSQL temporal de `alembic upgrade head`; resultado local: 53 tablas, único head y auditoría sin faltantes. Ver `docs/MIGRATIONS_NOTES.md`.

- Frontend/Migración Vue: La imagen productiva compila React y Vue. `frontend-vue/config/modules.json` decide el runtime por dominio; React es el fallback general para rutas todavía no activadas o sujetas a rollback. Estado y comandos en `docs/FRONTEND_MIGRATION_VUE.md`.

- Frontend/Productos Vue: Catálogo, detalle principal, Stock e Imágenes tienen rutas Vue activas. La imagen avanzada `/productos/:id/imagen` y otras capacidades declaradas como legacy permanecen en React hasta completar su corte.

- Frontend/Proveedores Vue: `/proveedores` habilita búsqueda y alta básica para administradores. Compras reutiliza el selector con autocomplete y deja de exponer IDs internos en sus formularios.

- Desarrollo/Inicio local: `scripts/start-dev.ps1` es el método único durante la etapa de desarrollo. Reutiliza o levanta únicamente PostgreSQL mediante Docker, aplica Alembic y ejecuta API/Vue localmente con healthchecks y logs aislados por ejecución en `logs/dev/`. El arranque productivo se adaptará cuando se prepare el despliegue.

- Frontend/Arquitectura: La base modular definida en `frontend/brainstorming_Growen.md` comenzó su implementación. La convivencia React/Vue evita cambiar Docker y el build productivo antes de lograr paridad funcional.

- Documentación/Onboarding Dev: El flujo principal quedó consolidado en `.\scripts\start-dev.ps1`; los arranques manuales se mantienen únicamente como herramientas de diagnóstico.

- DB/Backend: Se agregaron metadatos de trazabilidad de enriquecimiento en `products` (`last_enriched_at`, `enriched_by`) y se exponen en `GET /products/{id}`. El endpoint `POST /products/{id}/enrich` los setea automáticamente; `DELETE /products/{id}/enrichment` los limpia. Migración: `20251021_add_product_enrichment_trace.py`.

- Frontend: La ficha de producto vuelve a mostrar la "Descripción enriquecida" con vista previa HTML sanitizada para todos los roles (scripts/iframes/eventos inline se eliminan). Los usuarios con permisos de edición mantienen el textarea y pueden guardar via `PATCH /catalog/products/{id}`.
- Frontend/Backend: El detalle `/productos/:id` se habilitó en modo lectura para el rol `guest` (ProtectedRoute + endpoint `GET /catalog/products/{id}` aceptan invitados). Los invitados ven nombre, precio y descripción, mientras que las acciones siguen restringidas a colaborador/admin.
- Chatbot: El WebSocket `/ws` ahora comparte la misma memoria conversacional que el endpoint HTTP, inyectando el historial reciente en los prompts y persistiendo cada intercambio en `chat_messages`.
- Chatbot - Sesiones Persistentes: Implementado sistema de sesiones persistentes (`ChatSession`) que permite mantener contexto conversacional por usuario y auditar conversaciones desde Dashboard Admin. Los mensajes ahora se relacionan con sesiones vía ForeignKey, y el handler de Telegram crea/actualiza sesiones opacas automáticamente. El diseño inicial quedó archivado en `docs/archive/CHAT_MEMORY_PLAN.md`; el contrato vigente está en `docs/CHAT.md`.


- Backend: FastAPI + SQLAlchemy (async) para gestión de compras (borradores, validación, confirmación), adjuntos (PDF remito), logs y auditoría.
- AI: Capa `ai/` con enrutador y proveedores (OpenAI y/o Ollama) para tareas de razonamiento y validación.
- Frontend: SPA React/TypeScript (Vite) productiva y SPA Vue 3/Vuetify 3 paralela en migración.
- Almacenamiento de archivos: `data/purchases/{id}/...` para PDFs y artefactos relacionados.

## Roadmap de Inteligencia Growen (Evolución 2025)

### Etapa 0: Core AI asíncrono y MCP interoperable
- **Estado**: Implementación completada sobre Python 3.14.6; quality gate de seguridad y contratos incorporado para ejecución local o CI manual.
- `AIRouter.run_async`, OpenAI async y la propagación de rol están conectados en HTTP, WebSocket y Telegram.
- Products y Web Search exponen MCP Streamable HTTP en `/mcp` y conservan `/invoke_tool` como adaptador deprecado.
- Growen descubre `tools/list`, filtra por rol y ejecuta `tools/call` mediante `agent_core/mcp_client.py`.
- El schema estático fue retirado. `chat_with_tools` quedó como adaptador del flujo asíncrono descubierto; su nombre y el RPC legacy se retirarán tras validar paridad y completar la ventana de dos semanas sin invocaciones RPC.

### Etapas Futuras (Resumen)
- **Etapa 1**: Enriquecimiento de datos estructurados — **EN PROGRESO**
  - ✅ Campos JSONB agregados al modelo `Product`: `technical_specs` (dimensiones, potencia, peso, etc.) y `usage_instructions` (pasos, consejos de uso).
  - ✅ Esquemas Pydantic actualizados en `chat.py` y `catalog.py` para exponer los nuevos campos.
  - ✅ MCP `products_server` actualizado para incluir los datos estructurados en las respuestas de `get_product_info` y `get_product_full_info`.
  - ✅ Migración de base de datos aplicada (`20251119_add_product_specs_and_usage`).
  - ⏸️ Futuros pasos: UI para editar especificaciones técnicas, pipeline de enriquecimiento automático con IA, validación de esquemas JSON.

- **Etapa 2**: RAG para documentación propia — **✅ COMPLETADA (Infraestructura + Motor de Ingesta)**
  - ✅ PostgreSQL actualizado a `pgvector/pgvector:pg17` con extensión pgvector 0.8.1 instalada.
  - ✅ Dependencias agregadas: `pgvector>=0.3.8`, `langchain-text-splitters>=0.3.0`, `tiktoken>=0.8.0`.
  - ✅ Modelos `KnowledgeSource` y `KnowledgeChunk` implementados con Vector(1536).
  - ✅ Migración aplicada: `b2d22a7ce889_add_rag_knowledge_tables_manual`.
  - ✅ `EmbeddingService` migrado a Ollama asíncrono con `qwen3-embedding:4b` y validación estricta de 1536 dimensiones.
  - ✅ `DocumentIngestor` implementado en `services/rag/ingest.py` con chunking inteligente (RecursiveCharacterTextSplitter).
  - ✅ Script de carga `scripts/index_docs.py` funcional con detección de cambios por hash SHA256.
  - ✅ Directorio `docs/knowledge_base/` creado con documentación completa.
  - ✅ Corpus sintético/curado y runner reproducible disponibles; su evaluación productiva queda bloqueada hasta superar el preflight local de Ollama.
  - 🔄 **Próximos pasos**:
    - Implementar endpoint `/api/v1/rag/search` para búsquedas semánticas.
    - Integrar recuperación RAG en respuestas del chatbot.
    - Agregar reranking para mejorar relevancia de resultados.
    - Implementar índice IVFFlat después de alcanzar 10K+ vectores.
    - Monitorear latencias, memoria y disponibilidad de Ollama.

- **Etapa 3**: Conciencia de Roles y Seguridad — **EN PROGRESO**. JWT MCP por audiencia, control granular, rate limit y revocación distribuidos en Redis, rotación compatible por `kid`, aislamiento de contenedores y supply-chain checks ya implementados. Quedan SSO/MFA (Keycloak/Authentik) y automatizar la custodia/rotación externa de claves para un despliegue remoto.
- **Etapa 4**: Modo Desarrollador — Indexación del repositorio local, acceso controlado al código fuente, gateway de lectura/escritura confinada a `PR/`, y memoria conversacional a largo plazo.
- **Etapa 5**: Business Intelligence — Text-to-SQL para consultas de finanzas, stock, ventas y análisis de tendencias; dashboards conversacionales.

### Memoria y Aprendizaje — Sesiones Persistentes (Fase 1 y 2)

- **Estado**: ✅ COMPLETADA (Fase 1 y 2)
- **Objetivo**: Evolucionar de un sistema stateless a sesiones persistentes que permitan mantener contexto conversacional y auditar conversaciones para RLHF.

**Fase 1 - Base de Datos y API (Completada)**:
  - ✅ Modelo `ChatSession` creado en `db/models.py` con campos: `session_id` (PK), `user_identifier`, `status` (new/reviewed/archived), `tags`, `admin_notes`, timestamps.
  - ✅ Modelo `ChatMessage` actualizado para usar ForeignKey hacia `ChatSession` (antes era String sin relación).
  - ✅ Migración `20250126_add_chat_sessions_table_and_fk` que:
    - Crea tabla `chat_sessions` con índices necesarios.
    - Migra mensajes existentes agrupándolos por `session_id` y creando sesiones correspondientes.
    - Convierte `chat_messages.session_id` a ForeignKey con `CASCADE`.
  - ✅ Router `services/routers/admin_chat.py` con endpoints:
    - `GET /admin/chats`: Lista sesiones (paginado, filtros por status).
    - `GET /admin/chats/{session_id}`: Detalle completo de sesión + mensajes.
    - `PATCH /admin/chats/{session_id}`: Actualizar estado, notas o tags.
  - ✅ Servicio `services/chat/history.py` actualizado:
    - `get_or_create_session()`: Obtiene o crea sesión automáticamente.
    - `save_message()`: Guarda mensaje y actualiza `last_message_at` de la sesión.

**Fase 2 - Integración y Frontend (Completada)**:
  - ✅ Handler Telegram (`services/chat/telegram_handler.py`) actualizado:
    - Usa `message.from.id` para resolver la identidad y genera `session_id`/`conversation_key` opacos mediante HMAC; `chat.id` sólo identifica destino y conversación.
    - Guarda mensajes de usuario y asistente usando `save_message()`.
    - Recupera historial conversacional antes de procesar.
  - ✅ Página frontend `frontend/src/pages/admin/ChatInbox.tsx`:
    - Layout de 2 columnas: lista de conversaciones (izq) y vista de chat + panel de acciones (der).
    - Filtros por status, paginación, vista de mensajes en formato burbujas.
    - Panel de acciones para cambiar status (new/reviewed/archived) y agregar notas administrativas.
  - ✅ Servicio HTTP `frontend/src/services/chats.ts` con funciones para consumir endpoints admin.
  - ✅ Routing frontend actualizado (`paths.ts`, `App.tsx`, `AdminLayout.tsx`) con ruta `/admin/chats` y botón "Chat Dashboard".

**Próximas Fases (RLHF)**:
  - Fase 3: Etiquetado automático (análisis de sentimiento, detección de intents problemáticos).
  - Fase 4: Feedback humano estructurado (marcar respuestas como buena/mala, notas estructuradas).
  - Fase 5: Aprendizaje iterativo (pipeline que procesa feedback y ajusta prompts, métricas de calidad).

**Documentación**:
  - ✅ `docs/archive/CHAT_MEMORY_PLAN.md`: arquitectura histórica; `docs/CHAT.md` contiene el flujo vigente y seguro.

### Capa MCP Servers (estado)

Arquitectura MCP real establecida para exponer herramientas de dominio a LLMs.

Servicio actual:
- `mcp_products` y `mcp_web_search` (FastMCP + ASGI).
  - Tools descubiertas: `find_products_by_name`, `get_product_info`, `get_product_full_info`, `search_web`.
  - Endpoint canónico `/mcp`; `/invoke_tool` queda deprecado durante la migración.
  - JWT Bearer con issuer/audience, roles, rate limiting y auditoría compartida.
  - Consume API principal vía HTTP (no DB directa).
  - Dockerizado en puertos 8100 y 8102; desarrollo local administrado por `scripts/start-dev.ps1`.
  - Tests: permisos, cache, token auth, invocación tool (respx) y contrato Streamable HTTP `initialize` + `tools/list`.

Integración chatbot:
- Endpoint `/chat` ahora usa tool-calling (OpenAI → MCP) para consultas de producto. `price_lookup.py` marcado DEPRECATED.

**Autenticación MCP → API (2025-11-19):**
- ✅ **Token de servicio interno implementado**: Se agregó `INTERNAL_SERVICE_TOKEN` al `.env` para autenticación entre microservicios (MCP servers → API principal).
- ✅ **Middleware de autenticación**: Función `verify_internal_service_token()` en `services/auth.py` valida el header `X-Internal-Service-Token` con comparación de tiempo constante (prevención de timing attacks).
- ✅ **Integración en require_roles**: El middleware de autenticación por roles ahora acepta token de servicio interno como método prioritario (asume rol `admin` cuando el token es válido).
- ✅ **MCP server actualizado**: `mcp_servers/products_server/tools.py` ahora incluye la función `_get_internal_auth_headers()` que agrega el token en todas las peticiones HTTP hacia la API principal.
- ✅ **Configuración unificada**: Se agregó `internal_service_token` a `agent_core/config.py` para centralizar la lectura del entorno.
- ⚠️ **Seguridad**: El token actual es para desarrollo. En producción debe rotarse por uno generado con `secrets.token_urlsafe(32)` y mantenerse secreto (no commitear).

Próximos pasos MCP:
- Ejecutar contract tests con Python 3.14.6 y MCP Inspector.
- Retirar RPC y schemas estáticos tras dos semanas sin invocaciones legacy.
- Evaluar MCP SDK v2 después de su versión estable.
- Extender tools: métricas de ventas, equivalencias SKU, historial de precios.
- Rate limiting por rol y circuito de retry/backoff.

## Estado actual (hecho)

- Se actualizo la persona del chatbot para reflejar un tono mas malhumorado, sarcastico y centrado en Nice Grow.
- El chatbot de precios ahora pide aclaracion cuando hay multiples coincidencias antes de compartir montos.
- Backend compras: update_purchase limpia los vinculos al editar SKUs y confirm_purchase expone deltas por linea.
- UI compras: se corrigió la codificación de textos en frontend/src/pages/PurchaseDetail.tsx para eliminar caracteres extra (acento, guion largo, preguntas).
- UI compras: selector de proveedor unificado (autocompletado con lista inicial, soporte dark y feedback en modal PDF, ficha de proveedor y Nueva compra).
- Flujo iAVaL (Validador de IA de remitos) — primera versión funcional:
  - Backend:
    - Endpoints nuevos:
      - `POST /purchases/{purchase_id}/iaval/preview` — Extrae texto del PDF, construye prompt con datos actuales de la compra, invoca IA y retorna propuesta estructurada + diffs.
      - `POST /purchases/{purchase_id}/iaval/apply` — Aplica cambios al borrador según la propuesta recibida, registra auditoría y persiste.
    - Utilidades:
      - Extracción de texto de PDF con `pdfplumber` (fallback seguro si no está disponible).
      - Builder de prompt con esquema de salida JSON estricto.
      - Normalización de salida IA y coerción a JSON (tolerante a prefijos/prosa del proveedor).
      - Detección de diffs permitidos:
        - Header: `remito_number`, `remito_date`, `vat_rate`.
        - Líneas por índice: `qty`, `unit_cost`, `line_discount`, `supplier_sku`, `title`.
      - Auditoría en `apply` (acción `purchase.iaval.apply`).
  - Frontend:
    - Servicios en `frontend/src/services/purchases.ts`:
      - `iavalPreview(id)` y `iavalApply(id, proposal, emitLog?)`.
    - UI en `frontend/src/pages/PurchaseDetail.tsx`:
      - Botón “iAVaL” visible en BORRADOR (deshabilitado si no hay PDF adjunto).
  - Modal de revisión de cambios: muestra confianza, comentarios, diffs de header y líneas; casilla “Enviar logs de cambios” para activar registro; botón “Sí, aplicar cambios” que aplica cambios y, si corresponde, habilita enlaces de descarga del log.
  - Seguridad/Reglas:
    - Operación limitada a estado BORRADOR y requiere al menos un PDF adjunto.
    - Cambios aplicables restringidos a campos permitidos (sin re-asociación automática de productos).

- Otras capacidades ya presentes (resumen):
  - Importación y edición de borradores de compras con cálculo de totales e IVA.
  - Validación de líneas (vinculación SKU proveedor / producto), creación rápida de productos y creación masiva.
  - Confirmación de compra con aplicación de deltas de stock y reenvío de stock en confirmadas.
  - Logs de importación y descarga de JSON de auditoría.

## Implementaciones pendientes (próximos hitos)

Hito 0 — Consolidación iAVaL (estado actual y cierre)
- Documentación específica del flujo iAVaL
  - Detallar en `docs/PURCHASES.md` el flujo, precondiciones, campos afectados, mensajes de error comunes y ejemplos de salida.
  - Documentar variables de entorno para IA: `OPENAI_API_KEY`, `OPENAI_MODEL`, `AI_DISABLE_OLLAMA=true`, timeouts.
- Pruebas automatizadas
  - Backend: tests de preview/apply con IA mockeada (JSON determinista), validando diffs y actualización de compra.
  - Frontend: smoke test del modal iAVaL y happy path de aplicación, y caso “sin diferencias”.
- UX/Ergonomía iAVaL
  - Plegado/paginación de diffs extensos, aviso cuando la confianza sea baja y resaltado claro de “sin diferencias”.
- Observabilidad y trazabilidad
  - Incluir `prompt_id`/`correlation_id` en logs; métricas básicas: ratio de aplicación, tiempo de respuesta, tasa de neutral/no-op.
- Estado proveedor IA
  - Forzar JSON-only en OpenAI (modo `json_object`), Ollama deshabilitado por env; fallback defensivo en preview para evitar 502 (ya implementado).

Hito 1 — Dominio SKU dual (SKU interno y SKU de proveedor)
- Objetivo
  - Asegurar que el sistema maneje y exponga claramente el SKU interno (editable) y el SKU de proveedor por cada relación proveedor–producto.
- Modelo/Datos (revisión de lo existente)
  - `Variant.sku` es el SKU interno único (global). Mantener constraint único.
  - `SupplierProduct.supplier_product_id` es el SKU del proveedor (único por `supplier_id`). Ya existe `UniqueConstraint(supplier_id, supplier_product_id)`.
  - `SupplierProduct.internal_product_id`/`internal_variant_id` vinculan a producto/variante internos. Mantener como fuente de verdad del mapeo.
  - Acciones: agregar índices si faltan en consultas de búsqueda por `supplier_id, supplier_product_id` y por `internal_variant_id`.
- Endpoints Backend
  - [Implementado] `PUT /variants/{id}/sku` (CSRF, admin|colaborador): editar SKU interno (valida regex y unicidad; audita cambio en `AuditLog`).
  - [Implementado] `POST /supplier-products/link` (CSRF): cuerpo `{ supplier_id, supplier_product_id, title?, internal_variant_id }` crea o actualiza la relación con validaciones (upsert amigable).

Hito 1.1 — Taxonomía manual, asociación en productos y exportación de stock
- Objetivo
  - Permitir crear manualmente categoría y subcategoría planas, asociarlas a productos existentes desde la UI y ofrecer exportación XLS desde Stock.
- Modelo/Datos (vigente)
  - `Category.kind` distingue `category` y `subcategory`; `parent_id` se conserva temporalmente para compatibilidad y no condiciona las selecciones nuevas.
  - `Product.category_id` y `Product.subcategory_id` son FK independientes a `categories.id` y se validan contra su `kind`.
- Endpoints Backend
  - [Implementado] `GET /categories?kind=` y `POST /categories` con `{name, kind}` para búsqueda y alta manual por tipo.
  - [Implementado] `PATCH /products/{product_id}` acepta `category_id` y `subcategory_id`, valida el tipo y audita los cambios.
  - [Implementado] `GET /stock/export.xlsx` (roles: cliente|proveedor|colaborador|admin): genera XLS con `CATEGORIA` en formato `Categoría > Subcategoría` y respeta los filtros del listado.
- Frontend
  - Productos (`/productos`):
    - [Implementado] Autocompletes escribibles independientes: al no encontrar un nombre ofrecen `Agregar “…”` y crean el tipo correspondiente sin exigir padre.
    - [Implementado] La ficha del producto permite asociar y modificar ambos campos independientemente.
    - En ficha mantener y documentar edición de SKUs: ya existe `PUT /variants/{id}/sku` para SKU propio y modal “Agregar SKU de proveedor” que usa `POST /supplier-products/link`.
  - Stock (`/stock`):
    - [Implementado] Botón oscuro “Descargar XLS” que llama a `GET /stock/export.xlsx` respetando filtros vigentes y descarga el archivo.
- Criterios de aceptación
  - [Hecho] Se pueden crear `category` y `subcategory` manualmente desde `/productos`, incluso con el mismo nombre entre tipos.
  - [Hecho] En la ficha se pueden asignar/modificar ambos valores y persisten en `Product.category_id`/`Product.subcategory_id`.
  - En la ficha se puede modificar SKU propio (variante) y SKU proveedor (vía vínculo) conforme endpoints actuales.
  - En `/stock` se descarga un XLS con columnas y datos solicitados, respetando filtros.
  - Auditoría: cambios de categoría quedan registrados en `AuditLog`.


  - [Implementado] Borrado de productos:
    - `DELETE /catalog/products` (CSRF): borrado con reglas. Bloquea cuando hay stock (`400`) o referencias en compras directas/indirectas (`409`); devuelve resumen con `deleted`, `blocked_stock`, `blocked_refs` para lotes.
    - `DELETE /products` (CSRF): borrado directo (no aplica reglas de stock/referencias). Pensado para usos internos y tests; elimina el producto y sus `SupplierProduct` asociados; devuelve `{ requested, deleted }`.
  - [Implementado] `GET /suppliers/search?q=`: autocompletar por `name|slug` (like, limit 20) para UI.
  - [Implementado] `GET /products/{product_id}/variants`: lista variantes del producto (id, sku, name, value) para alimentar modales de vínculo.
- Frontend
  - [Implementado] Componente `SupplierAutocomplete` creado (debounce, teclado, loading, vacío) e integrado en el modal de vínculo de la ficha.
  - [Implementado] Ficha de producto: botón “Agregar SKU de proveedor” abre modal con autocompletar de proveedor, `supplier_sku`, selector de variante interna y título opcional; al guardar, llama al upsert y refresca ofertas.
  - Compras: al editar una línea `SIN_VINCULAR`, permitir ingreso de `supplier_sku`; si coincide (supplier_id, supplier_sku) vincula y cambia a `OK`.
- Confirmación de compra (interacción con SKUs)
  - Durante `POST /purchases/{id}/confirm`, auto-vincular líneas no resueltas cuando (supplier_id, supplier_sku) existe y apunta a `internal_variant_id` válido.
- Criterios de aceptación
  - Se puede editar el SKU interno de una variante y persiste con unicidad garantizada.
  - Es posible vincular un nuevo SKU de proveedor a una variante desde UI y backend lo refleja (idempotente si ya existía).
  - El autocompletado de proveedor funciona en modales y formularios pertinentes.
  - En confirmación, líneas con `supplier_sku` reconocido se vinculan automáticamente.

Hito 2 — Confirmación de compras: correcciones de stock y seguridad transaccional
- Objetivo
  - Hacer la confirmación idempotente, precisa en stock y segura en concurrencia.
- Backend
  - Transacción atómica con nivel de aislamiento adecuado; locks pesimistas sobre `variants`/`inventory` al ajustar stock.
  - Redondeo consistente: cantidades enteras, precios con `Decimal` (2 decimales), control de desvío acumulado.
  - Idempotencia: marca de confirmación y protección ante re-ejecución (no duplica movimientos).
  - Price history: actualizar `SupplierProduct.current_purchase_price` y registrar `SupplierPriceHistory` en cada línea confirmada.
  - Auto-link previo a confirmar por (supplier_id, supplier_sku) cuando falte `product_id`/`variant_id`.
- Criterios de aceptación
  - Repetir confirmación no cambia stock ni duplica historial; responde 409 o 200 idempotente con indicación de “ya confirmado”.
  - Movimientos de stock consistentes con sumatoria de líneas; diferencias por redondeo ≤ $0.01.
  - Historial de precios creado por cada línea con precio válido.

Hito 3 — UI: Autocomplete de proveedor en fichas y flujos relevantes
- Objetivo
  - Reemplazar inputs numéricos de proveedor por un autocompletar usable y rápido.
- Backend
  - `GET /suppliers/search?q=` paginado, orden por `name`, retorna `{ id, name, slug }` (máx. 20).
- Frontend
  - Componente reutilizable `SupplierAutocomplete` (debounce 250ms, teclado accesible, loading state).
  - Usos:
    - [Implementado] Modal “Agregar SKU de proveedor” en ficha de producto.
    - [Implementado] Filtros de proveedor en `ProductsDrawer` y `Stock` reemplazados por autocompletar.
    - [Pendiente] Otros formularios con selección de proveedor (alta rápida, panel admin, usuarios, importación PDF, Compras listado) a migrar a autocompletar.
- Criterios de aceptación
  - Teclado: navegar, seleccionar; mouse: clic.
  - Vacío/no resultados: estados amigables, sin errores en consola.

Hito 1.2 — Ventas y Clientes (MVP)
- Backend: modelos `Customer`, `Sale`, `SaleLine`, `SalePayment`, `SaleAttachment` + endpoints mínimos (`/sales`, `/sales/customers`, adjuntos).
- Frontend: páginas `/clientes` y `/ventas`; botón desde Dashboard. Registro de venta descuenta stock y permite crear cliente mínimo en línea.
- Próximos: listado de ventas, anulación (reponer stock), reportes.

Hito 4 — Pipeline de extracción (PDF remito) más robusto
- Objetivo
  - Reducir dependencia de razonamiento IA en campos estructurables.
- Acciones
  - Extracción determinista de cabeceras y tabla (regex + heurísticas) antes de IA.
  - Perfiles de proveedor (Santa Planta primero): mapeos de columnas, normalizaciones (tildes, mayúsculas, separadores decimales), formatos de fecha.
  - OCR fallback con `ocrmypdf` cuando el PDF no tenga capa de texto o la calidad sea pobre (flag de diagnóstico en respuesta).
  - Artefactos: guardar tabla parseada (CSV/JSON) y comparación con borrador.
- Criterios de aceptación
  - Para Santa Planta, ≥ 95% de líneas correctamente parseadas sin IA en casos de prueba conocidos.
  - El preview iAVaL emite menos diffs triviales (p. ej. normalizaciones de formatting).

Hito 5 - Chatbot administrativo con acceso controlado
- Objetivo
  - Incorporar un chatbot corporativo con control de acceso estricto y soporte a tiempo real para desarrollo y soporte.
- Alcance
  - Roles diferenciados (Admin vs Colaborador) con permisos según alcance de información y capacidad de escritura limitada a `PR/`.
  - Integración con proveedor de SSO/MFA open source (p.ej. Keycloak/Authentik) usando OIDC y emisión de tokens con claims de rol.
  - Capa de gateway para repositorio en modo lectura y endpoint restringido para sugerencias en `PR/`.
  - Pipeline RAG con chunking etiquetado por rol y actualización incremental tras cambios en el repositorio.
  - Auditoría centralizada de consultas, respuestas y modificaciones, con reportes para admins.

Hito 5.1 - Funcionalidad "Mercado" (comparación de precios)
- Objetivo
  - Permitir a admins y colaboradores comparar rápidamente los precios de venta internos con los rangos actuales del mercado para tomar decisiones de precios informadas.
- Estado actual: **backend observable y módulo Vue activos; React permanece como fallback temporal**
  - Documentación completa en `docs/MERCADO.md` con plan de 10 secciones (alcance, UI/UX, modelo de datos, fuentes, worker scraping, seguridad, testing, futuras mejoras).
  - Componente frontend `Market.tsx` implementado con tabla de productos mostrando: nombre, precio venta (ARS), rango mercado (min-máx), última actualización, categoría y botón de detalle.
  - Navegación configurada: nueva ruta `/mercado` protegida (solo admin/colaborador), botón "Mercado" agregado en `AppToolbar` junto a "Productos".
  - Filtros implementados: búsqueda por nombre/SKU, filtro por proveedor (autocomplete) y categoría (dropdown).
  - Indicadores visuales de comparación: precio por debajo, dentro o por encima del rango de mercado con colores distintivos.
- Implementado: Base de Conocimiento Canónica; `market_sources` fue reemplazada por activos etiquetados/capacitados y perfiles técnicos con IDs compatibles. Mercado conserva API, scraping, scheduler, alertas e histórico.
- Estado operativo actualizado el 2026-07-21: worker `market_worker` Docker saludable, heartbeat vigente y cola `market` sin mensajes pendientes; las fuentes y observaciones quedan auditadas por producto y trabajo.
- Implementado: consumidor dedicado, jobs persistentes e idempotentes, histórico de tres años, política ARS/promedio y observabilidad por cola, producto y fuente.
- Migración Vue: módulo `market` activo en Vue sobre `/mercado`; React se conserva como fallback durante un ciclo estable.
- Auditoría y plan: `docs/MARKET_CURRENT_STATE_20260721.md`.
- Evolución 2026-07-26: Centro Vue **Conocimiento**, worker dedicado y Enrich knowledge-first desplegados; evidencia en `docs/CANONICAL_KNOWLEDGE_DEPLOYMENT_SMOKE_20260726.md`.
- Seguridad Mercado 2026-07-26: scraping, promedio y agregados sólo aceptan conocimiento validado; el perfil migrado conserva ARS pero requiere confirmar entrega argentina desde **Conocimiento** antes de volver a participar.
- Detalle Producto 2026-07-26: edición confirmada del SKU canónico activa en Vue para staff, con formato estricto, normalización, auditoría y rechazo transaccional de duplicados.
- Criterios de aceptación
  - Admin/Colaborador pueden visualizar lista de productos con comparación de precios vs mercado.
  - Scraping funcional para al menos 3 fuentes obligatorias (MercadoLibre, tienda competidora, fabricante).
  - Modal de detalles muestra todas las fuentes con enlaces clickeables y permite actualización manual.
  - Tests de scraping cubren casos de éxito, fallo de fuente individual y formato de precio no reconocido.

### Ventas / Clientes (Sprint 1 + Sprint 2 parcial)
- Modelos y endpoints base de Customers y Sales (BORRADOR/CONFIRMADA/ENTREGADA/ANULADA) con líneas, pagos y adjuntos.
- Devoluciones parciales: `POST /sales/{id}/returns` + reposición de stock y auditoría `return_create`.
- Timeline consolidado: `GET /sales/{id}/timeline` (audit + pagos + devoluciones) para UI.
- Reportes agregados:
  - Ventas netas: `GET /sales/reports/net` (bruto, devoluciones, neto, ventas_count, devoluciones_count).
  - Top productos: `GET /sales/reports/top-products` (qty/monto vendidos, devueltos y netos).
  - Top clientes: `GET /sales/reports/top-customers` (bruto, devoluciones, neto, conteos).
- Cache in-memory TTL (60s) para reportes con invalidación autom. al confirmar venta o crear devolución.
- Libro de stock inicial: tabla `stock_ledger` + hooks en confirmación de venta (delta negativo) y devolución (delta positivo) con `balance_after`.
- Historial de stock por producto: `GET /products/{id}/stock/history` paginado.
- Búsqueda rápida de clientes: `GET /sales/customers/search?q=` con ranking (document_number exacta, nombre prefix, etc.).
- Endpoint dedicado de pagos `GET /sales/{id}/payments` (optimiza UI polling).
- Clamp automático de `discount_amount` al confirmar si excede `subtotal` (`sale_discount_clamped` audit).
- Indexación adicional ventas (status+sale_date, customer_id+sale_date) para acelerar filtros y reportes.
- Auditoría extendida: `sale_lines_ops`, `sale_payment_add`, `sale_confirm`, `sale_discount_clamped` con `elapsed_ms` y `stock_deltas`.
- Tests: lifecycle, timeline, reportes (net/top), ledger consistencia, clamp de descuento.

Pendiente siguiente iteración Ventas:
- Margen / costo en reportes (integrar costos de compra o precio promedio).
- Apoyo a notas de crédito / facturación y numeración de comprobantes.
- Depósitos múltiples y proyección de stock (reservas vs disponible).
- Paginación y filtros avanzados en historial de stock (fuente, rango fechas, tipo de movimiento).
- Prorrateo de descuento global a líneas para métrica de margen por producto.
- Entregables
  - Documentación viva: nuevos archivos `docs/CHATBOT_ARCHITECTURE.md`, `docs/CHATBOT_ROLES.md`, actualización de `README.md` y `docs/roles-endpoints.md`.
  - Suite de pruebas (unitarias/integración) para autenticación, gateway del repositorio, RAG y auditoría.
  - Scripts de soporte (`scripts/build_chatbot_index.py`, diagnósticos de auditoría) documentados en `AGENTS.md`.

Hito 5 — Pruebas y documentación cruzada
- Tests
  - Backend: unit/integration para endpoints nuevos (`variants/sku`, `supplier-products/link`, `suppliers/search`, confirmación idempotente).
  - Frontend: pruebas del componente `SupplierAutocomplete` y flujo de agregar SKU de proveedor.
- Documentación
  - Actualizar `docs/PURCHASES.md`, `docs/SUPPLIERS.md` y esta hoja de ruta al finalizar cada hito.

Hito 6 — Despliegue y migraciones
- Migraciones
  - Agregar índices que falten; no se prevén columnas nuevas críticas (revisión post-impl.).
- Rollout
  - Feature flags donde aplique; checklist de rollback.
- Criterios de aceptación
  - Migraciones aplican en < 2s en dataset de prueba y no bloquean el arranque.

## Mejoras de Enriquecimiento IA (Priorización Futura)

### Contexto Actual
El enriquecimiento de productos con IA (`POST /products/{id}/enrich`) está funcional con:
- ✅ Búsqueda web obligatoria (MCP Web Search via DuckDuckGo)
- ✅ Jerarquía de fuentes (fabricante > marketplaces > grow shops)
- ✅ Generación de descripción en tono argentino con voseo
- ✅ Keywords SEO integradas al final de la descripción
- ✅ Archivo de fuentes consultadas en `/media/enrichment_logs/`
- ✅ Corrección automática de encoding UTF-8 corrupto

### 🔴 Prioridad ALTA: Bulk Enrich Asíncrono

**Problema actual**:
- `POST /products/enrich-multiple` ejecuta **secuencialmente** hasta 20 productos
- Tiempo estimado: 20 productos × 12s promedio = **4 minutos**
- **Bloquea un worker de FastAPI** completo durante toda la operación
- **Timeout en proxy/nginx** (típicamente 60-90s) corta la conexión antes de terminar
- **Sin retry ni recuperación** si falla a mitad del batch

**Impacto**:
- Imposible enriquecer lotes grandes (50-100 productos)
- Experiencia de usuario degradada con timeouts frecuentes
- Workers de FastAPI bloqueados impactan otras requests

**Soluciones propuestas** (implementar una):

1. **Background Tasks de FastAPI** (Rápida - 30 min)
   - Usa `BackgroundTasks` nativo de FastAPI
   - Libera el response inmediatamente
   - Sin dependencias adicionales
   - ❌ Limitaciones: no sobrevive restart, sin retry, sin monitoreo de progreso

2. **Dramatiq Worker** (Robusta - 2-3 hs)
   - Cola persistente en Redis (ya disponible en `docker-compose.yml`)
   - Retry automático con backoff exponencial
   - Monitoreo de progreso via polling de estado
   - Puede procesar 100+ productos sin timeout
   - ✅ Recomendada para producción

**Criterios de aceptación**:
- Bulk enrich de 50 productos completa sin timeout
- Response HTTP retorna inmediatamente con `job_id`
- Frontend puede consultar progreso del job
- Workers de FastAPI no se bloquean

### 🟡 Prioridad MEDIA: Valor de Mercado con Fechas

**Problema actual**:
- DuckDuckGo HTML **no devuelve fecha de publicación** de los resultados
- OpenAI no puede filtrar precios por antigüedad (requisito: últimos 4 meses)
- Mayoría de enriquecimientos reportan: *"ADVERTENCIA: Precio con más de 4 meses de antigüedad, probablemente desactualizado"*

**Soluciones propuestas**:

1. **API con metadatos de fecha** (Mejor, costo ~$50-100/mes)
   - SerpAPI, Bing Search API, Google Custom Search
   - Devuelven `published_date`, `last_modified` por resultado
   - Permite filtrado preciso por rango de fechas
   
2. **Heurísticas de scraping** (Intermedia)
   - Detectar patrones en URL: `/2024/`, `/2025/`
   - Parsear snippet: "hace 2 días", "hace 3 semanas"
   - Mejorar prompt para que OpenAI infiera actualidad del contexto

3. **Relajar validación** (Pragmática - 15 min)
   - Cambiar advertencia a: *"Valor de mercado estimado: $X ARS (fecha de publicación no verificada)"*
   - Mejorar transparencia sin bloquear por falta de fecha

**Criterios de aceptación**:
- ≥80% de enriquecimientos con precios NO muestran advertencia de desactualización
- Precios realmente antiguos (>6 meses) se omiten o identifican claramente

### 🟢 Prioridad BAJA: Datos Técnicos Opcionales

**Problema actual**:
- Peso, alto, ancho, profundidad raramente se completan
- Grow shops no publican especificaciones técnicas en snippets
- Snippets de DuckDuckGo limitados a ~150 caracteres

**Soluciones propuestas**:

1. **Búsqueda dirigida al fabricante**
   - Modificar prompt para buscar PRIMERO en sitio oficial del fabricante
   - Segunda búsqueda en fichas técnicas de grow shops

2. **Scraping del sitio del fabricante**
   - Si se identifica URL oficial, hacer fetch completo de la página
   - Extraer tabla de especificaciones con BeautifulSoup
   - Requiere manejo de rate limits y caching

3. **Incentivos en prompt**
   - Recompensar a la IA por encontrar datos técnicos
   - Ejemplo: "BONIFICACIÓN: Si encuentras peso/dimensiones, inclúyelos para mejorar la ficha"

**Criterios de aceptación**:
- ≥50% de productos enriquecidos tienen al menos 2 campos técnicos completados (peso o dimensiones)

### Documentación Relacionada
- `docs/ENRICHMENT_LOGS.md` - Logging y diagnóstico de enriquecimiento
- `docs/PRODUCTS_UI.md` - UI de productos y enriquecimiento
- `mcp_servers/web_search_server/` - Servidor MCP de búsqueda web

---

Hito 7 - Chatbot: Consulta de precios en lenguaje natural (REDEFINIDO - Ver "Roadmap de Inteligencia Growen")
- **Estado**: Tool calling asíncrono implementado; validación y retiro legacy pendientes.
- **Diagnóstico actual**:
  - ✅ Matcher `price_query` y servicio `price_lookup.py` implementados (funcional pero marcado DEPRECATED).
  - ✅ Frontend `ChatWindow` representa respuestas `price_answer` con detalle de ofertas.
  - ✅ MCP Products Server implementado con tools `get_product_info` y `get_product_full_info`.
  - ✅ Router asíncrono y descubrimiento MCP conectados en los canales principales.
  - ⚠️ Fallback a `price_lookup.py` funcional pero no escala ni permite acceso a información externa actualizada.
- **Plan de evolución**:
  - Este hito se reestructura como parte de la **Etapa 0: Refactorización Core AI** (ver sección superior).
  - Una vez completada la Etapa 0, el chatbot podrá:
    - Responder consultas de precio/stock usando tool calling asíncrono.
    - Acceder dinámicamente a MCP Products para información actualizada.
    - Escalar a nuevas tools (ventas, proveedores, equivalencias SKU) sin modificar el núcleo del router.
  - Etapas 1-5 expandirán las capacidades con RAG, roles, BI y más.
- **Acciones pendientes inmediatas**:
  - Mantener la venv Python 3.14.6+ y ejecutar `scripts/check-quality.ps1`.
  - Validar paridad y retirar `chat_with_tools`, schemas estáticos y RPC legacy.
- **Criterios de aceptación** (actualizados):
  - El chatbot responde consultas de precio/stock sin bloqueos ni timeouts.
  - Tool calling funcional con inyección de contexto de usuario (rol).
  - Tests existentes (`test_ai_router.py`, `test_chat_ws_price.py`) pasan con implementación asíncrona.
  - `price_lookup.py` puede ser retirado tras migración completa de canales (WS, Telegram).

Hito 8 — Módulo MCP de Ventas Conversacionales
- Objetivo
  - Permitir a usuarios con roles `Colaborador` o `Admin` registrar ventas utilizando lenguaje natural, interactuando con un nuevo servicio MCP.
- Arquitectura
  - Crear un nuevo servicio MCP en `mcp_servers/sales_server/`, similar al existente `mcp_products`.
  - El servicio consumirá exclusivamente los endpoints de la API de ventas (`/sales`) y no tendrá acceso directo a la base de datos.
  - Las ventas creadas por este medio se registrarán en estado `BORRADOR`.
- Backend / MCP Service
  - [Nuevo] Crear el archivo `mcp_servers/sales_server/tools.py`.
  - [Nuevo] Implementar la herramienta principal `registrar_venta_conversacional(orden_usuario: str)`.
  - [Nuevo] Desarrollar un manejador de estado para el flujo conversacional (ej. `esperando_productos`, `esperando_cliente`, `esperando_confirmacion`).
  - [Nuevo] Implementar funciones auxiliares para interactuar con la API:
    - `_buscar_producto(nombre: str)` que llama a `GET /sales/catalog/search` y maneja desambiguación.
    - `_gestionar_cliente(nombre: str)` que llama a `GET /sales/customers/search` y ofrece crear el cliente si no existe.
    - Una función para construir el payload y enviarlo a `POST /sales`.
- Flujo Conversacional
  - El sistema solicitará interactivamente la información faltante (productos, cliente).
  - Antes de crear la venta, se mostrará un resumen completo para la confirmación explícita del usuario.
- Criterios de aceptación
  - El módulo es completamente conversacional y guía al usuario para completar la información.
  - La búsqueda de productos y clientes es flexible y maneja ambigüedades.
  - La creación de la venta solo ocurre tras la confirmación del usuario.
  - El módulo se integra únicamente a través de la API RESTful existente.
  - La venta se crea correctamente en estado `BORRADOR`.

## Detalles técnicos por área

- Backend (compras):
  - Modelos: `Purchase`, `PurchaseLine`, `PurchaseAttachment` (ver `db/models.py`).
  - Rutas: router de compras (ver `services/routers/purchases.py`).
  - iAVaL: helpers para PDF/prompt/JSON, endpoints `preview` y `apply` (precondiciones, diffs, auditoría).

- IA:
  - Router y providers en `ai/`. Uso de `Task.REASONING`.
  - Prompt con esquema de salida JSON: `{ header, lines[], confidence, comments[] }`.

- Frontend:
  - Servicios en `frontend/src/services/purchases.ts` (`iavalPreview`, `iavalApply`).
  - Pantalla `PurchaseDetail.tsx`: botón “iAVaL”, modal y refresco tras `apply`.

## Clientes y Ventas — Fases 0 a 4 (2026-07-17)

- [x] Contratos consistentes: quote, borrador idempotente, CSRF, totales con costos adicionales y OpenAPI sin operation IDs duplicados.
- [x] Cantidades decimales en inventario, compras, ventas, devoluciones, ledger y faltantes.
- [x] Clientes Vue: CRUD, reactivación, ficha 360°, historial, métricas y cuenta corriente.
- [x] Ventas Vue: listado, detalle, recibo, pagos, devoluciones, adjuntos y POS.
- [x] Reservas explícitas, cuenta corriente append-only, límite de crédito, margen, canales y segmentación calculada.
- [x] Corte reversible React/Vue mediante manifiesto modular único y assets separados.
- [x] Proxy canónico `/api`, transportes HTTP/descargas/WS/SSE, capacidades y telemetría por release/correlation ID.
- [x] Nginx dual generado desde el manifiesto, aliases de imágenes y fallback React sin cambios de rutas públicas.
- [x] Quality gate Vue con tipos, unitarias, Playwright E2E, build y auditoría.
- [x] Servicios administrativos Vue: resumen, workers, health, start/stop, auto-start, dependencias, logs/SSE y MCP con permisos alineados al backend.
- [x] Usuarios y Backups Vue con capacidades admin, formularios, confirmaciones, reset seguro y descarga autenticada.
- [x] Completar panel admin Vue: Drive Sync, Diagnóstico de catálogos, Scheduler, Conocimiento y Chat Inbox.
- [x] Retrospectiva y handoff técnico del corte administrativo en `docs/RETROSPECTIVE_FRONTEND_ADMIN_20260718.md`; registra el 500 sin evidencia suficiente y el reinicio requerido ante un Vite desactualizado.

Pendiente operativo: ejecutar migración y pruebas concurrentes contra PostgreSQL real en integración antes del corte productivo.

## Cómo probar manualmente (resumen)

- Caso base: Compra en BORRADOR con PDF adjunto en `data/purchases/{id}/`.
- Abrir la compra en el frontend → click en “iAVaL” → revisar cambios → “Sí, aplicar cambios”.
- Verificar actualización de header/líneas en la UI y logs de auditoría.

## Riesgos y consideraciones

- Respuestas de IA no estrictamente JSON → se mitigó con normalización/parsing robusto; mantener defensivo.
- PDFs con OCR deficiente → puede requerir `force_ocr` en flujos de importación o ajustes de extracción.
- No se realizan re-asociaciones de producto automáticas en esta versión.

## Trazabilidad y mantenimiento

- Por favor, actualizar este Roadmap en cada PR/commit que afecte:
  - Endpoints, modelos, capa IA, lógica de validación o UI.
  - Dependencias, variables de entorno o scripts de entorno.
- Vincular commits/PRs relevantes y anotar brevemente el impacto.

---
Notas de mantenimiento: Si se modifica la lógica de migraciones o diagnósticos, actualizar también `docs/MIGRATIONS_NOTES.md` y el inventario en `AGENTS.md`.







