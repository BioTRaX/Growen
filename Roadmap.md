<!-- NG-HEADER: Nombre de archivo: Roadmap.md -->
<!-- NG-HEADER: Ubicación: Roadmap.md -->
<!-- NG-HEADER: Descripción: Hoja de ruta vigente de pendientes y trabajo futuro de Growen. -->
<!-- NG-HEADER: Lineamientos: Ver AGENTS.md -->

# Roadmap de Growen

Este documento contiene únicamente trabajo pendiente o futuro. El historial de estados anteriores se conserva en [`docs/archive/ROADMAP_HISTORY.md`](docs/archive/ROADMAP_HISTORY.md); los cambios entregados se registran en [`CHANGELOG.md`](CHANGELOG.md).

## Documentación y SiYuan

- [ ] Integrar al gate manual la sincronización Git → SiYuan y su modo de reconstrucción explícita después de completar la ventana de estabilidad local.
- [ ] Automatizar el smoke de Attribute Views MCP sobre un workspace SiYuan desechable y versionado.
- [ ] Incorporar el widget Crono al smoke desechable de Attribute Views para validar minutos, segundos, estados, categorías de sólo lectura y checkbox.
- [ ] Integrar el diagnóstico `sync-siyuan-widget.ps1` al gate manual cuando exista un workspace desechable de widgets.
- [ ] Añadir revisión periódica de enlaces, encabezados y modelos retirados al pipeline de calidad.
- [ ] Completar la taxonomía de documentos operativos y retirar referencias históricas de las guías vigentes.

## Plataforma y calidad

- [ ] Reducir la deuda Ruff histórica del árbol completo (798 incidencias en la
  línea base del 2026-09-10) antes de convertir el lint global en compuerta; el
  conjunto modificado y el gate oficial acotado ya terminan en cero.
- [x] Configurar `192.168.100.100/24` como dirección manual del servidor;
  verificada en estado `Preferred` con gateway `192.168.100.1` activo el
  2026-09-10.
- [ ] Confirmar en el router que `.100` esté fuera del pool DHCP, aplicar
  firewall LAN, importar la CA vigente en Windows/Docker Desktop y distribuirla
  a los dispositivos autorizados.
- [x] Completar login, push y pull contra el registro autenticado y TLS ya
  saludable; publicar sólo imágenes aprobadas por Trivy y conservar SBOM y
  manifiesto de digests por commit (2026-09-13, revisión `bb48d80`).
- [x] Ejecutar las fases `Bootstrap` y `Application` con topología `SingleNode`
  después de aprobar independientemente migración y despliegue; los 17 servicios
  estabilizados en estado 1/1 saludable (2026-09-13).
- [ ] Ejecutar el smoke autenticado desde otro dispositivo de la LAN contra
  `https://192.168.100.100` después de provisionar un certificado con IP SAN.
- [x] Aplicar en una ventana controlada la migración `20260909_user_active` y la
  copia verificada de media privada; conservar originales hasta validar rollback
  (2026-09-13).
- [ ] Ejecutar carga y failover del rate limit Redis y del proxy TLS en el Swarm
  productivo antes de declarar operativa la primera puesta en producción.
- [ ] Completar smokes autenticados de API, WebSocket, Telegram y MCP para los roles soportados.
- [ ] Resolver el drift histórico de Alembic en una revisión separada y verificable.
- [ ] Consolidar la observabilidad de costes, latencia y errores de proveedores IA.
- [ ] Medir periódicamente activaciones y consumo de tokens de skills Growen/Superpowers para ajustar descripciones sin debilitar los gates locales.
- [x] Desacoplar y aislar volúmenes y redes entre Docker Compose (Dev) y Docker Swarm (Prod): volumen dedicado `growen_dev_pgdata` y prefijos `growen_dev_*` para prevenir colisiones de nombres y corrupción concurrente de PostgreSQL (2026-09-13).
- [ ] Evaluar `git worktree add` por sesión de agente como aislamiento físico real, después de la serialización actual mediante el ámbito global `git-worktree`; requiere definir rutas, puertos y autoridad del checkout central antes de implementarse.

## Frontend Vue

- [x] Unificar el frontend productivo sobre Vue 3 como SPA principal (rutas raíz y `/login` integradas a `LoginView.vue`), eliminando la dependencia de fallback de React y resolviendo el error de Mixed Content (2026-09-13).
- [x] Edición en línea de nombre canónico en el detalle del producto (`/productos/:id`) con sincronización atómica de títulos vinculados, y normalización de descargas/adjuntos mediante `apiUrl` para evitar redirección a `/login` (2026-09-13).
- [x] Completar la paridad funcional de Proveedores (`/proveedores/:id` con detalle, edición y gestión de adjuntos), Compras, Chat y Dashboard, activando el runtime Vue para todos los módulos de negocio en `modules.json` y regenerando las reglas Nginx (2026-09-15).
- [x] Retiro total y desmantelamiento del código huérfano React legado (`frontend/`, ~23.400 líneas), unificando Dockerfile multietapa a un único build Vue 3 y orientando scripts de desarrollo/despliegue exclusivamente a `frontend-vue` (2026-09-15).
- [x] Saneamiento integral de UI, router y gobernanza: eliminación de textos de transición en Dashboard y AppShell, sustitución de vistas residuales pendientes por `NotFoundView` (404) y actualización de `FRONTEND_MIGRATION_OPERATIONS.md` (2026-09-17).
- [ ] Retirar los adaptadores públicos de Enrich después del ciclo estable de compatibilidad.

## Ventas y Clientes

- [x] Habilitar ventas para colaboradores a precio de costo: cliente tipo `colaborador`, resolución autoritativa de costo vía `SupplierProduct.current_purchase_price`, exposición en `/sales/catalog/search`, cotización autoritativa y experiencia POS Vue con distintivo visual (2026-09-11).
- [x] Dashboard de compras de colaboradores y clientes en el panel de administración (`/admin/compras-dashboard`): agregación analítica comparativa de monto, unidades y órdenes, ratios de participación (share), rankings de compradores y productos, listado de últimas compras y filtros avanzados por colaborador en `GET /sales` (2026-09-13).

## IA, Mercado y operaciones

- [x] Activar túnel y proxy DNS MeLi; gateway/worker saludables y HTTPS público verificado el 2026-09-04 (callback incompleto 422, webhook GET 405, health bloqueado 404).
- [x] Autorizar al primer vendedor MeLi tras ampliar `meli_accounts.scopes` a `TEXT`: cuenta activa, permisos de 505 caracteres, tokens cifrados y state consumido verificados el 2026-09-05.
- [ ] Procesar una notificación POST real, probar sincronización de stock y renovación de tokens; validar además inicio OAuth con sesión admin y CSRF.
- [x] Solicitar explícitamente `read write offline_access` y distinguir ausencia de refresh token de vencimiento OAuth; validación real del permiso pendiente del vendedor.
- [x] Incorporar diagnóstico seguro del rechazo OAuth sin códigos ni tokens; cuatro pruebas del gateway aprobadas el 2026-09-04. Repetición real pendiente de autorización del vendedor.

- [x] Unificar descubrimiento, validación, alta y extracción de Mercado en jobs persistentes individuales y masivos, con cuarentena y archivo recuperable.
- [x] Incorporar detección focal de precio y validación manual auditada de ARS/entrega desde el detalle Vue.
- [ ] Medir precisión de evidencia de entrega argentina y ampliar aliases de competidores a partir de resultados reales auditados.
- [x] Separar el auditor autónomo de Enrich, persistir runs/ítems/feedback,
  deduplicar por huella efectiva y exponer operación Vue (2026-09-13).
- [x] Aplicar `20260913_catalog_audit_v1` en desarrollo, reconstruir ambos
  workers Compose y ejecutar un smoke sintético con Ollama 100 % GPU
  (2026-09-14).
- [x] Ejecutar el primer run controlado del canónico 3 y verificar desde los
  contratos de la UI `queued → running → completed`, clasificación `container`
  y score 100; la repetición terminó `skipped_unchanged` (2026-09-14).
- [ ] Iniciar desde la UI la auditoría de los 29 canónicos.
- [x] Aplicar en producción la migración, imágenes y servicios Swarm preparados
  para el auditor; backup restaurado en PostgreSQL aislado, head
  `20260913_catalog_audit_v1`, 18 servicios en 1/1 y smoke operativo con Ollama
  al 100 % GPU (2026-09-14).
- [x] Separar el control local de `catalog_audit_worker` del controlador Compose:
  reconciliar proceso, heartbeat, PID y worktree desde Workers, impedir roots
  competidores y aislar el nombre del contenedor opcional (2026-09-14).
- [x] Corregir la prioridad de rutas del auditor y exponer en Dashboard/Workers
  la cola Redis, los runs encolados o activos y el progreso persistido
  (2026-09-14).
- [ ] Resolver huérfanos, cuarentenas y feedback surgidos del primer run completo.
- [ ] Completar evaluaciones RAG por rol, canal e intención con datos clasificados.
- [ ] Evolucionar alertas de Mercado con score de confianza, circuit breaker y recomendaciones explicables con aprobación humana.
- [ ] Incorporar inventario MeLi User Products/multiorigen después de validar el contrato oficial por site; el worker clásico falla cerrado mientras tanto.
- [ ] Completar el consumidor IA supervisado de preguntas/mensajes MeLi, con aprobación humana, rate limiting y auditoría antes de habilitar respuestas.
- [ ] Ejecutar carga sostenida y failover multinodo del gateway/worker MeLi en un Swarm productivo con PostgreSQL y Redis altamente disponibles.
- [ ] Extraer un lock Python mínimo para la imagen MeLi y medir su tamaño/tiempo de build sin perder hashes ni Python 3.14.6.
