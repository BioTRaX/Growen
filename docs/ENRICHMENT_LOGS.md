<!-- NG-HEADER: Nombre de archivo: ENRICHMENT_LOGS.md -->
<!-- NG-HEADER: Ubicación: docs/ENRICHMENT_LOGS.md -->
<!-- NG-HEADER: Descripción: Documentación sobre logging y diagnóstico de enriquecimiento IA. -->
<!-- NG-HEADER: Lineamientos: Ver AGENTS.md -->

# Logging y Diagnóstico de Enriquecimiento IA

## Resumen

El enriquecimiento IA **SIEMPRE requiere búsqueda web obligatoria**. Si el enriquecimiento falla o no genera la descripción y fuentes esperadas, existen **tres fuentes principales de información** para diagnosticar el problema:

1. **Logs en archivo** (`logs/backend.log`)
2. **Tabla `audit_log`** en la base de datos
3. **Endpoint de debug** (`GET /debug/enrich/{product_id}`)

## Comportamiento del Enriquecedor

### Búsqueda Web Obligatoria

El enriquecedor **SIEMPRE** debe realizar búsqueda en internet. No es opcional. Requisitos:

1. **Variable de entorno**: `AI_USE_WEB_SEARCH=1`
2. **Servicio MCP Web Search**: Debe estar corriendo y saludable
3. **Permiso externo**: `AI_ALLOW_EXTERNAL=true`

Si alguna condición falla, el enriquecimiento retorna **error 500/502**.

### Jerarquía de Fuentes (Regla de Oro)

Prioridad estricta de veracidad:

1. **Prioridad #1**: Sitio oficial del fabricante
2. **Prioridad #2**: Marketplaces importantes (Mercado Libre)
3. **Prioridad #3**: Grow shops y vendedores online

**Conflictos**: Siempre usar la fuente de mayor prioridad.

### Contenido Generado

1. **Descripción** (máx 500 palabras, voseo argentino)
   - Estructura de 3 partes: beneficios, modo de uso, cierre con keywords
   - Keywords integradas al final (5 palabras separadas por comas, sin prefijos)
2. **Datos técnicos** (Peso, Alto, Ancho, Profundidad - null si no disponible)
3. **Precio de mercado AR$** (últimos 4 meses, advertencia si desactualizado)
4. **Fuentes** (OBLIGATORIO - archivo `.txt` en `/media/enrichment_logs/`)

### Correcciones de Encoding

**Problema**: OpenAI a veces devuelve respuestas con encoding UTF-8 corrupto (`├®` en vez de `é`, `├¡` en vez de `í`).

**Solución implementada**:
- Detección automática de caracteres corruptos: `├`, `┬`, `®`, `¡`, `▒`, etc.
- Conversión latin-1 → UTF-8 en dos etapas:
  1. **Pre-parse**: Antes de convertir JSON
  2. **Post-parse**: En la descripción extraída antes de guardar en BD
- Logging detallado cuando se aplica la corrección

### Cambios Recientes (2025-11-09)

#### ✅ Mejoras Implementadas

1. **Keywords SEO sin texto introductorio**
   - Antes: `...para vos. Keywords SEO integradas: fertilizante orgánico, guano...`
   - Ahora: `...para vos. fertilizante orgánico, guano murciélago, bokashi natural, cultivo indoor, abono vegetativo`
   - Eliminado campo duplicado "Keywords SEO" del schema JSON

2. **Encoding UTF-8 corregido automáticamente**
   - Detecta caracteres corruptos en respuesta de OpenAI
   - Aplica conversión latin-1 → UTF-8 automáticamente
   - Logs de debug para tracking: `enrich.encoding_fixed_pre_parse`, `enrich.encoding_fix_failed`

3. **Validación obligatoria de fuentes**
   - El campo "Fuentes" es OBLIGATORIO en la respuesta
   - Error 502 si falta: "Respuesta de IA inválida (falta campo 'Fuentes' obligatorio)"

4. **Estructura mejorada de descripción**
   - Prompt refactorizado con instrucciones de 3 pasos obligatorios
   - Ejemplo explícito de cómo terminar con keywords

#### ⚠️ Problemas Conocidos

1. **Valor de mercado casi siempre desactualizado**
   - **Causa**: DuckDuckGo HTML no devuelve fecha de publicación
   - OpenAI no puede filtrar por antigüedad (requisito: últimos 4 meses)
   - Ver `Roadmap.md` > "Mejoras de Enriquecimiento IA" para soluciones propuestas

2. **Datos técnicos opcionales raramente completados**
   - Grow shops no publican especificaciones en snippets cortos
   - Ver `Roadmap.md` para estrategias de mejora (búsqueda dirigida, scraping)

3. **Bulk enrich con timeout en lotes grandes**
   - `POST /products/enrich-multiple` ejecuta secuencialmente (bloquea worker)
   - Timeout típico: 20 productos × 12s = 4 minutos > nginx timeout (60s)
   - Ver `Roadmap.md` > "Bulk Enrich Asíncrono" para soluciones propuestas

---

## 1. Logs en Archivo (`logs/backend.log`)

### Ubicación
- Desarrollo local: `<proyecto>/logs/backend.log`
- Docker: dentro del contenedor `api` en `/app/logs/backend.log` (puede montarse como volumen)

### Configuración
- Nivel de log: variable `LOG_LEVEL` (por defecto `INFO`)
- Formato: `%(asctime)s | %(levelname)s | %(name)s | %(message)s`
- Rotación: 10 MB por archivo, hasta 5 backups

### Eventos de Enriquecimiento

El flujo de enriquecimiento emite logs estructurados en formato JSON (cuando se usa `logger.info/warning/error` con diccionarios):

#### 1. Selección de título
```python
logger.info({
    "event": "enrich.choose_title",
    "product_id": 123,
    "title_selected": "Nombre del producto",
    "used_canonical_title": true,
    "canonical_product_id_found": 456,
    "fallback_to_product_title": false
})
```

**Cuándo aparece:** Al inicio del enriquecimiento, después de resolver si existe un producto canónico y cuál título usar.

**Qué verificar:**
- Si `used_canonical_title` es `false`, significa que no se encontró canónico o su nombre estaba vacío.
- `title_selected` debe contener el título que se enviará a la IA.

#### 2. Error al buscar canónico
```python
logger.warning({
    "event": "enrich.choose_title.error",
    "product_id": 123,
    "reason": "Error al buscar producto canónico",
    "error": "<excepción>"
})
```

**Cuándo aparece:** Si falla la consulta a `ProductEquivalence` o `CanonicalProduct`.

#### 3. Inicio de web-search (si habilitado)
```python
logger.info({
    "event": "enrich.web_search.start",
    "product_id": 123
})
```

**Cuándo aparece:** Si `AI_USE_WEB_SEARCH=1` y `ai_allow_external=true`.

#### 4. Health check de web-search
```python
logger.info({
    "event": "enrich.web_search.health_check_result",
    "product_id": 123,
    "status": "ok"  # o "bad_status_XXX", "unhealthy"
})
```

**Qué verificar:**
- `status: "ok"` → servicio MCP web-search saludable
- `status: "unhealthy"` → servicio no responde o error de conexión
- `status: "bad_status_XXX"` → respondió pero con código HTTP != 200

#### 5. Éxito de web-search
```python
logger.info({
    "event": "enrich.web_search.success",
    "product_id": 123,
    "query": "Nombre del producto",
    "hits": 3,
    "with_sources": true
})
```

**Cuándo aparece:** Cuando MCP web-search devolvió resultados.

**Qué verificar:**
- `hits > 0` indica que se encontraron resultados.
- `with_sources: true` significa que hay URLs en los items.

#### 6. Fallo de web-search
```python
logger.error({
    "event": "enrich.web_search.execution_failed",
    "product_id": 123,
    "query": "...",
    "error": "<excepción>",
    "message": "Web search tool failed. Proceeding without web context."
})
```

**Cuándo aparece:** Cuando el MCP tool lanza excepción (timeout, formato inesperado, etc.).

**Qué hacer:** El enriquecimiento continuará sin contexto web. Verificar logs del servicio `mcp_web_search`.

#### 7. Web-search omitido
```python
logger.warning({
    "event": "enrich.web_search.skipped",
    "product_id": 123,
    "reason": "Web search service is not healthy.",
    "health_status": "unhealthy"
})
```

**Cuándo aparece:** Si el healthcheck falló antes de intentar la búsqueda.

#### 8. JSON inválido de IA
```python
logger.warning({
    "event": "enrich.error",
    "product_id": 123,
    "reason": "invalid_json",
    "preview": "<primeros 200 caracteres de respuesta>"
})
```

**Cuándo aparece:** La IA devolvió texto que no se puede parsear como JSON.

**Qué verificar:**
- `preview` muestra el inicio de la respuesta. Puede tener fences de markdown (```json), texto en lenguaje natural, o errores de sintaxis JSON.
- Si aparece `openai:` o `ollama:` al principio, el router ya intentó limpiar pero falló.

**Posibles causas:**
- No hay clave de OpenAI (`OPENAI_API_KEY`) y Ollama no está corriendo → la IA devuelve un echo del prompt o error.
- La IA no respeta las instrucciones de formato.

#### 9. Falta descripción en respuesta
```python
logger.warning({
    "event": "enrich.error",
    "product_id": 123,
    "reason": "missing_description"
})
```

**Cuándo aparece:** El JSON parseó correctamente pero no contiene la clave `"Descripción para Nice Grow"` o está vacía.

#### 10. Enriquecimiento exitoso
```python
logger.info({
    "event": "enrich.done",
    "product_id": 123,
    "used_canonical_title": true,
    "sources": true,
    "source_file": "/media/enrichment_logs/product_123_enrichment_20250108T120000Z.txt",
    "web_search_hits": 3
})
```

**Cuándo aparece:** Al finalizar exitosamente, antes del commit final.

**Qué verificar:**
- `sources: true` → se generó archivo `.txt` con fuentes.
- `web_search_hits > 0` → se incluyó contexto web en el prompt.

---

## 2. Tabla `audit_log` en Base de Datos

### Esquema
```sql
CREATE TABLE audit_log (
    id SERIAL PRIMARY KEY,
    action VARCHAR(32),
    "table" VARCHAR(64),
    entity_id INTEGER,
    metadata JSONB,
    user_id INTEGER REFERENCES users(id),
    ip VARCHAR(64),
    created_at TIMESTAMP DEFAULT NOW()
);
```

### Acciones Relevantes

#### `enrich` o `reenrich`
Se registra **antes del commit final** en cada enriquecimiento.

**Metadatos importantes:**
```json
{
  "fields_generated": ["description_html", "weight_kg", ...],
  "desc_len_old": 0,
  "desc_len_new": 345,
  "num_sources": 2,
  "source_file": "/media/enrichment_logs/product_123_enrichment_20250108T120000Z.txt",
  "prompt_hash": "abc123...",
  "web_search_query": "Nombre del producto",
  "web_search_hits": 3,
  "used_canonical_title": true
}
```

**Qué verificar:**
- `fields_generated` lista los campos actualizados (debe incluir `description_html`).
- `num_sources > 0` → la IA devolvió fuentes.
- `web_search_hits > 0` → se usó contexto web.
- `used_canonical_title: true` → se usó el nombre canónico.
- `prompt_hash` permite correlacionar con logs si necesitas reconstruir el prompt exacto.

#### `bulk_enrich`
Para enriquecimientos masivos (`POST /products/enrich-multiple`):

```json
{
  "requested": 10,
  "enriched": 8,
  "skipped": 1,
  "errors": [123],
  "ids": [100, 101, ...]
}
```

**Qué verificar:**
- `errors` contiene IDs de productos que fallaron.
- `skipped` incluye productos sin título o ya enriquecidos (sin `force`).

### Consultas Útiles

#### Últimos 10 enriquecimientos
```sql
SELECT id, action, entity_id, metadata->>'fields_generated' AS fields, created_at
FROM audit_log
WHERE action IN ('enrich', 'reenrich')
ORDER BY created_at DESC
LIMIT 10;
```

#### Enriquecimientos sin fuentes (posible fallo)
```sql
SELECT id, entity_id, metadata
FROM audit_log
WHERE action IN ('enrich', 'reenrich')
  AND (metadata->>'num_sources')::int = 0
ORDER BY created_at DESC;
```

#### Productos que fallan recurrentemente
```sql
SELECT entity_id, COUNT(*) AS intentos
FROM audit_log
WHERE action = 'reenrich'
GROUP BY entity_id
HAVING COUNT(*) > 2
ORDER BY intentos DESC;
```

---

## 3. Endpoint de Debug: `GET /debug/enrich/{product_id}`

### Requisitos
- Rol: `admin`
- No modifica datos (solo diagnóstico)

### Respuesta Ejemplo
```json
{
  "product_id": 123,
  "title": "Fertilizante Orgánico 5L",
  "title_used": "Fertilizante Orgánico 5L",
  "used_canonical_title": true,
  "ai_allow_external": true,
  "ai_provider_selected": "OpenAIProvider",
  "web_search": {
    "enabled": true,
    "health": "ok",
    "query": "Fertilizante Orgánico 5L",
    "hits": 3
  },
  "prompt": "Eres GrowMaster...\n\nProducto: Fertilizante Orgánico 5L\n\n...",
  "raw_ai_preview": "{\"Título del Producto\": \"Fertilizante...\"}",
  "raw_ai_looks_json": true
}
```

### Campos Clave

| Campo | Descripción |
|-------|-------------|
| `title_used` | Título final enviado a la IA (después de resolver canónico) |
| `used_canonical_title` | `true` si usó el nombre del canónico |
| `ai_provider_selected` | Proveedor IA activo (OpenAI, Ollama, etc.) |
| `web_search.enabled` | Si `AI_USE_WEB_SEARCH=1` y `ai_allow_external=true` |
| `web_search.health` | Estado del servicio MCP web-search: `ok`, `unhealthy`, `disabled` |
| `web_search.hits` | Cantidad de resultados obtenidos (0 si no hay o falló) |
| `prompt` | Prompt completo enviado a la IA (incluyendo contexto MCP y web si aplican) |
| `raw_ai_preview` | Primeros 1200 caracteres de la respuesta cruda de IA |
| `raw_ai_looks_json` | `true` si la respuesta parece JSON válido después de limpiar fences |

### Cuándo Usar

1. **Antes de enriquecer:** Para confirmar que el flujo está configurado correctamente (provider, web-search, título correcto).
2. **Después de fallo:** Para ver qué devolvió la IA sin persistir cambios.
3. **Troubleshooting:** Si `raw_ai_looks_json: false`, revisar `raw_ai_preview` para identificar el formato incorrecto.

---

## Checklist de Diagnóstico

Cuando el enriquecimiento falla:

### 1. Verificar proveedor IA
- [ ] ¿Está configurado `OPENAI_API_KEY`?
- [ ] Si usas Ollama: ¿está corriendo y accesible en `OLLAMA_HOST`?
- [ ] Consultar `GET /debug/enrich/{id}` → `ai_provider_selected`

### 2. Verificar respuesta de IA
- [ ] Consultar `logs/backend.log` buscando eventos `enrich.error` con `reason: invalid_json` o `missing_description`
- [ ] Usar `GET /debug/enrich/{id}` → `raw_ai_preview` y `raw_ai_looks_json`
- [ ] Si `raw_ai_looks_json: false`, la IA no respeta el formato pedido

### 3. Verificar web-search (si habilitado)
- [ ] `AI_USE_WEB_SEARCH=1` en variables de entorno
- [ ] `ai_allow_external=true` en settings (ver `agent_core/config.py`)
- [ ] Servicio `mcp_web_search` corriendo y healthy: `GET http://mcp_web_search:8002/health`
- [ ] Logs: buscar `enrich.web_search.health_check_result` → `status: "ok"`
- [ ] Si `status: "unhealthy"`, revisar logs de `mcp_web_search` (`docker compose logs mcp_web_search`)

### 4. Verificar título canónico
- [ ] ¿El producto tiene equivalencia con un canónico?
- [ ] ¿El canónico tiene nombre (`canonical_products.name`)?
- [ ] Logs: buscar `enrich.choose_title` → `used_canonical_title: true/false`
- [ ] Debug: `GET /debug/enrich/{id}` → `title_used` debe ser el esperado

### 5. Revisar auditoría
- [ ] Consultar `audit_log` con `action = 'enrich'` y `entity_id = <product_id>`
- [ ] Verificar `metadata`:
  - `fields_generated` debe incluir `description_html`
  - `num_sources > 0` indica que se generó archivo de fuentes
  - `web_search_hits > 0` indica contexto web incluido

### 6. Verificar archivo de fuentes
- [ ] Si `num_sources > 0` pero no aparece en UI, buscar `enrichment_sources_url` en la tabla `products`
- [ ] Verificar que exista físicamente en `<MEDIA_ROOT>/enrichment_logs/product_<id>_enrichment_<timestamp>.txt`
- [ ] Permisos de lectura correctos

---

## Variables de Entorno Relevantes

| Variable | Valor por defecto | Descripción |
|----------|-------------------|-------------|
| `LOG_LEVEL` | `INFO` | Nivel de logging (`DEBUG`, `INFO`, `WARNING`, `ERROR`) |
| `LOG_DIR` | `logs/` | Directorio para `backend.log` |
| `AI_USE_WEB_SEARCH` | `0` | Activar búsqueda web en enriquecimiento (`1` para activar) |
| `MCP_WEB_SEARCH_URL` | `http://mcp_web_search:8002/invoke_tool` | URL del servicio MCP web-search |
| `AI_WEB_SEARCH_MAX_RESULTS` | `3` | Cantidad máxima de resultados web a incluir |
| `OPENAI_API_KEY` | (vacío) | API key de OpenAI (si no está, cae a Ollama) |
| `OLLAMA_HOST` | `http://localhost:11434` | Host de Ollama |
| `MEDIA_ROOT` | `Devs/Imagenes` | Directorio raíz para archivos media |

---

## Problemas Comunes

### Problema: Enriquecimiento retorna 502 "Respuesta de IA inválida"

**Causas:**
1. La IA no devolvió JSON válido (fences de markdown, texto natural, etc.)
2. Falta clave `"Descripción para Nice Grow"` en JSON

**Solución:**
- Verificar logs: buscar `enrich.error` con `reason: invalid_json` o `missing_description`
- Usar `GET /debug/enrich/{id}` para ver `raw_ai_preview`
- Si la IA devuelve texto no estructurado, revisar prompt o cambiar de proveedor

### Problema: No genera fuentes aunque la IA las devuelve

**Causas:**
1. La IA devolvió `"Fuentes": null` o formato incorrecto
2. Fallo al escribir archivo `.txt` (permisos, disco lleno)

**Solución:**
- Revisar `audit_log` → `num_sources` debe ser > 0
- Verificar logs: buscar excepciones en escritura de archivo
- Comprobar permisos en `<MEDIA_ROOT>/enrichment_logs/`

### Problema: Web-search no incluye resultados

**Causas:**
1. `AI_USE_WEB_SEARCH` no está activado
2. `ai_allow_external=false` en settings
3. Servicio `mcp_web_search` no está healthy
4. El MCP tool falló (timeout, formato inesperado)

**Solución:**
- Verificar flags y servicio con `GET /debug/enrich/{id}` → `web_search.health`
- Si `health: "unhealthy"`, revisar logs de `mcp_web_search`
- Buscar en logs eventos `enrich.web_search.*`

### Problema: Usa título interno en lugar de canónico

**Causas:**
1. No existe equivalencia en `product_equivalences`
2. El canónico asociado no tiene `name` definido
3. Fallo al consultar canónico (excepción SQL)

**Solución:**
- Verificar `GET /debug/enrich/{id}` → `used_canonical_title`
- Logs: buscar `enrich.choose_title` → debe mostrar `canonical_product_id_found`
- Si hay error, buscar `enrich.choose_title.error`

---

## Ejemplo Completo de Diagnóstico

### Escenario
Enriquecer producto ID 456. El resultado es 502 y no aparece descripción.

### Paso 1: Consultar debug endpoint
```bash
curl -H "Cookie: session_id=..." http://localhost:8000/debug/enrich/456
```

**Resultado:**
```json
{
  "ai_provider_selected": "OpenAIProvider",
  "raw_ai_looks_json": false,
  "raw_ai_preview": "Lo siento, no tengo información específica sobre..."
}
```

**Diagnóstico:** La IA devolvió texto natural en lugar de JSON.

### Paso 2: Revisar configuración
- ¿Hay `OPENAI_API_KEY`? → No configurada
- ¿Está Ollama corriendo? → No

**Conclusión:** Sin proveedor válido, el router devuelve el prompt como echo o un mensaje de error.

### Paso 3: Solución
1. Configurar `OPENAI_API_KEY` con una clave válida, **O**
2. Iniciar Ollama localmente con un modelo compatible (ej. `llama3.2`)
3. Reintentar enriquecimiento

### Paso 4: Verificar logs
Tras reintentar con proveedor configurado:
```
2025-01-08 14:23:10 | INFO | growen | {'event': 'enrich.choose_title', 'product_id': 456, 'used_canonical_title': True, ...}
2025-01-08 14:23:15 | INFO | growen | {'event': 'enrich.done', 'product_id': 456, 'sources': True, 'web_search_hits': 3}
```

**Resultado:** Enriquecimiento exitoso.

---

## Mejoras Futuras

- [ ] Dashboard de métricas de enriquecimiento (tasa de éxito, latencia, fuentes generadas)
- [ ] Alertas automáticas cuando tasa de error > 20% en 1 hora
- [ ] Endpoint admin para re-encolar enriquecimientos fallidos
- [ ] Integración con Notion: crear tarjetas para enriquecimientos con error recurrente
- [ ] Logs estructurados en formato JSON puro (actualmente mezcla texto y dicts)

---

## Referencias

- Código de enriquecimiento: `services/routers/catalog.py` (`enrich_product`, `debug_enrich_product`)
- Configuración de logging: `services/api.py` (setup de `logger`)
- Modelo AuditLog: `db/models.py` (`class AuditLog`)
- Documentación de API: `docs/API_PRODUCTS.md` (sección "POST /products/{id}/enrich" y "GET /debug/enrich/{id}")
