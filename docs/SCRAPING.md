<!-- NG-HEADER: Nombre de archivo: SCRAPING.md -->
<!-- NG-HEADER: Ubicación: docs/SCRAPING.md -->
<!-- NG-HEADER: Descripción: Documentación de scraping de precios de mercado -->
<!-- NG-HEADER: Lineamientos: Ver AGENTS.md -->

# Scraping de Precios de Mercado

Esta documentación describe la funcionalidad de scraping para obtener precios desde fuentes externas en el módulo "Mercado".

## Tabla de Contenidos

- [Tipos de Scraping](#tipos-de-scraping)
- [Scraping Estático](#scraping-estático)
- [Scraping Dinámico](#scraping-dinámico)
- [Extractores por Dominio](#extractores-por-dominio)
- [Uso Básico](#uso-básico)
- [Integración con Worker](#integración-con-worker)
- [Tests](#tests)
- [Troubleshooting](#troubleshooting)

## Tipos de Scraping

El sistema soporta dos tipos de scraping según la naturaleza de la página:

### 1. Scraping Estático (`source_type='static'`)

Para páginas que renderizan el precio directamente en HTML sin JavaScript.

**Características:**
- Usa `requests` + `BeautifulSoup`
- Más rápido y ligero
- Funciona sin navegador
- Ideal para sitios simples

**Sitios compatibles:**
- MercadoLibre Argentina
- Amazon Argentina
- Sitios genéricos con precios en HTML

### 2. Scraping Dinámico (`source_type='dynamic'`)

Para páginas que requieren JavaScript para mostrar precios.

**Características:**
- Usa `Playwright` en modo headless
- Más lento pero más completo
- Requiere navegador Chromium
- Para SPAs y sitios complejos

**Sitios compatibles:**
- Sitios React/Vue/Angular
- Páginas con lazy loading de precios
- Sitios que detectan requests/BeautifulSoup

## Scraping Estático

### Arquitectura

```
workers/scraping/
├── __init__.py              # Exporta scrape_static_price
└── static_scraper.py        # Implementación principal

Flujo:
1. scrape_static_price(url) → Detecta dominio
2. Intenta extractor específico (MercadoLibre, Amazon)
3. Fallback a extractor genérico
4. Normaliza precio a Decimal
```

### Función Principal

```python
from workers.scraping import scrape_static_price
from workers.scraping.static_scraper import NetworkError, PriceNotFoundError

try:
    price = scrape_static_price("https://www.mercadolibre.com.ar/producto", timeout=15)
    print(f"Precio: ${price}")
    
except NetworkError as e:
    print(f"Error de red: {e}")
    
except PriceNotFoundError as e:
    print(f"Precio no encontrado: {e}")
```

**Parámetros:**
- `url` (str): URL completa del producto
- `timeout` (int): Timeout en segundos (default: 10)

**Returns:**
- `Decimal`: Precio extraído
- Lanza `NetworkError` si hay error de red/timeout
- Lanza `PriceNotFoundError` si no encuentra precio

## Extractores por Dominio

### MercadoLibre Argentina

**Selectores:**
```python
# Contenedor principal
div.ui-pdp-price__main-container

# Parte entera
span.andes-money-amount__fraction

# Centavos (opcional)
span.andes-money-amount__cents
```

**Ejemplo HTML:**
```html
<div class="ui-pdp-price__main-container">
    <span class="andes-money-amount__fraction">1250</span>
    <span class="andes-money-amount__cents">50</span>
</div>
```

**Resultado:** `Decimal('1250.50')`

## Scraping Dinámico

### Arquitectura

```
workers/scraping/
├── __init__.py              # Exporta scrape_dynamic_price, scrape_dynamic_price_sync
└── dynamic_scraper.py       # Implementación con Playwright

Flujo:
1. scrape_dynamic_price(url) → Lanza navegador headless (Chromium)
2. Navega a URL y espera networkidle (AJAX completo)
3. Extrae precio con selector proporcionado o detecta automáticamente
4. Cierra navegador (garantizado con finally block)
5. Normaliza precio a Decimal
```

### Instalación

```bash
# 1. Instalar Playwright (ya en requirements.txt)
pip install playwright

# 2. Descargar navegador Chromium (~170MB)
playwright install chromium
```

**Verificar instalación:**
```bash
playwright --version
# playwright 1.42.0
```

### Función Principal

```python
from workers.scraping import scrape_dynamic_price_sync
from workers.scraping.dynamic_scraper import (
    BrowserLaunchError,
    PageLoadError,
    SelectorNotFoundError,
    DynamicScrapingError,
)

try:
    # Versión sincrónica (recomendada para workers)
    price = scrape_dynamic_price_sync(
        "https://www.spa-shop.com/producto",
        selector="span.precio-final",  # Opcional
        timeout=15000,  # 15 segundos
        wait_for_selector_timeout=8000,  # 8 segundos
    )
    print(f"Precio: ${price}")
    
except BrowserLaunchError as e:
    print(f"Error lanzando navegador: {e}")
    
except PageLoadError as e:
    print(f"Timeout al cargar página: {e}")
    
except SelectorNotFoundError as e:
    print(f"Selector no apareció en DOM: {e}")
    
except DynamicScrapingError as e:
    print(f"Error general: {e}")
```

**Versión async (para código nativo async):**
```python
from workers.scraping import scrape_dynamic_price

async def my_scraper():
    price = await scrape_dynamic_price(
        "https://www.example.com/product",
        selector=".price-tag",
        timeout=15000,
    )
    return price
```

### Parámetros

| Parámetro | Tipo | Default | Descripción |
|-----------|------|---------|-------------|
| `url` | `str` | Requerido | URL completa del producto |
| `selector` | `Optional[str]` | `None` | Selector CSS del precio (ej: `".price-value"`) |
| `timeout` | `int` | `15000` | Timeout para cargar página (ms) |
| `wait_for_selector_timeout` | `int` | `8000` | Timeout para esperar selector (ms) |

**Returns:**
- `Decimal`: Precio extraído y normalizado
- `None`: Si no encuentra precio
- Lanza excepciones específicas en caso de error

### Excepciones Específicas

```python
# Error al lanzar navegador (falta instalación, permisos, etc.)
BrowserLaunchError: "No se pudo lanzar navegador: ..."

# Timeout al cargar página o esperar networkidle
PageLoadError: "Timeout cargando https://... : TimeoutError..."

# Selector no apareció en tiempo límite
SelectorNotFoundError: "Selector '.price' no encontrado: TimeoutError..."

# Error general/inesperado
DynamicScrapingError: "Error inesperado en scraping: ..."
```

### Estrategias de Extracción

#### 1. Con Selector Específico (Recomendado)

Más confiable cuando conoces el selector del precio:

```python
# Inspeccionar en DevTools:
# Clic derecho en precio → Inspeccionar → Copy selector

price = scrape_dynamic_price_sync(
    "https://www.growshop.com/producto",
    selector="span[data-testid='product-price']",  # Selector específico
    timeout=15000,
)
```

**Ventajas:**
- Más rápido (espera directa al elemento)
- Más confiable (no ambigüedad)
- Timeout específico (8s por defecto)

#### 2. Detección Automática

Sin selector, busca en selectores comunes:

```python
price = scrape_dynamic_price_sync(
    "https://www.growshop.com/producto"  # Sin selector
)
```

**Selectores probados automáticamente:**
```python
[
    "[class*='price']",         # Cualquier clase con "price"
    "[id*='price']",            # Cualquier id con "price"
    "[itemprop='price']",       # Schema.org markup
    "[data-testid*='price']",   # Testing IDs comunes
    ".product-price",           # Clase específica común
    "#product-price",           # ID específico común
    ".price-tag",
    ".precio",                  # Variante español
    "[class*='precio']",
    # ... más selectores
]
```

**Fallback final:** Regex en contenido HTML completo
```python
\$\s?([\d.,]+)    # Busca $ seguido de números
```

### Configuración del Navegador

```python
# Configuración headless optimizada (interno)
browser = await p.chromium.launch(
    headless=True,
    args=[
        '--no-sandbox',              # Docker/CI compatibility
        '--disable-setuid-sandbox',
        '--disable-dev-shm-usage',   # Evita OOM en contenedores
        '--disable-gpu',             # No necesario en headless
    ]
)

# Context con user-agent realista
context = await browser.new_context(
    viewport={'width': 1280, 'height': 720},
    user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    locale='es-AR',
)
```

### Esperas Apropiadas

```python
# 1. Navegar con espera básica
await page.goto(url, wait_until='domcontentloaded', timeout=15000)

# 2. Esperar que todas las requests AJAX terminen
await page.wait_for_load_state('networkidle', timeout=15000)
# networkidle = no más de 2 conexiones activas por 500ms

# 3. Si hay selector, esperar que aparezca
if selector:
    await page.wait_for_selector(selector, timeout=8000)
```

### Cierre Garantizado de Recursos

El navegador **siempre** se cierra, incluso con errores:

```python
browser: Optional[Browser] = None

try:
    async with async_playwright() as p:
        browser = await p.chromium.launch(...)
        # ... scraping ...
        
        await browser.close()
        browser = None  # Marcar como cerrado
        
except Exception as e:
    raise DynamicScrapingError(f"Error: {e}")
    
finally:
    # Red de seguridad: cierre garantizado
    if browser and browser.is_connected():
        await browser.close()
```

**Importante:** No deja procesos colgados de Chromium.

### Ejemplos de Uso

#### Ejemplo 1: Sitio React con Selector Conocido

```python
from workers.scraping import scrape_dynamic_price_sync

# Sitio SPA que carga precio con React
price = scrape_dynamic_price_sync(
    url="https://www.react-shop.com/producto/123",
    selector="div[data-price] span.amount",
    timeout=20000,  # 20s para sitios lentos
)

print(f"Precio React: ${price}")
# Precio React: $2450.00
```

#### Ejemplo 2: Sitio Desconocido sin Selector

```python
# Detecta automáticamente el precio
price = scrape_dynamic_price_sync(
    url="https://www.unknown-shop.com/product"
)

if price:
    print(f"Precio detectado: ${price}")
else:
    print("No se encontró precio")
```

#### Ejemplo 3: Manejo Completo de Errores

```python
from workers.scraping.dynamic_scraper import (
    scrape_dynamic_price_sync,
    BrowserLaunchError,
    PageLoadError,
    SelectorNotFoundError,
)

def safe_scrape_dynamic(url: str, selector: str = None):
    try:
        return scrape_dynamic_price_sync(url, selector=selector)
        
    except BrowserLaunchError:
        # Navegador no instalado o error de permisos
        print("ERROR: Ejecutar 'playwright install chromium'")
        return None
        
    except PageLoadError:
        # Timeout cargando página (sitio caído, muy lento)
        print("ERROR: Página no cargó en tiempo límite")
        return None
        
    except SelectorNotFoundError:
        # Selector no apareció (probablemente incorrecto)
        print("ERROR: Selector no encontrado, probar sin selector")
        # Retry sin selector
        return scrape_dynamic_price_sync(url)
        
    except Exception as e:
        print(f"ERROR: {e}")
        return None

price = safe_scrape_dynamic(
    "https://www.spa-shop.com/producto",
    selector=".product-price"
)
```

### Performance

| Operación | Tiempo Típico |
|-----------|---------------|
| Lanzar navegador | 1-2 segundos |
| Cargar página simple | 2-4 segundos |
| Cargar página con AJAX | 5-10 segundos |
| Extracción con selector | <1 segundo |
| Extracción genérica | 1-3 segundos |
| **Total típico** | **8-15 segundos** |

**Comparación con scraping estático:**
- Estático: 1-3 segundos
- Dinámico: 8-15 segundos (3-5x más lento)

**Recomendación:** Usar `source_type='static'` siempre que sea posible. Solo usar `'dynamic'` cuando sea estrictamente necesario (JavaScript requerido).

### Amazon Argentina

**Selectores:**
```python
# Precio principal
span.a-price[data-a-size='xl']

# Parte entera
span.a-price-whole

# Centavos
span.a-price-fraction

# Fallback (páginas antiguas)
span#priceblock_ourprice
```

**Ejemplo HTML:**
```html
<span class="a-price" data-a-size="xl">
    <span class="a-price-whole">2499</span>
    <span class="a-price-fraction">99</span>
</span>
```

**Resultado:** `Decimal('2499.99')`

### Extractor Genérico

Busca precios en elementos comunes cuando no hay extractor específico:

**Selectores buscados:**
```python
[class*='price']       # Cualquier clase con "price"
[id*='price']          # Cualquier id con "price"
[class*='precio']      # Variante en español
[itemprop='price']     # Schema.org markup
```

**Patrones regex:**
```python
\$\s?([\d.,]+)                    # $ 1.250,00
(?:ARS|AR\$)\s?([\d.,]+)          # ARS 1250
(?:precio|price):\s?\$?\s?([\d.,]+)  # Precio: 1250.50
```

## Uso Básico

### Script de Prueba Manual

```bash
python scripts/test_scraping_manual.py <URL>
```

**Ejemplo:**
```bash
python scripts/test_scraping_manual.py "https://www.mercadolibre.com.ar/producto-ejemplo"

============================================================
Scraping de: https://www.mercadolibre.com.ar/producto-ejemplo
============================================================

✅ ÉXITO: Precio encontrado
   Precio: $1250.50
   Formato: Decimal

============================================================
```

### Uso Programático

```python
from workers.scraping import scrape_static_price
from decimal import Decimal

# Ejemplo básico
price = scrape_static_price("https://www.example.com/product")

# Con timeout personalizado
price = scrape_static_price("https://www.slow-site.com/product", timeout=30)

# Validar tipo
assert isinstance(price, Decimal)
```

## Integración con Worker

El worker `refresh_market_prices_task` usa automáticamente el scraper apropiado:

```python
# En workers/market_scraping.py

async def scrape_market_source(source: MarketSource):
    """
    Detecta source_type y aplica scraper correspondiente.
    """
    if source.source_type == "static":
        # Usa scrape_static_price (requests + BeautifulSoup)
        price = scrape_static_price(source.url, timeout=15)
        return price, None
        
    elif source.source_type == "dynamic":
        # Usa scrape_dynamic_price_sync (Playwright headless)
        from workers.scraping.dynamic_scraper import (
            scrape_dynamic_price_sync,
            BrowserLaunchError,
            PageLoadError,
            SelectorNotFoundError,
        )
        
        try:
            price = scrape_dynamic_price_sync(source.url, timeout=15000)
            return price, None
        except (BrowserLaunchError, PageLoadError, SelectorNotFoundError) as e:
            return None, str(e)
```

### Flujo Completo

```
1. Usuario crea MarketSource con source_type='static'
2. Sistema encola refresh_market_prices_task(product_id)
3. Worker obtiene todas las fuentes del producto
4. Para cada fuente:
   a. Llama scrape_market_source()
   b. scrape_market_source() detecta type='static'
   c. Ejecuta scrape_static_price(source.url)
   d. Actualiza source.last_price
   e. Actualiza source.last_checked_at
5. Calcula promedio → product.market_price_reference
6. Actualiza product.market_price_updated_at
```

## Tests

### Estructura de Tests

```
tests/
├── test_static_scraper.py       # Tests scraping estático (25 tests)
├── test_dynamic_scraper.py      # Tests scraping dinámico (16 tests)
└── html_fixtures/               # HTML de ejemplo
    ├── mercadolibre_example.html
    ├── amazon_example.html
    └── generic_example.html
```

### Tests de Scraping Estático

```bash
# Todos los tests estáticos
pytest tests/test_static_scraper.py -v

# Solo normalización
pytest tests/test_static_scraper.py::TestNormalizePrice -v

# Solo extractores
pytest tests/test_static_scraper.py::TestExtractPrice -v
```

**Tests incluidos (25 tests):**
- Normalización de precios (8 tests)
- Extractores por dominio (9 tests)
- Scraping completo con mocks (7 tests)
- Tests de integración (1 test, marcado)

### Tests de Scraping Dinámico

```bash
# Todos los tests dinámicos (sin integración)
pytest tests/test_dynamic_scraper.py -v -k "not integration"

# Solo normalización
pytest tests/test_dynamic_scraper.py::TestNormalizePriceDynamic -v

# Solo extracción
pytest tests/test_dynamic_scraper.py::TestExtractPriceFromPage -v

# Solo scraping completo
pytest tests/test_dynamic_scraper.py::TestScrapeDynamicPrice -v
```

**Tests incluidos (16 tests):**
- Normalización de precios (5 tests)
- Extracción de página con mocks (3 tests)
- Scraping completo con mocks de Playwright (6 tests)
- Wrapper sincrónico (2 tests)
- Tests de integración (1 test, marcado)

**Mocking de Playwright:**
```python
# Los tests usan AsyncMock para simular Playwright
mock_browser = AsyncMock()
mock_page = AsyncMock()
mock_element = AsyncMock()

# Simular precio en elemento
mock_element.inner_text.return_value = "$ 1.250,50"
mock_page.query_selector.return_value = mock_element

# Ejecutar scraping (sin navegador real)
price = await scrape_dynamic_price(url, selector=".price")
assert price == Decimal("1250.50")
```

**Nota:** Los tests con AsyncMock generan warnings sobre coroutines no esperadas. Es comportamiento normal y no afecta funcionalidad.

## Troubleshooting

### Scraping Estático

#### Error: "Precio no encontrado"

**Causas comunes:**
1. Sitio requiere JavaScript (usar `source_type='dynamic'`)
2. Selectores cambiaron (actualizar extractor)
3. URL apunta a página sin precio

**Solución:**
```python
# 1. Verificar HTML manualmente
import requests
response = requests.get(url)
print(response.text)  # Buscar precio en HTML crudo

# 2. Inspeccionar en navegador
# Abrir DevTools → Elements → Buscar precio
# Ver si está en HTML inicial o se carga con JS

# 3. Cambiar a dinámico si es necesario
source.source_type = "dynamic"  # Usar Playwright
```

#### Error: "Timeout al acceder"

**Causas:**
- Red lenta
- Sitio bloqueando User-Agent
- Firewall/proxy

**Solución:**
```python
# Aumentar timeout
price = scrape_static_price(url, timeout=30)

# Verificar User-Agent (en static_scraper.py)
headers = {
    "User-Agent": "GrowenBot/1.0 (+https://growen.app)",
    # ...
}
```

#### Selectores Cambiaron

**MercadoLibre cambió estructura:**

```python
# Actualizar en static_scraper.py:extract_price_mercadolibre()

# Antes:
price_container = soup.select_one("div.ui-pdp-price__main-container")

# Después (si cambia):
price_container = soup.select_one("div.nueva-clase-precio")
```

### Scraping Dinámico

#### Error: "Browser not installed"

**Causa:** Playwright browsers no descargados

**Solución:**
```bash
# Descargar navegador Chromium
playwright install chromium

# Verificar instalación
playwright --version
```

#### Error: BrowserLaunchError

**Causas comunes:**
- Chromium no instalado (ver arriba)
- Permisos insuficientes en Linux/Docker
- Falta dependencias del sistema

**Solución Linux/Docker:**
```bash
# Instalar dependencias de Chromium
apt-get update && apt-get install -y \
    libnss3 \
    libnspr4 \
    libatk1.0-0 \
    libatk-bridge2.0-0 \
    libcups2 \
    libdrm2 \
    libdbus-1-3 \
    libxkbcommon0 \
    libatspi2.0-0 \
    libxcomposite1 \
    libxdamage1 \
    libxfixes3 \
    libxrandr2 \
    libgbm1 \
    libasound2

# En Dockerfile, agregar antes de install chromium
```

#### Error: PageLoadError (Timeout)

**Causas:**
- Sitio muy lento
- Red lenta
- Muchos recursos AJAX

**Solución:**
```python
# Aumentar timeout a 30 segundos
price = scrape_dynamic_price_sync(url, timeout=30000)

# O deshabilitar espera networkidle (modificar código interno)
# await page.wait_for_load_state('load')  # En lugar de 'networkidle'
```

#### Error: SelectorNotFoundError

**Causas:**
- Selector incorrecto
- Precio se carga después del timeout
- Precio solo visible tras interacción (scroll, click)

**Solución:**
```python
# 1. Verificar selector en DevTools
# Abrir página en navegador normal
# Clic derecho en precio → Inspeccionar → Copy selector

# 2. Aumentar timeout de selector
price = scrape_dynamic_price_sync(
    url,
    selector=".price",
    wait_for_selector_timeout=15000,  # 15s en lugar de 8s
)

# 3. Probar sin selector (detección automática)
price = scrape_dynamic_price_sync(url)
```

#### Navegador se Queda Colgado

**Síntoma:** Procesos Chromium no se cierran

**Causa:** Error en cierre del navegador

**Verificar:**
```bash
# Linux/Mac
ps aux | grep chromium

# Windows PowerShell
Get-Process | Where-Object { $_.ProcessName -like "*chrom*" }
```

**Solución:**
```bash
# Matar procesos manualmente
pkill chromium  # Linux
taskkill /F /IM chrome.exe  # Windows

# El código ya tiene finally block que garantiza cierre
# Si persiste, revisar logs para excepción específica
```

#### Precio No Detectado (Devuelve None)

**Causas:**
- Precio en iframe (no accesible)
- Precio en Shadow DOM (no accesible)
- Formato de precio no reconocido

**Solución:**
```python
# 1. Verificar si precio está en iframe
# En navegador: Inspeccionar → Ver si <iframe> contiene precio
# Playwright requiere cambiar a frame explícitamente (no implementado)

# 2. Para Shadow DOM (raro):
# Requiere modificar código para atravesar shadowRoot

# 3. Agregar normalización para formato específico
# Modificar normalize_price_dynamic() en dynamic_scraper.py
```

#### Performance Lenta

**Síntoma:** Scraping dinámico toma >20 segundos

**Optimizaciones:**
```python
# 1. Reducir timeout si sitio es rápido
price = scrape_dynamic_price_sync(url, timeout=10000)  # 10s

# 2. Deshabilitar imágenes (modificar código interno):
context = await browser.new_context(
    viewport={'width': 1280, 'height': 720},
    # Bloquear imágenes y CSS
)
await context.route("**/*.{png,jpg,jpeg,gif,webp,css}", lambda route: route.abort())

# 3. Usar static scraping si es posible
# Verificar si realmente requiere JS
```

#### Error en Docker/CI

**Síntoma:** Funciona local, falla en Docker

**Causa:** Falta shared memory o dependencias

**Solución en docker-compose.yml:**
```yaml
services:
  api:
    # ...
    shm_size: '2gb'  # Chromium requiere shared memory
    cap_add:
      - SYS_ADMIN  # Solo si --no-sandbox no funciona
```

**O usar --disable-dev-shm-usage:**
```python
# Ya implementado en dynamic_scraper.py
args=['--disable-dev-shm-usage', ...]
```

## Próximos Pasos

### Mejoras Planificadas

1. **Cache de Precios**
   - No scrapear si `last_checked_at` < 1 hora
   - Rate limiting por dominio
   - Circuit breaker para fuentes problemáticas

2. **Más Extractores Específicos**
   - Coto Digital
   - Carrefour
   - Walmart
   - Otros marketplaces argentinos
   - Extractores dinámicos por dominio (Playwright)

3. **Optimizaciones de Performance**
   - Pool de navegadores Playwright (reutilizar instancias)
   - Cache de páginas scrapeadas
   - Scraping paralelo con límite de concurrencia

4. **Inteligencia**
   - Detectar cambios bruscos de precio (alertas)
   - Historial de precios (modelo ya implementado)
   - Análisis de tendencias
   - Predicción de mejores momentos de compra

5. **Robustez**
   - Retry con backoff exponencial
   - Rotación de User-Agents
   - Proxies para evitar bloqueos
   - Detección automática de CAPTCHAs

6. **Selectores Inteligentes**
   - Aprender selectores de éxitos previos
   - Sugerir selectores al crear MarketSource
   - Auto-corregir selectores rotos

## Referencias

- **Código estático:** `workers/scraping/static_scraper.py`
- **Código dinámico:** `workers/scraping/dynamic_scraper.py`
- **Tests estáticos:** `tests/test_static_scraper.py`
- **Tests dinámicos:** `tests/test_dynamic_scraper.py`
- **Fixtures:** `tests/html_fixtures/`
- **Worker:** `workers/market_scraping.py`
- **Script prueba estático:** `scripts/test_scraping_manual.py`

## Changelog

### 2025-01-XX - Scraping Dinámico con Playwright

**Nuevo:**
- `workers/scraping/dynamic_scraper.py` - Scraping con Playwright headless
- Función `scrape_dynamic_price()` async completa
- Wrapper `scrape_dynamic_price_sync()` para código sincrónico
- Extractor genérico con selectores comunes
- Excepciones específicas: BrowserLaunchError, PageLoadError, SelectorNotFoundError
- 16 tests con mocks de Playwright
- Integración con worker `market_scraping.py`
- Documentación completa en esta guía

**Características:**
- Navegador headless Chromium con args optimizados
- User-agent realista para evitar bloqueos
- Espera networkidle para AJAX completo
- Timeouts configurables (página: 15s, selector: 8s)
- Cierre garantizado de navegador (finally block)
- Estrategias multi-nivel de extracción
- Compatible con Docker/CI

### 2025-01-XX - Scraping Estático Inicial

**Implementación inicial:**
- `workers/scraping/static_scraper.py` - requests + BeautifulSoup
- Extractores específicos: MercadoLibre, Amazon
- Extractor genérico con regex
- 25 tests unitarios
- Integración con worker
- Script de prueba manual
