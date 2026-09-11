<!-- NG-HEADER: Nombre de archivo: Roadmap.md -->
<!-- NG-HEADER: Ubicación: Roadmap.md -->
<!-- NG-HEADER: Descripción: Hoja de ruta vigente de pendientes y trabajo futuro de Growen. -->
<!-- NG-HEADER: Lineamientos: Ver AGENTS.md -->

# Roadmap de Growen

Este documento contiene únicamente trabajo pendiente o futuro. El historial de estados anteriores se conserva en [`docs/archive/ROADMAP_HISTORY.md`](docs/archive/ROADMAP_HISTORY.md); los cambios entregados se registran en [`CHANGELOG.md`](CHANGELOG.md).

## Documentación y SiYuan

- [ ] Integrar la sincronización Git → SiYuan al gate manual de publicación después de su ventana de estabilidad local.
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
- [ ] Completar login, push y pull contra el registro autenticado y TLS ya
  saludable; publicar sólo imágenes aprobadas por Trivy y conservar SBOM y
  manifiesto de digests por commit.
- [ ] Ejecutar las fases `Bootstrap` y `Application` con topología `SingleNode`
  después de aprobar independientemente migración y despliegue.
- [ ] Ejecutar el smoke autenticado desde otro dispositivo de la LAN contra
  `https://192.168.100.100` después de provisionar un certificado con IP SAN.
- [ ] Aplicar en una ventana controlada la migración `20260909_user_active` y la
  copia verificada de media privada; conservar originales hasta validar rollback.
- [ ] Ejecutar carga y failover del rate limit Redis y del proxy TLS en el Swarm
  productivo antes de declarar operativa la primera puesta en producción.
- [ ] Completar smokes autenticados de API, WebSocket, Telegram y MCP para los roles soportados.
- [ ] Resolver el drift histórico de Alembic en una revisión separada y verificable.
- [ ] Consolidar la observabilidad de costes, latencia y errores de proveedores IA.
- [ ] Medir periódicamente activaciones y consumo de tokens de skills Growen/Superpowers para ajustar descripciones sin debilitar los gates locales.
- [ ] Extender `scripts/audit_agentic_environment.py` para reportar locks de `scripts/agent_lock.py` vencidos y olvidados en `.agents/state/locks/`.
- [ ] Evaluar `git worktree add` por sesión de agente como aislamiento físico real, alternativo al lock lógico cooperativo descrito en `docs/architecture/AGENT_ORCHESTRATION.md`; requiere decisión explícita antes de implementarse.

## Frontend Vue

- [ ] Completar la paridad funcional pendiente y los smokes visuales autenticados.
- [ ] Retirar gradualmente el fallback React después de dos releases estables y siete días sin incidentes críticos.
- [ ] Migrar los consumidores React restantes a contratos canónicos antes de eliminar código legado.
- [ ] Retirar los adaptadores públicos de Enrich después del ciclo estable de compatibilidad.

## IA, Mercado y operaciones

- [x] Activar túnel y proxy DNS MeLi; gateway/worker saludables y HTTPS público verificado el 2026-09-04 (callback incompleto 422, webhook GET 405, health bloqueado 404).
- [x] Autorizar al primer vendedor MeLi tras ampliar `meli_accounts.scopes` a `TEXT`: cuenta activa, permisos de 505 caracteres, tokens cifrados y state consumido verificados el 2026-09-05.
- [ ] Procesar una notificación POST real, probar sincronización de stock y renovación de tokens; validar además inicio OAuth con sesión admin y CSRF.
- [x] Solicitar explícitamente `read write offline_access` y distinguir ausencia de refresh token de vencimiento OAuth; validación real del permiso pendiente del vendedor.
- [x] Incorporar diagnóstico seguro del rechazo OAuth sin códigos ni tokens; cuatro pruebas del gateway aprobadas el 2026-09-04. Repetición real pendiente de autorización del vendedor.

- [x] Unificar descubrimiento, validación, alta y extracción de Mercado en jobs persistentes individuales y masivos, con cuarentena y archivo recuperable.
- [x] Incorporar detección focal de precio y validación manual auditada de ARS/entrega desde el detalle Vue.
- [ ] Medir precisión de evidencia de entrega argentina y ampliar aliases de competidores a partir de resultados reales auditados.
- [x] Incorporar motor de auditoría y coherencia física para Enrich v2 con bloqueo de auto-apply ante inconsistencias y visualización en Vue (2026-09-10).
- [ ] Reejecutar Enrich sobre productos antiguos y validar calidad, deduplicación y estados terminales.
- [ ] Completar evaluaciones RAG por rol, canal e intención con datos clasificados.
- [ ] Evolucionar alertas de Mercado con score de confianza, circuit breaker y recomendaciones explicables con aprobación humana.
- [ ] Incorporar inventario MeLi User Products/multiorigen después de validar el contrato oficial por site; el worker clásico falla cerrado mientras tanto.
- [ ] Completar el consumidor IA supervisado de preguntas/mensajes MeLi, con aprobación humana, rate limiting y auditoría antes de habilitar respuestas.
- [ ] Ejecutar carga sostenida y failover multinodo del gateway/worker MeLi en un Swarm productivo con PostgreSQL y Redis altamente disponibles.
- [ ] Extraer un lock Python mínimo para la imagen MeLi y medir su tamaño/tiempo de build sin perder hashes ni Python 3.14.6.
