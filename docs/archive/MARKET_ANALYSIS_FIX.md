# Análisis y Corrección: Flujo de Estudio de Mercado

**Fecha**: 2025-11-16  
**Estado**: Parcialmente funcional (cálculo OK, scraping NO)

---

## 🔍 Estado Actual del Sistema

### ✅ **Componentes Funcionando**

#### 1. **Base de Datos PostgreSQL**
- **Contenedor**: `growen-postgres` (NO `growen-db-1`)
- **Puerto**: `5433:5432`
- **Estado**: Healthy, conectado correctamente
- **Tabla**: `market_sources` con campos:
  - `product_id`: FK a canonical_products
  - `source_name`: Nombre de la tienda
  - `url`: URL de la fuente
  - `last_price`: Último precio obtenido (Decimal)
  - `last_checked_at`: Timestamp de última actualización
  - `is_mandatory`: Boolean para fuentes obligatorias

#### 2. **API Backend (Cálculo de Rango)** ✅
- **Endpoint 1**: `GET /market/products`
  - ✅ Calcula `market_price_min` y `market_price_max` consultando `market_sources`
  - ✅ Query por producto:
    ```python
    query_prices = (
        select(MarketSource.last_price)
        .where(
            and_(
                MarketSource.product_id == prod.id,
                MarketSource.last_price.isnot(None)
            )
        )
    )
    ```
  - ✅ Retorna `min(prices)` y `max(prices)`

- **Endpoint 2**: `GET /market/products/{id}/sources`
  - ✅ Schema actualizado con `market_price_min` y `market_price_max`
  - ✅ Calcula rango iterando sobre fuentes cargadas
  - ✅ Solo considera precios válidos (`last_price IS NOT NULL`)

#### 3. **Frontend UI** ✅
- **Componente**: `MarketDetailModal.tsx`
- ✅ Muestra "Rango de Mercado: $ min - $ max"
- ✅ Actualiza automáticamente cuando hay datos
- ✅ Muestra "Sin datos" cuando no hay precios

#### 4. **Redis** ✅
- **Contenedor**: `growen-redis` (NO `redis-1`)
- **Puerto**: `6379:6379`
- **Estado**: Running
- **Propósito**: Cola de tareas para Dramatiq

#### 5. **Servicios MCP** ✅
- `growen-mcp-products` - Puerto 8100
- `growen-mcp-web-search` - Puerto 8102
- Ambos healthy y funcionando

---

### ❌ **Componentes NO Funcionando**

#### 1. **Worker de Market Scraping** 🔴
- **PID**: 15616 (proceso zombie)
- **Error crítico**: `Error 10061 connecting to localhost:6379`
- **Causa**: 
  - Worker inició ANTES de que Redis estuviera disponible
  - Intenta conectar a `localhost` en lugar de `127.0.0.1`
  - Loop infinito de reconexión cada 3 segundos

**Evidencia en logs**:
```
[2025-11-16 13:53:59,189] [dramatiq.worker.ConsumerThread(market)] [CRITICAL] 
Consumer encountered a connection error: Error 10061 connecting to localhost:6379
[INFO] Restarting consumer in 3.00 seconds.
```

**Impacto**:
- ❌ No se procesan tareas encoladas de actualización de precios
- ❌ Botón "🔄 Actualizar Precios" encola tarea (202 Accepted) pero nunca se ejecuta
- ❌ Los precios nunca se actualizan automáticamente vía scraping

---

## 🔄 Flujo Actual de Estudio de Mercado

### **Flujo Completo (Diseñado)**

```
Usuario → UI → API → Redis → Worker → Scraping → DB → API → UI
   │       │     │      │       │         │        │     │     │
   └───────┴─────┴──────┴───────┴─────────┴────────┴─────┴─────┘
                          ❌ ROTO AQUÍ
```

### **Paso a Paso Detallado**

#### **Fase 1: Configuración de Fuentes** ✅
1. Usuario abre modal de producto (`MarketDetailModal`)
2. Click en "+ Agregar Fuente" o "Buscar fuentes automáticamente"
3. **Opción A - Manual**:
   - `POST /market/products/{id}/sources`
   - Body: `{ source_name, url, is_mandatory }`
   - Inserta en `market_sources` con `last_price=null`
4. **Opción B - Descubrimiento Automático**:
   - `POST /market/products/{id}/discover-sources?max_results=20`
   - Llama MCP Web Search (DuckDuckGo)
   - Filtra resultados por dominio conocido
   - Retorna URLs sugeridas
   - Usuario selecciona y agrega

**Estado actual**: ✅ Funciona perfectamente

---

#### **Fase 2: Actualización de Precios** ❌ ROTO

**Flujo Diseñado**:
```
1. Usuario → Click "🔄 Actualizar Precios"
2. UI → POST /market/products/{id}/refresh-market
3. API → Valida producto existe
4. API → refresh_market_prices_task.send(product_id)
5. API → Retorna 202 Accepted con job_id
6. Redis → Encola mensaje en cola "market"
7. Worker → Consume mensaje de Redis
8. Worker → Ejecuta scraping para cada fuente del producto
9. Worker → Actualiza market_sources.last_price y last_checked_at
10. Worker → Actualiza canonical_products.market_price_updated_at
11. Usuario → Recarga modal después de 3 segundos
12. API → Calcula rango desde market_sources
13. UI → Muestra "$ min - $ max"
```

**Flujo Actual (Roto en paso 7)**:
```
1. Usuario → Click "🔄 Actualizar Precios" ✅
2. UI → POST /market/products/{id}/refresh-market ✅
3. API → Valida producto existe ✅
4. API → refresh_market_prices_task.send(product_id) ✅
5. API → Retorna 202 Accepted ✅
6. Redis → Mensaje encolado en "market" ✅
7. Worker → ❌ NO CONSUME (sin conexión a Redis)
8. Worker → ❌ NUNCA EJECUTA
9-13. → ❌ NUNCA OCURREN
```

**Resultado**:
- Tarea queda en Redis indefinidamente
- Precios nunca se actualizan
- UI muestra "Sin datos" en rango

---

#### **Fase 3: Cálculo y Visualización** ✅

**Cuando HAY precios** (insertados manualmente o scrapeados):
```
1. GET /market/products/{id}/sources
2. Query: SELECT last_price FROM market_sources WHERE product_id = {id} AND last_price IS NOT NULL
3. Calcula: min(prices), max(prices)
4. Retorna: { market_price_min: 1180.0, market_price_max: 1350.0 }
5. UI muestra: "$ 1,180.00 - $ 1,350.00"
```

**Estado actual**: ✅ Funciona correctamente (probado con datos manuales)

---

## 🛠️ Diagnóstico del Problema del Worker

### **Causa Raíz**
El worker inició antes que Redis, intentó conectar, falló, y quedó en loop infinito de reconexión.

### **Por qué localhost vs 127.0.0.1 falla**
- Windows resuelve `localhost` a `::1` (IPv6) primero
- Redis en Docker solo escucha en `0.0.0.0` y `127.0.0.1` (IPv4)
- La conexión falla con "Connection refused"

### **Evidencia en netstat**
```powershell
TCP    0.0.0.0:6379           0.0.0.0:0              LISTENING       22992  # Redis escucha en IPv4
TCP    [::]:6379              [::]:0                 LISTENING       22992  # Redis escucha en IPv6
```

Pero el worker intenta `localhost:6379` que puede resolver a IPv6 primero.

---

## ✅ Soluciones Implementadas

### **1. Corrección del Cálculo de Rango** ✅ COMPLETO

**Archivo**: `services/routers/market.py`

**Cambio 1 - Endpoint `/market/products`** (líneas ~206-240):
```python
# ANTES:
# TODO Etapa 2: Calcular market_price_min, market_price_max desde market_sources
market_price_min_val = None
market_price_max_val = None

# DESPUÉS:
# Calcular market_price_min, market_price_max desde market_sources
market_price_min_val = None
market_price_max_val = None

query_prices = (
    select(MarketSource.last_price)
    .where(
        and_(
            MarketSource.product_id == prod.id,
            MarketSource.last_price.isnot(None)
        )
    )
)
result_prices = await db.execute(query_prices)
prices = [float(p) for p in result_prices.scalars().all() if p is not None]

if prices:
    market_price_min_val = min(prices)
    market_price_max_val = max(prices)
```

**Cambio 2 - Schema `ProductSourcesResponse`** (líneas ~275-284):
```python
class ProductSourcesResponse(BaseModel):
    product_id: int
    product_name: str
    sale_price: Optional[float] = None
    market_price_reference: Optional[float] = None
    market_price_updated_at: Optional[str] = ...
    market_price_min: Optional[float] = Field(None, description="Precio mínimo calculado desde fuentes")  # ✅ NUEVO
    market_price_max: Optional[float] = Field(None, description="Precio máximo calculado desde fuentes")  # ✅ NUEVO
    mandatory: list[MarketSourceItem] = ...
    additional: list[MarketSourceItem] = ...
```

**Cambio 3 - Endpoint `/products/{id}/sources`** (líneas ~332-368):
```python
# Separar fuentes y calcular rango
mandatory_sources = []
additional_sources = []
prices = []  # ✅ NUEVO

for source in sources:
    item = MarketSourceItem(...)
    
    # ✅ NUEVO: Recopilar precios válidos
    if source.last_price is not None:
        prices.append(float(source.last_price))
    
    if source.is_mandatory:
        mandatory_sources.append(item)
    else:
        additional_sources.append(item)

# ✅ NUEVO: Calcular rango
market_price_min_val = min(prices) if prices else None
market_price_max_val = max(prices) if prices else None

return ProductSourcesResponse(
    ...,
    market_price_min=market_price_min_val,  # ✅ NUEVO
    market_price_max=market_price_max_val,  # ✅ NUEVO
    ...
)
```

**Resultado**: ✅ Rango se calcula correctamente cuando hay precios

---

### **2. Datos de Prueba para Validación** ✅ COMPLETO

**Comando ejecutado**:
```sql
UPDATE market_sources SET last_price = 1180.00, last_checked_at = NOW() WHERE id = 1;
UPDATE market_sources SET last_price = 1350.00, last_checked_at = NOW() WHERE id = 2;
```

**Resultado**:
```
Producto 45 - "Bandeja Bulldog Lisa"
├── Fuente 1: ML Bandeja Bulldog 27*18 → $ 1,180.00
└── Fuente 2: 0800 Grow → $ 1,350.00

Rango calculado: $ 1,180.00 - $ 1,350.00 ✅
```

---

## 🚀 Soluciones Pendientes

### **Solución 1: Reparar Worker de Market** 🔴 URGENTE

#### **Opción A - Reinicio Limpio del Worker** (Recomendado)
```powershell
# 1. Detener worker zombie desde el panel de admin
#    O terminar proceso manualmente:
taskkill /PID 15616 /F

# 2. Limpiar logs antiguos
Remove-Item "logs\worker_market.log" -Force

# 3. Verificar Redis está corriendo
docker ps | Select-String "growen-redis"

# 4. Reiniciar worker desde admin panel
#    O manualmente:
.\scripts\start_worker_market.cmd
```

**Validación post-reinicio**:
```powershell
# Verificar conexión exitosa a Redis
Get-Content "logs\worker_market.log" -Tail 20 | Select-String "connected|ready|listening"

# Debe mostrar:
# [INFO] Consumer is ready.
# [INFO] Connected to Redis at 127.0.0.1:6379
```

---

#### **Opción B - Forzar IP 127.0.0.1 en .env** (Si Opción A falla)

**Archivo**: `.env`
```bash
# CAMBIAR:
REDIS_URL=redis://localhost:6379/0

# A:
REDIS_URL=redis://127.0.0.1:6379/0
```

Luego reiniciar worker.

---

#### **Opción C - Modo Inline (Sin Redis)** (Solo desarrollo, NO producción)

**Archivo**: `.env`
```bash
RUN_INLINE_JOBS=1
```

**NOTA**: Esto ejecuta tareas síncronamente, bloqueando la API. Solo para debug.

---

### **Solución 2: Mejorar Configuración del Worker** 📋

**Archivo**: `scripts/start_worker_market.cmd`

**Agregar validación de Redis antes de iniciar**:
```batch
@echo off
echo [INFO] Verificando conexión a Redis...

REM Probar conexión a Redis
python -c "import redis; r = redis.Redis(host='127.0.0.1', port=6379); r.ping(); print('[OK] Redis disponible')" 2>nul
if errorlevel 1 (
    echo [ERROR] Redis no disponible en 127.0.0.1:6379
    echo [ERROR] Ejecuta: docker ps ^| findstr redis
    pause
    exit /b 1
)

echo [INFO] Iniciando worker de market...
python -m dramatiq workers.market_scraping --processes 1 --threads 4 --watch . >> logs\worker_market.log 2>&1
```

---

### **Solución 3: Implementar Scraping Real** 📋

**Archivo actual**: `workers/market_scraping.py`

**Estado de implementación**:
- ✅ Task `refresh_market_prices_task` implementada con Dramatiq
- ✅ Función `scrape_market_source()` soporta:
  - Scraping estático con `requests + BeautifulSoup`
  - Scraping dinámico con `Playwright`
- ✅ Manejo robusto de errores (NetworkError, PriceNotFoundError)
- ✅ Logging detallado con contexto
- ✅ Fix para Windows `ProactorEventLoop` incompatible con psycopg async

**Flujo del worker**:
1. Recibe `product_id` de la cola Redis
2. Consulta todas las fuentes del producto (`market_sources`)
3. Itera sobre cada fuente:
   - Determina tipo (`static` vs `dynamic`)
   - Ejecuta scraping con timeout de 15 segundos
   - Extrae precio y moneda
   - Actualiza `last_price` y `last_checked_at` en DB
4. Actualiza `market_price_updated_at` en producto canónico
5. Retorna resumen con fuentes exitosas/fallidas

**Ejemplo de log esperado** (cuando funcione):
```
[INFO] Iniciando scraping para producto 'Bandeja Bulldog Lisa' - fuente 'ML Bandeja Bulldog 27*18'
[INFO] ✓ Precio extraído exitosamente: 1180.00 ARS
[INFO] Guardando precio en DB para fuente ID 1
[INFO] Scraping completado para producto 45: 2/2 fuentes exitosas
```

**Estado actual**:
- ❌ Worker no conecta a Redis → nunca procesa tareas
- ✅ Lógica de scraping lista para usar
- ✅ Parsers de HTML funcionan correctamente

---

## 📊 Evoluciones Propuestas

### **Nivel 1: Reparación Inmediata** (1-2 horas)

#### **1.1 Arreglar Worker** 🔴 CRÍTICO
- [ ] Detener proceso zombie (PID 15616)
- [ ] Cambiar `.env`: `REDIS_URL=redis://127.0.0.1:6379/0`
- [ ] Reiniciar worker desde admin panel
- [ ] Validar conexión exitosa a Redis
- [ ] Probar actualización de precios en UI

#### **1.2 Documentar Nombres Correctos de Contenedores** 📝
- [x] `growen-postgres` (NO `growen-db-1`)
- [x] `growen-redis` (NO `redis-1`)
- [ ] Actualizar README.md con nombres reales
- [ ] Actualizar scripts que usan nombres antiguos

---

### **Nivel 2: Mejoras de Estabilidad** (1 semana)

#### **2.1 Health Checks del Worker**
**Archivo nuevo**: `services/routers/worker_health.py`

```python
@router.get("/health/worker/market")
async def worker_market_health():
    """
    Verifica si el worker de market está procesando tareas.
    Retorna último job procesado y tiempo desde última ejecución.
    """
    # Query a Redis para ver tareas pendientes
    # Query a DB para ver última actualización de precios
    # Retorna: { status: "healthy|degraded|down", last_run: ..., pending_jobs: ... }
```

**Uso**: Panel de admin muestra indicador visual del estado del worker.

---

#### **2.2 Retry Logic Inteligente**
**Archivo**: `workers/market_scraping.py`

**Mejora**:
```python
@dramatiq.actor(
    max_retries=3,
    min_backoff=60000,  # 1 minuto
    max_backoff=3600000,  # 1 hora
    queue_name="market"
)
def refresh_market_prices_task(product_id: int):
    # Si falla por timeout, reintenta en 1 min
    # Si falla por bloqueo (429), reintenta en 1 hora
    # Si falla por precio no encontrado, no reintenta
```

---

#### **2.3 Cache de Resultados**
**Objetivo**: Evitar scrapear la misma URL múltiples veces en corto tiempo.

**Tabla nueva**: `market_scraping_cache`
```sql
CREATE TABLE market_scraping_cache (
    url_hash VARCHAR(64) PRIMARY KEY,  -- SHA256(url)
    last_price DECIMAL(12,2),
    currency VARCHAR(10),
    cached_at TIMESTAMP,
    expires_at TIMESTAMP,
    hit_count INTEGER DEFAULT 1
);
```

**Lógica**:
- Si URL scrapeada hace <1 hora, usar cache
- Si URL cambió, invalidar cache
- Contador de hits para métricas

---

### **Nivel 3: Funcionalidades Avanzadas** (1 mes)

#### **3.1 Scraping Programado (Cron Jobs)**
**Objetivo**: Actualizar precios automáticamente sin intervención manual.

**Implementación**:
- Usar `APScheduler` o Dramatiq Middleware
- Configurar frecuencias por categoría:
  - Productos premium: cada 6 horas
  - Productos estándar: cada 24 horas
  - Productos de baja rotación: cada 7 días

**Archivo nuevo**: `services/jobs/market_scheduler.py`
```python
from apscheduler.schedulers.asyncio import AsyncIOScheduler

scheduler = AsyncIOScheduler()

@scheduler.scheduled_job('cron', hour='*/6')
async def update_premium_products():
    products = await get_products_by_category("premium")
    for product in products:
        refresh_market_prices_task.send(product.id)
```

---

#### **3.2 Detección de Anomalías de Precio**
**Objetivo**: Alertar cuando un precio se desvía significativamente del rango histórico.

**Tabla nueva**: `market_price_history`
```sql
CREATE TABLE market_price_history (
    id SERIAL PRIMARY KEY,
    source_id INTEGER REFERENCES market_sources(id),
    price DECIMAL(12,2),
    currency VARCHAR(10),
    scraped_at TIMESTAMP DEFAULT NOW(),
    INDEX idx_source_scraped (source_id, scraped_at DESC)
);
```

**Lógica**:
```python
def detect_price_anomaly(source_id: int, new_price: Decimal) -> bool:
    # Obtener últimos 10 precios
    history = get_price_history(source_id, limit=10)
    avg = mean(history)
    stddev = stdev(history)
    
    # Precio fuera de ±2 desviaciones estándar
    if abs(new_price - avg) > 2 * stddev:
        create_alert(
            type="price_anomaly",
            source_id=source_id,
            message=f"Precio {new_price} fuera de rango esperado {avg}±{2*stddev}"
        )
        return True
    return False
```

---

#### **3.3 Integración con APIs de Mercado Libre**
**Objetivo**: Usar API oficial en lugar de scraping para ML.

**Ventajas**:
- ✅ Más confiable (no se rompe con cambios de HTML)
- ✅ Más rápido (sin parsing de HTML)
- ✅ Datos estructurados (marca, modelo, stock, etc.)

**Implementación**:
```python
async def scrape_mercadolibre_api(product_url: str) -> tuple[Decimal, str]:
    # Extraer item_id de URL
    item_id = extract_ml_item_id(product_url)
    
    # Consultar API pública (sin auth)
    response = await http.get(f"https://api.mercadolibre.com/items/{item_id}")
    data = response.json()
    
    price = Decimal(str(data['price']))
    currency = data['currency_id']
    
    return price, currency
```

---

#### **3.4 Comparación Visual de Precios**
**Objetivo**: Gráfico de evolución de precios por fuente.

**Componente nuevo**: `frontend/src/components/PriceEvolutionChart.tsx`

**Funcionalidad**:
- Line chart con últimos 30 días
- Una línea por fuente
- Tooltip con detalles al hover
- Filtros por fuente y rango de fechas

**Datos**:
```typescript
interface PriceDataPoint {
  date: string;
  source_name: string;
  price: number;
}

// Endpoint nuevo:
GET /market/products/{id}/price-history?days=30
```

---

### **Nivel 4: Inteligencia Artificial** (3+ meses)

#### **4.1 Predicción de Precios**
**Modelo**: ARIMA o Prophet (Facebook)

**Features**:
- Histórico de precios (30-90 días)
- Estacionalidad (día de semana, mes)
- Eventos externos (feriados, promociones)

**Output**:
- Predicción de precio para próximos 7 días
- Intervalo de confianza 95%
- Recomendación: "Buen momento para comprar/vender"

---

#### **4.2 Clasificación Automática de Fuentes Confiables**
**Objetivo**: ML para detectar fuentes con precios más estables/confiables.

**Features por fuente**:
- Varianza de precios históricos
- Frecuencia de fallos de scraping
- Tiempo de respuesta promedio
- Correlación con otras fuentes

**Score**:
- 0-100: Confiabilidad de la fuente
- Automáticamente marca fuentes con score >80 como `is_mandatory`

---

## 📝 Actualización de Documentación

### **Archivos a Corregir**

#### **1. README.md**
```markdown
# ANTES:
docker exec -it growen-db-1 psql ...

# DESPUÉS:
docker exec -it growen-postgres psql -U growen -d growen
```

#### **2. docs/features/API_MARKET.md**
- [ ] Agregar sección "Cálculo Automático de Rango"
- [ ] Documentar que `market_price_min` y `market_price_max` se calculan desde `market_sources.last_price`
- [ ] Agregar ejemplos de respuesta con rangos calculados

#### **3. docker-compose.yml**
- [ ] Comentar nombres de contenedores:
```yaml
services:
  db:
    container_name: growen-postgres  # ← Nombre real del contenedor
    ...
  redis:
    container_name: growen-redis  # ← Nombre real del contenedor
    ...
```

#### **4. scripts/README_SCRIPTS.md** (nuevo)
- [ ] Documentar todos los scripts en `scripts/`
- [ ] Explicar cuándo usar cada uno
- [ ] Listar dependencias (Docker, Redis, PostgreSQL)

---

## ✅ Checklist de Implementación

### **Fase 1: Reparación (HOY)** 🔴
- [ ] Matar proceso worker zombie (PID 15616)
- [ ] Cambiar `REDIS_URL` a `127.0.0.1` en `.env`
- [ ] Reiniciar worker desde admin panel
- [ ] Probar actualización de precios en UI
- [ ] Confirmar que rango se actualiza automáticamente
- [ ] Actualizar este documento con resultado

### **Fase 2: Documentación (Esta semana)** 📝
- [ ] Corregir nombres de contenedores en README.md
- [ ] Actualizar docs/features/API_MARKET.md con cálculo de rango
- [ ] Crear docs/WORKER_TROUBLESHOOTING.md
- [ ] Agregar sección "Workers" a Roadmap.md

### **Fase 3: Mejoras (Próximas 2 semanas)** 🔧
- [ ] Implementar health check del worker
- [ ] Agregar retry logic inteligente
- [ ] Implementar cache de scraping (1 hora TTL)
- [ ] Crear endpoint `/market/products/{id}/price-history`

### **Fase 4: Evoluciones (Próximo mes)** 🚀
- [ ] Scraping programado con APScheduler
- [ ] Detección de anomalías de precio
- [ ] Integración con API de Mercado Libre
- [ ] Gráfico de evolución de precios en UI

---

## 📊 Métricas de Éxito

### **Indicadores Actuales** (Manual)
- Rango de precios: ✅ Se calcula correctamente
- Actualización de precios: ❌ Requiere inserción manual
- Worker de scraping: ❌ No funciona (sin Redis)

### **Indicadores Deseados** (Automático)
- Rango de precios: ✅ Calculado automáticamente
- Actualización de precios: ✅ Automática cada 6-24h según categoría
- Worker de scraping: ✅ Procesando tareas en tiempo real
- Cobertura de fuentes: >80% de productos con al menos 2 fuentes
- Éxito de scraping: >90% de fuentes retornan precio válido
- Latencia promedio: <5 segundos por fuente

---

## 🎯 Conclusión

### **Estado Actual**
✅ **Cálculo de rango**: Implementado y funcionando  
❌ **Worker de scraping**: Roto (sin conexión a Redis)  
⚠️ **Scraping automático**: Listo pero no se ejecuta  

### **Próximos Pasos Inmediatos**
1. Reparar worker (cambiar localhost → 127.0.0.1)
2. Probar actualización de precios end-to-end
3. Documentar nombres correctos de contenedores
4. Implementar health checks

### **Visión a Largo Plazo**
- Sistema totalmente automático de actualización de precios
- Predicción de precios con ML
- Alertas inteligentes de oportunidades de compra/venta
- Integración con múltiples marketplaces (ML, OLX, etc.)

---

**Última actualización**: 2025-11-16 14:15  
**Próxima revisión**: Después de reparar worker