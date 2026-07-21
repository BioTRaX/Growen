<!-- NG-HEADER: Nombre de archivo: FEATURES_PENDIENTES.md -->
<!-- NG-HEADER: Ubicación: docs/FEATURES_PENDIENTES.md -->
<!-- NG-HEADER: Descripción: Lista consolidada de features pendientes de implementación -->
<!-- NG-HEADER: Lineamientos: Ver AGENTS.md -->

# Features Pendientes de Implementación

> **Última actualización**: 2025-12-23  
> **Fuente**: Análisis de documentación (Roadmap.md, CHAT*.md, SALES.md, MCP.md, RAG.md)

---

## 🔴 Prioridad ALTA

### 1. Refactorización Core AI (Etapa 0)

**Problema**: El router `ai/router.py` es síncrono, impidiendo uso de `chat_with_tools` para consultas MCP en tiempo real.

**Acciones requeridas**:
- [ ] Convertir `AIRouter.run` a `async def`
- [ ] Implementar `generate_async` en `OpenAIProvider` con soporte de tools dinámicas
- [ ] Actualizar endpoints `/chat`, `/ws`, `/telegram/webhook` para usar `await router.run(...)`
- [ ] Sincronizar esquemas JSON de tools entre provider y MCP

**Archivos afectados**:
- `ai/router.py`
- `ai/providers/openai_provider.py`
- `services/routers/chat.py`
- `services/chat/telegram_handler.py`

**Criterios de aceptación**:
- Chatbot responde consultas de stock/precios sin bloqueos
- Tests `test_ai_router.py` y `test_chat_ws_price.py` pasan

---

### 2. Endpoint RAG Search

**Estado**: Solo infraestructura implementada, falta endpoint de búsqueda.

**Acciones requeridas**:
- [ ] Crear `services/routers/rag.py` con endpoint `POST /api/v1/rag/search`
- [ ] Implementar búsqueda por similitud coseno en pgvector
- [ ] Integrar recuperación RAG en respuestas del chatbot

**Ejemplo de implementación** (de `docs/RAG.md`):
```python
@router.post("/search")
async def search_knowledge(query: str, top_k: int = 5, session: AsyncSession = Depends(get_session)):
    embedding_service = get_embedding_service()
    query_vector = await embedding_service.generate_embedding(query)
    stmt = select(KnowledgeChunk).order_by(
        KnowledgeChunk.embedding.cosine_distance(query_vector)
    ).limit(top_k)
    results = await session.execute(stmt)
    return {"query": query, "results": [...]}
```

---

### 3. Bulk Enrich Asíncrono

**Problema**: `POST /products/enrich-multiple` ejecuta secuencialmente hasta 20 productos (4+ minutos), bloqueando workers.

**Opciones de solución**:

| Opción | Tiempo est. | Complejidad |
|--------|-------------|-------------|
| Background Tasks FastAPI | 30 min | Baja |
| Dramatiq Worker | 2-3 hs | Media |

**Criterios de aceptación**:
- Bulk enrich de 50 productos sin timeout
- Response HTTP retorna inmediatamente con `job_id`
- Frontend puede consultar progreso

---

## 🟡 Prioridad MEDIA

### 4. Token Firmado MCP (HMAC/JWT)

**Estado actual**: MCP real con JWT; el rol viaja en claims firmados y no aparece en los argumentos de tools.

**Acciones requeridas**:
- [ ] Implementar firma de token con expiración y claims de rol
- [ ] Lista blanca de tools por rol
- [ ] Rate limiting por rol/IP
- [ ] Auditoría estructurada de invocaciones

**Archivos afectados**:
- `mcp_servers/products_server/tools.py`
- `services/auth.py`

---

### 5. Canales de Venta y Costos Adicionales (Backend)

**Estado**: UI implementada pero cálculo solo en frontend.

**Acciones requeridas**:
- [ ] Integrar `additional_costs` en cálculo de totales del backend
- [ ] Implementar reportes por canal de venta
- [ ] Endpoint PDF oficial del recibo

---

### 6. Mejoras de Valor de Mercado con Fechas

**Problema**: DuckDuckGo HTML no devuelve fecha de publicación.

**Opciones de solución**:
1. API con metadatos (SerpAPI, Bing) - Costo ~$50-100/mes
2. Heurísticas de scraping (patrones de URL, snippets)
3. Relajar validación de fecha

---

## 🟢 Prioridad BAJA

### 7. Sistema de Personas - Persistencia de Estado

De `docs/CHAT_PERSONA.md`:
- [ ] Persistir estado de conversación en BD (no solo memoria)
- [ ] Permitir cambio manual de persona ("actúa como técnico")
- [ ] Personalizar urgencia de stock según historial del cliente
- [ ] Usar tags para filtrar búsquedas directamente en API

---

### 8. Mejoras RAG Futuras

- [ ] Reranking con cross-encoder (`ms-marco-MiniLM-L-12-v2`)
- [ ] Índice IVFFlat cuando haya >10K vectores
- [ ] Hybrid search (vectorial + BM25)
- [ ] Metadata filtering por `product_id`, `category`

---

### 9. Knowledge Base - Mejoras UI

De `docs/KNOWLEDGE_BASE.md`:
- [ ] Soporte para subcarpetas anidadas en `/Conocimientos`
- [ ] Vista previa de contenido de chunks
- [ ] Estadísticas de uso por documento
- [ ] Integración con OCR para PDFs escaneados
- [ ] Drag & drop en UI de upload

---

### 10. Datos Técnicos en Enriquecimiento

**Problema**: Peso, alto, ancho, profundidad raramente se completan.

**Opciones**:
- [ ] Búsqueda dirigida al sitio oficial del fabricante
- [ ] Scraping de tabla de especificaciones
- [ ] Incentivos en prompt para extraer datos técnicos

---

## 📋 Checklist de Features por Documento

### De SALES.md

| Feature | Estado |
|---------|--------|
| Reportes por canal de venta | ⏸️ Pendiente |
| Endpoint PDF recibo | ⏸️ Pendiente |
| Costos adicionales en backend | ⏸️ Pendiente |
| Búsqueda productos trigram/full-text | ⏸️ Pendiente |
| Estructura StockLedger detallada | ⏸️ Pendiente |
| Cache Redis multi-proceso | ⏸️ Pendiente |

### De RAG.md

| Feature | Estado |
|---------|--------|
| Endpoint `/api/v1/rag/search` | ⏸️ Pendiente |
| Integración RAG con chatbot | ⏸️ Pendiente |
| Reranking | ⏸️ Pendiente |
| Monitoreo y métricas | ⏸️ Pendiente |

### De MCP.md

| Feature | Estado |
|---------|--------|
| Token firmado HMAC/JWT | ⏸️ Pendiente |
| Lista blanca tools por rol | ⏸️ Pendiente |
| Rate limiting MCP | ⏸️ Pendiente |
| Métricas de invocaciones | ⏸️ Pendiente |
| Caching de resultados | ⏸️ Pendiente |

---

## Referencias Cruzadas

- **Arquitectura detallada**: `docs/CHATBOT_ARCHITECTURE.md`
- **Roadmap completo**: `Roadmap.md`
- **Estado del RAG**: `docs/RAG.md`
- **Estado del Chat**: `docs/CHAT.md`
