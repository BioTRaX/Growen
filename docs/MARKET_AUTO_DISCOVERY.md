<!-- NG-HEADER: Nombre de archivo: MARKET_AUTO_DISCOVERY.md -->
<!-- NG-HEADER: Ubicación: docs/MARKET_AUTO_DISCOVERY.md -->
<!-- NG-HEADER: Descripción: Descubrimiento automático de fuentes de precios con validación -->
<!-- NG-HEADER: Lineamientos: Ver AGENTS.md -->

# Descubrimiento Automático de Fuentes de Precio

Sistema para encontrar y validar automáticamente fuentes de precio de mercado usando MCP Web Search.

## Flujo Completo

### 1. Descubrimiento (Usuario → Sistema)

**UI**: Botón "Buscar fuentes automáticamente" en `MarketDetailModal`

```
Usuario hace clic → POST /market/products/{id}/discover-sources
                   ↓
         Sistema construye query: "{nombre} precio {categoría} comprar"
                   ↓
         Llama MCP Web Search (DuckDuckGo)
                   ↓
         Filtra resultados por:
           • Dominios confiables (MercadoLibre, growshops, etc.)
           • Indicadores de precio ($, "precio", "comprar")
           • Exclusión de recursos (imágenes, CSS, JS)
           • Deduplicación vs URLs existentes
                   ↓
         Retorna hasta 10 URLs sugeridas con snippet
```

### 2. Revisión (Usuario)

**UI**: Lista de URLs con checkboxes en `SuggestedSourcesSection`

- Usuario ve título, URL y snippet de cada sugerencia
- Checkboxes para seleccionar las relevantes
- Badges visuales: "MERCADOLIBRE", "ALTA CONFIANZA" para dominios conocidos
- Botón "Agregar seleccionadas (N)"

### 3. Validación Automática (Sistema)

**Backend**: Cada URL seleccionada se valida antes de agregar

```
Usuario selecciona URLs → POST /market/products/{id}/sources/batch-from-suggestions
                        ↓
          Para cada URL en paralelo (max 3 concurrentes):
                        ↓
          1. Verificar no duplicada
          2. Verificar disponibilidad (HEAD request, 5s timeout)
          3. Si dominio de alta confianza: ✅ aprobar directamente
          4. Si no: GET request + parsing HTML (10s timeout)
             • Buscar patrones de precio ($, "precio", meta tags)
          5. Si precio encontrado: ✅ crear MarketSource
          6. Si no: ❌ rechazar con razón
                        ↓
          Retornar resumen: N éxitos, M fallos
```

### 4. Resultado (Sistema → Usuario)

**UI**: Toast con resumen de resultados

- Éxito: "3 fuentes agregadas exitosamente"
- Parcial: "2 fuentes agregadas, 1 falló"
- Detalles de fallos: URL + razón (price_not_found, network_error, etc.)

## Arquitectura

### Módulos Backend

```
workers/discovery/
├── source_finder.py          # Descubrimiento vía MCP Web Search
│   ├── discover_price_sources()      # Función principal
│   ├── build_search_query()          # Construye query contextual
│   ├── call_mcp_web_search()         # Llama al MCP
│   ├── extract_valid_urls()          # Filtra resultados
│   └── is_valid_ecommerce_url()      # Valida dominios
│
└── source_validator.py       # Validación de precios
    ├── validate_source()             # Validación completa
    ├── check_url_availability()     # HEAD request
    ├── detect_price_in_html()        # GET + parsing
    └── validate_multiple_sources()   # Validación en paralelo
```

### Endpoints API

| Endpoint | Método | Descripción | Roles |
|----------|--------|-------------|-------|
| `/market/products/{id}/discover-sources` | POST | Descubre URLs candidatas | admin, colaborador |
| `/market/products/{id}/sources/from-suggestion` | POST | Agrega 1 fuente con validación | admin, colaborador |
| `/market/products/{id}/sources/batch-from-suggestions` | POST | Agrega N fuentes en paralelo | admin, colaborador |

### Componentes Frontend

```
frontend/src/components/
├── SuggestedSourcesSection.tsx    # Sección completa (descubrir + agregar)
│   ├── handleDiscover()           # Llama a discover-sources
│   ├── handleToggleSelection()    # Seleccionar/deseleccionar URL
│   └── handleAddSelected()        # Llama a batch-from-suggestions
│
└── MarketDetailModal.tsx          # Modal principal (incluye sección)
```

## Configuración

### Variables de Entorno

```bash
# URL del servicio MCP Web Search
MCP_WEB_SEARCH_URL=http://mcp_web_search:8002/invoke_tool
```

### Dominios de Alta Confianza

Definidos en `workers/discovery/source_validator.py`:

```python
HIGH_CONFIDENCE_DOMAINS = [
    "mercadolibre.com.ar",
    "mercadolibre.com",
    "santaplanta.com",
    "cultivargrowshop.com",
]
```

Estos dominios se agregan sin validación estricta de precio (se asume que siempre tienen precio si existen).

### Patrones de Precio

Definidos en `workers/discovery/source_validator.py`:

```python
PRICE_PATTERNS = [
    r'\$\s*\d{1,3}(?:[,\.]\d{3})*(?:[,\.]\d{2})?',  # $1234, $1,234
    r'precio\s*:?\s*\$?\s*\d{1,3}(?:[,\.]\d{3})*',  # Precio: 1234
    r'ARS\s*\$?\s*\d{1,3}(?:[,\.]\d{3})*',          # ARS 1234
    r'price["\']?\s*>?\s*\$?\s*\d{1,3}(?:[,\.]\d{3})*',  # class="price" ... >1234<
]
```

También se busca en meta tags schema.org: `<meta property="product:price:amount">`

## Uso

### 1. Desde la UI (Recomendado)

```
1. Abrir producto en Mercado → "Ver Detalles"
2. Scroll hasta "🔍 Buscar fuentes automáticamente"
3. Clic en "Buscar ahora"
4. Esperar resultados (5-15 segundos)
5. Seleccionar URLs relevantes con checkboxes
6. Clic en "Agregar seleccionadas (N)"
7. Sistema valida y agrega automáticamente
```

### 2. Desde API (Manual)

**Descubrir fuentes**:
```bash
POST /market/products/123/discover-sources?max_results=20
Authorization: Bearer <token>

# Response
{
  "success": true,
  "query": "Sustrato de coco precio comprar",
  "total_results": 15,
  "valid_sources": 3,
  "sources": [
    {
      "url": "https://www.santaplanta.com/sustrato-coco",
      "title": "Sustrato Coco 20L",
      "snippet": "Precio $2500 con envío"
    }
  ]
}
```

**Agregar múltiples fuentes con validación**:
```bash
POST /market/products/123/sources/batch-from-suggestions
Authorization: Bearer <token>
Content-Type: application/json

{
  "sources": [
    {"url": "https://www.santaplanta.com/sustrato-coco", "validate_price": true},
    {"url": "https://articulo.mercadolibre.com.ar/...", "validate_price": true}
  ],
  "stop_on_error": false
}

# Response
{
  "total_requested": 2,
  "successful": 2,
  "failed": 0,
  "results": [
    {
      "url": "https://www.santaplanta.com/sustrato-coco",
      "success": true,
      "source_id": 42,
      "message": "Fuente 'Santaplanta.com' agregada exitosamente",
      "validation_result": {
        "is_valid": true,
        "reason": "high_confidence"
      }
    }
  ]
}
```

## Tests

### Tests Unitarios

```bash
# Validador de fuentes (27 tests)
pytest tests/test_source_validator.py -v

# Descubridor de fuentes (25 tests pasando)
pytest tests/test_source_finder.py -v
```

### Cobertura

- ✅ Construcción de query contextual
- ✅ Validación de dominios de e-commerce
- ✅ Detección de indicadores de precio
- ✅ Exclusión de recursos (imágenes, CSS, JS)
- ✅ Deduplicación de URLs
- ✅ Detección de precio en HTML (con mocks)
- ✅ Validación completa de fuentes
- ✅ Manejo de errores de red

### Mocking

Tests usan `respx` para mockear requests HTTP sin hacer llamadas reales:

```python
@pytest.mark.asyncio
async def test_detect_price_with_dollar_sign(respx_mock):
    url = "https://example.com/producto"
    html = "<html><body><span>Precio: $1250</span></body></html>"
    
    respx_mock.get(url).mock(return_value=httpx.Response(200, text=html))
    
    result = await detect_price_in_html(url)
    assert result is True
```

## Limitaciones y Futuras Mejoras

### Limitaciones Actuales

1. **Solo HTML estático**: No ejecuta JavaScript (para páginas dinámicas, usar `source_type="dynamic"` y scrapear con Playwright)
2. **Timeouts fijos**: HEAD 5s, GET 10s (no configurables por fuente)
3. **Sin retry**: Si falla por timeout, no reintenta (considerar backoff exponencial)
4. **Cache ausente**: Re-valida URLs repetidas (considerar cache con TTL de 30 min)

### Roadmap

**Corto plazo**:
- [ ] Cache de validaciones con TTL de 30 minutos
- [ ] Rate limiting por usuario/IP (max 10 descubrimientos por hora)
- [ ] Scoring de confiabilidad por dominio (0-100)
- [ ] Pre-validación de disponibilidad (HEAD) antes de agregar a UI

**Mediano plazo**:
- [ ] Detección automática de `source_type` (static vs dynamic)
- [ ] Heurísticas de calidad de precio (si está en oferta, descuento, etc.)
- [ ] Historial de validaciones (para debugging y mejora de patrones)
- [ ] Sugerencias proactivas (notificar si aparecen nuevas fuentes)

**Largo plazo**:
- [ ] Machine Learning para scoring de URLs (modelo entrenado con éxitos/fallos históricos)
- [ ] Integración con más buscadores (Google Shopping, Bing, API específicas)
- [ ] Auto-agregar fuentes de muy alta confianza (MercadoLibre oficial, etc.)
- [ ] Monitoreo de cambios en fuentes (alertar si una fuente deja de tener precio)

## Troubleshooting

### "No se encontraron fuentes válidas"

**Causas**:
- Query demasiado específica (incluye SKU interno o marca poco común)
- Producto muy nicho (no hay tiendas online que lo vendan)
- Filtros muy estrictos (solo dominios de alta confianza + indicadores de precio)

**Soluciones**:
1. Usar query más genérica (remover SKU, usar solo nombre + categoría)
2. Agregar manualmente URLs conocidas con `validate_price=false`
3. Ampliar lista de dominios conocidos en `KNOWN_ECOMMERCE_DOMAINS`

### "Precio no detectado en la URL"

**Causas**:
- Página requiere JavaScript para renderizar precio (React, Vue, etc.)
- Precio está en imagen o iframe
- Selectors CSS/patrones no coinciden

**Soluciones**:
1. Usar `source_type="dynamic"` y scrapear con Playwright
2. Agregar con `validate_price=false` (usar con precaución)
3. Ampliar `PRICE_PATTERNS` en `source_validator.py`

### "Timeout al validar fuente"

**Causas**:
- Sitio web lento o con protección anti-bot
- Red inestable
- Timeout muy corto (10s)

**Soluciones**:
1. Reintentar validación después de unos minutos
2. Aumentar timeout en código (requiere cambio en `source_validator.py`)
3. Usar `validate_price=false` y validar manualmente

## Referencias

**Documentos relacionados**:
- `docs/API_MARKET.md` - Endpoints completos con ejemplos
- `docs/MCP.md` - Arquitectura de MCP Servers
- `workers/discovery/source_finder.py` - Código fuente descubridor
- `workers/discovery/source_validator.py` - Código fuente validador

**Tests**:
- `tests/test_source_finder.py` - Tests de descubrimiento
- `tests/test_source_validator.py` - Tests de validación

---

**Última actualización**: 2025-11-12  
**Estado**: ✅ Implementado y documentado  
**Versión**: 1.0.0
