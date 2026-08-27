<!-- NG-HEADER: Nombre de archivo: Roadmap.md -->
<!-- NG-HEADER: Ubicación: Roadmap.md -->
<!-- NG-HEADER: Descripción: Hoja de ruta vigente de pendientes y trabajo futuro de Growen. -->
<!-- NG-HEADER: Lineamientos: Ver AGENTS.md -->

# Roadmap de Growen

Este documento contiene únicamente trabajo pendiente o futuro. El historial de estados anteriores se conserva en [`docs/archive/ROADMAP_HISTORY.md`](docs/archive/ROADMAP_HISTORY.md); los cambios entregados se registran en [`CHANGELOG.md`](CHANGELOG.md).

## Documentación y SiYuan

- [ ] Implementar sincronización incremental Git → SiYuan basada en hash y actualización explícita.
- [ ] Añadir revisión periódica de enlaces, encabezados y modelos retirados al pipeline de calidad.
- [ ] Completar la taxonomía de documentos operativos y retirar referencias históricas de las guías vigentes.

## Plataforma y calidad

- [ ] Completar smokes autenticados de API, WebSocket, Telegram y MCP para los roles soportados.
- [ ] Resolver el drift histórico de Alembic en una revisión separada y verificable.
- [ ] Consolidar la observabilidad de costes, latencia y errores de proveedores IA.

## Frontend Vue

- [ ] Completar la paridad funcional pendiente y los smokes visuales autenticados.
- [ ] Retirar gradualmente el fallback React después de dos releases estables y siete días sin incidentes críticos.
- [ ] Migrar los consumidores React restantes a contratos canónicos antes de eliminar código legado.

## IA, Mercado y operaciones

- [ ] Reejecutar Enrich sobre productos antiguos y validar calidad, deduplicación y estados terminales.
- [ ] Completar evaluaciones RAG por rol, canal e intención con datos clasificados.
- [ ] Evolucionar alertas de Mercado con score de confianza, circuit breaker y recomendaciones explicables con aprobación humana.
