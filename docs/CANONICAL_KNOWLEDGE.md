<!-- NG-HEADER: Nombre de archivo: CANONICAL_KNOWLEDGE.md -->
<!-- NG-HEADER: Ubicación: docs/CANONICAL_KNOWLEDGE.md -->
<!-- NG-HEADER: Descripción: Arquitectura y operación de la Base de Conocimiento del Producto Canónico. -->
<!-- NG-HEADER: Lineamientos: Ver AGENTS.md -->

# Base de Conocimiento del Producto Canónico

Desde `20260726_canonical_knowledge_v1`, las URLs y archivos reutilizables pertenecen al `CanonicalProduct`. `CanonicalKnowledgeAsset` representa una página, documento, imagen o video; sus ubicaciones, etiquetas, capacidades, versiones, claims, hechos y eventos se almacenan por separado. `KnowledgeSource` continúa reservado para RAG/Chat global.

Las etiquetas controladas (`manufacturer`, `supplier`, `market`, `manual`, `catalog`, `msds`, `official`, `other`) no son `Product.tags`: no participan en catálogo, MCP Products ni búsquedas de productos. Las capacidades iniciales son `description`, `technical_specs`, `compatibility`, `images`, `manuals`, `price`, `availability`, `offers`, `seo`, `video`, `warranty` y `certifications`.

## Consumidores

- Enrich v3 consulta primero activos confirmados, vigentes y no excluidos, ordenados por confianza y capacidad. La web es fallback; lo descubierto se persiste. Sólo se autoconfirma una clasificación conservadora ≥0,90.
- Mercado consume activos confirmados con etiqueta `market`, capacidad `price` y perfil técnico activo. Las fuentes automáticas deben tener ARS y entrega argentina confirmados; una carga manual explícita puede aportar al promedio sin scraping. `canonical_knowledge_market_profiles` conserva scraping/moneda/validación; no posee nombre, URL ni producto.
- Imágenes y documentos se copian por hash. Incorporar una imagen a la galería comercial requiere acción explícita.
- Videos conservan metadatos, transcripción y frames limitados; no se eluden restricciones de plataformas externas.

Enrich nunca usa `price` para descripción o datos técnicos.

## Confianza y hechos

El puntaje determinista conserva desglose auditable: autoridad 40 %, identidad/validación 20 %, frescura 15 %, acuerdo 15 % y éxito de extracción 10 %. La IA puede ajustar ±10 puntos con razón estructurada. Un fallo o esquema inválido de IA no invalida la ingesta: se conserva el puntaje determinista.

Cada claim tiene confianza y evidencia propias. Claims contradictorios quedan marcados y no reemplazan silenciosamente un hecho confirmado.

## API y roles

`admin` y `colaborador` acceden a:

- `GET/POST /canonical-products/{id}/knowledge`
- `GET/PATCH/DELETE /canonical-products/{id}/knowledge/{asset_id}`
- `POST .../{asset_id}/restore|process|revalidate|locations`
- `POST /canonical-products/{id}/knowledge/upload`
- `GET .../facts|history|jobs`

`PATCH` exige `expected_revision` y devuelve `409` ante conflicto. `DELETE` archiva. Sólo admin puede sobrescribir confianza y administrar `/knowledge-capabilities`; eliminar una capacidad la desactiva para preservar referencias.

Los endpoints `/market/sources/{id}` mantienen el ID de perfil legacy, pero operan sobre el activo y devuelven `knowledge_asset_id`, etiquetas, capacidades y confianza.

## Worker y seguridad

`knowledge_worker` consume `canonical_knowledge`, publica `growen:knowledge_worker:heartbeat` y se verifica en `/health/knowledge-worker`. HTML/PDF remoto se obtiene exclusivamente mediante MCP Web Search con controles SSRF, MIME, redirects, tamaño y timeout. PDFs, OCR, imágenes, video y transcripción aplican los límites `KNOWLEDGE_*` de `.env.example`.

Arranque local:

```powershell
scripts\start-dev.ps1 -McpMode All -WithKnowledgeWorker
```

Compose:

```powershell
docker compose --profile optional up -d redis mcp_web_search knowledge_worker
```

En un despliegue híbrido, `KNOWLEDGE_MCP_WEB_SEARCH_URL` y `ENRICH_MCP_WEB_SEARCH_URL` permiten apuntar los workers al MCP del host sin cambiar el valor productivo por defecto.
