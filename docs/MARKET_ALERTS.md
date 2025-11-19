<!-- NG-HEADER: Nombre de archivo: MARKET_ALERTS.md -->
<!-- NG-HEADER: Ubicación: docs/MARKET_ALERTS.md -->
<!-- NG-HEADER: Descripción: Documentación sistema de alertas de variación de precios de mercado -->
<!-- NG-HEADER: Lineamientos: Ver AGENTS.md -->

# Sistema de Alertas de Variación de Precios de Mercado

Este documento describe el sistema automatizado de detección y gestión de alertas por variaciones significativas en los precios de mercado.

## Índice

1. [Arquitectura General](#arquitectura-general)
2. [Tipos de Alerta](#tipos-de-alerta)
3. [Umbrales y Configuración](#umbrales-y-configuración)
4. [Modelo de Datos](#modelo-de-datos)
5. [Flujo de Detección](#flujo-de-detección)
6. [API Endpoints](#api-endpoints)
7. [Integración con Frontend](#integración-con-frontend)
8. [Sistema de Notificaciones](#sistema-de-notificaciones)
9. [Troubleshooting](#troubleshooting)

---

## Arquitectura General

El sistema de alertas se compone de 4 capas:

```
┌─────────────────────────────────────────────────────────────┐
│                   1. DETECCIÓN AUTOMÁTICA                    │
│  workers/market_scraping.py → services/market/alerts.py     │
│  Ejecuta post-scraping, calcula deltas, crea alertas        │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│                   2. PERSISTENCIA                            │
│  db/models.py → MarketAlert                                  │
│  Almacena alertas con auditoría completa                    │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│                   3. API REST                                │
│  services/routers/alerts.py                                  │
│  6 endpoints: list, stats, detail, resolve, bulk, delete    │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│                   4. FRONTEND                                │
│  Indicador visual en lista de productos                     │
│  Dashboard de alertas (pendiente)                           │
└─────────────────────────────────────────────────────────────┘
```

---

## Tipos de Alerta

El sistema genera 4 tipos de alertas automáticamente:

### 1. `sale_vs_market`
**Descripción**: El precio de venta actual difiere significativamente del precio de mercado.

**Cuándo se genera**: `abs(sale_price - new_market_price) / sale_price > THRESHOLD_SALE_VS_MARKET`

**Umbral por defecto**: 15%

**Ejemplo**:
- Precio de venta: $1000
- Precio de mercado: $1200
- Delta: 20% → **Alerta generada**

**Interpretación**: 
- Delta positivo: Estamos vendiendo más barato que el mercado (oportunidad de ajustar precio)
- Delta negativo: Estamos vendiendo más caro que el mercado (riesgo de perder competitividad)

---

### 2. `market_vs_previous`
**Descripción**: El nuevo precio de mercado difiere significativamente del anterior registrado.

**Cuándo se genera**: `abs(new_market_price - market_price_reference) / market_price_reference > THRESHOLD_MARKET_VS_PREVIOUS`

**Umbral por defecto**: 20%

**Ejemplo**:
- Precio anterior: $1000
- Precio nuevo: $1300
- Delta: 30% → **Alerta generada**

**Interpretación**: Cambio drástico en la referencia de mercado (tendencia alcista o bajista).

---

### 3. `market_spike`
**Descripción**: Aumento repentino del precio de mercado.

**Cuándo se genera**: 
- `(new_market_price - market_price_reference) / market_price_reference > THRESHOLD_SPIKE`
- **Y** delta es positivo

**Umbral por defecto**: 30%

**Ejemplo**:
- Precio anterior: $1000
- Precio nuevo: $1400
- Delta: +40% → **Alerta generada (spike)**

**Interpretación**: Aumento drástico de precio (escasez, inflación, cambio de proveedor).

---

### 4. `market_drop`
**Descripción**: Caída repentina del precio de mercado.

**Cuándo se genera**: 
- `abs(new_market_price - market_price_reference) / market_price_reference > THRESHOLD_DROP`
- **Y** delta es negativo

**Umbral por defecto**: 25%

**Ejemplo**:
- Precio anterior: $1000
- Precio nuevo: $700
- Delta: -30% → **Alerta generada (drop)**

**Interpretación**: Caída drástica de precio (promoción, liquidación, competencia agresiva).

---

## Umbrales y Configuración

### Variables de Entorno

Copiar `.env.alerts.example` a `.env` y ajustar según necesidad:

```bash
# Umbrales (valores entre 0 y 1)
ALERT_THRESHOLD_SALE_VS_MARKET=0.15      # 15%
ALERT_THRESHOLD_MARKET_VS_PREVIOUS=0.20  # 20%
ALERT_THRESHOLD_SPIKE=0.30               # 30%
ALERT_THRESHOLD_DROP=0.25                # 25%

# Cooldown (horas)
ALERT_COOLDOWN_HOURS=24

# Notificaciones
ALERT_EMAIL_ENABLED=false
```

### Severidad Automática

El sistema calcula automáticamente la severidad basándose en el `delta_percentage` y el `alert_type`:

#### `market_spike` / `market_drop`
| Delta | Severidad |
|-------|-----------|
| ≥ 50% | `critical` |
| ≥ 35% | `high` |
| ≥ 25% | `medium` |
| < 25% | `low` |

#### `sale_vs_market`
| Delta | Severidad |
|-------|-----------|
| ≥ 30% | `high` |
| ≥ 20% | `medium` |
| < 20% | `low` |

#### `market_vs_previous`
| Delta | Severidad |
|-------|-----------|
| ≥ 40% | `high` |
| ≥ 25% | `medium` |
| < 25% | `low` |

---

## Modelo de Datos

### Tabla `market_alerts`

```sql
CREATE TABLE market_alerts (
    id SERIAL PRIMARY KEY,
    product_id INTEGER NOT NULL REFERENCES canonical_products(id) ON DELETE CASCADE,
    
    -- Clasificación
    alert_type VARCHAR(50) NOT NULL,  -- sale_vs_market | market_vs_previous | market_spike | market_drop
    severity VARCHAR(20) NOT NULL,    -- low | medium | high | critical
    
    -- Valores
    old_value NUMERIC(12,2),          -- Precio anterior (nullable para primer scraping)
    new_value NUMERIC(12,2) NOT NULL, -- Precio nuevo
    delta_percentage NUMERIC(8,4) NOT NULL, -- Delta porcentual (ej: 0.2500 = 25%)
    message TEXT NOT NULL,            -- Mensaje descriptivo
    
    -- Estado
    resolved BOOLEAN DEFAULT FALSE,
    resolved_at TIMESTAMP,
    resolved_by INTEGER REFERENCES users(id) ON DELETE SET NULL,
    resolution_note TEXT,
    
    -- Notificaciones
    email_sent BOOLEAN DEFAULT FALSE,
    email_sent_at TIMESTAMP,
    
    -- Auditoría
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);
```

### Índices

```sql
CREATE INDEX idx_market_alerts_product_id ON market_alerts(product_id);
CREATE INDEX idx_market_alerts_created_at ON market_alerts(created_at);
CREATE INDEX idx_market_alerts_resolved ON market_alerts(resolved);
CREATE INDEX idx_market_alerts_product_active ON market_alerts(product_id, resolved);
```

### Relaciones

- **`product`**: `MarketAlert.product_id → CanonicalProduct.id` (CASCADE)
- **`resolver`**: `MarketAlert.resolved_by → User.id` (SET NULL)

---

## Flujo de Detección

### Diagrama de Flujo

```
┌─────────────────────────────────────────────────────────────┐
│  1. Worker de Scraping finaliza para un producto            │
│     (workers/market_scraping.py)                             │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│  2. Calcula market_price_reference (promedio de fuentes)    │
│     market_price_ref = avg(successful_prices)               │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│  3. Llama detect_price_alerts()                              │
│     (services/market/alerts.py)                              │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│  4. Obtiene producto de BD                                   │
│     - sale_price                                             │
│     - market_price_reference (anterior)                      │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│  5. Compara new_market_price vs sale_price                   │
│     → Si delta > 15% → alerta sale_vs_market                 │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│  6. Compara new_market_price vs market_price_reference       │
│     → Si delta > 20% → alerta market_vs_previous             │
│     → Si delta > 30% y ↑ → alerta market_spike               │
│     → Si delta > 25% y ↓ → alerta market_drop                │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│  7. Para cada alerta detectada:                              │
│     a. Verifica cooldown (evitar duplicados 24h)             │
│     b. Determina severidad automáticamente                   │
│     c. Crea registro en BD                                   │
│     d. Programa notificación (placeholder)                   │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│  8. Commit y retorna lista de alertas creadas                │
│     Log: "🚨 Generadas N alerta(s) de precio"                │
└─────────────────────────────────────────────────────────────┘
```

### Función Principal: `detect_price_alerts()`

**Ubicación**: `services/market/alerts.py`

**Firma**:
```python
async def detect_price_alerts(
    db: AsyncSession,
    product_id: int,
    new_market_price: Decimal,
    currency: str = "ARS"
) -> List[MarketAlert]
```

**Retorno**: Lista de alertas creadas (puede ser vacía si no hay variaciones significativas).

**Manejo de errores**: 
- Try/except en el worker para no bloquear scraping principal
- Logging detallado con prefijo `[ALERT]`
- Nunca lanza excepciones hacia arriba

---

## API Endpoints

Base URL: `/alerts`

### 1. `GET /alerts` - Lista paginada

**Query Parameters**:
- `page` (int, ≥1): Número de página (default: 1)
- `page_size` (int, 1-100): Tamaño de página (default: 20)
- `resolved` (bool, opcional): Filtrar por estado resuelto
- `severity` (str, opcional): Filtrar por severidad (`low`, `medium`, `high`, `critical`)
- `alert_type` (str, opcional): Filtrar por tipo
- `product_id` (int, opcional): Filtrar por producto

**Respuesta**:
```json
{
  "items": [
    {
      "id": 123,
      "product_id": 456,
      "product_name": "Tornillo M8 x 50mm",
      "product_ng_sku": "NG-TOR-0456",
      "alert_type": "market_spike",
      "severity": "high",
      "old_value": 1000.00,
      "new_value": 1400.00,
      "delta_percentage": 0.4000,
      "message": "Aumento del 40.00% en precio de mercado",
      "resolved": false,
      "resolved_at": null,
      "resolver_name": null,
      "resolution_note": null,
      "email_sent": false,
      "email_sent_at": null,
      "created_at": "2025-01-10T14:30:00Z",
      "updated_at": "2025-01-10T14:30:00Z"
    }
  ],
  "total": 150,
  "page": 1,
  "page_size": 20,
  "total_pages": 8
}
```

**Permisos**: `admin`, `colaborador`

**Ejemplo**:
```bash
curl -X GET "http://localhost:8000/alerts?resolved=false&severity=high&page=1" \
  -H "Authorization: Bearer $TOKEN"
```

---

### 2. `GET /alerts/stats` - Estadísticas globales

**Respuesta**:
```json
{
  "active_alerts": 45,
  "resolved_alerts": 230,
  "critical_alerts": 3,
  "alerts_last_24h": 12,
  "total_alerts": 275
}
```

**Permisos**: `admin`, `colaborador`

**Ejemplo**:
```bash
curl -X GET "http://localhost:8000/alerts/stats" \
  -H "Authorization: Bearer $TOKEN"
```

---

### 3. `GET /alerts/{id}` - Detalle de alerta

**Respuesta**: Objeto `AlertResponse` (igual que item de lista).

**Errores**:
- `404`: Alerta no encontrada

**Permisos**: `admin`, `colaborador`

---

### 4. `PATCH /alerts/{id}/resolve` - Resolver alerta

**Body**:
```json
{
  "resolution_note": "Ajustado precio de venta según nueva referencia de mercado"
}
```

**Respuesta**: Objeto `AlertResponse` actualizado con:
- `resolved: true`
- `resolved_at: timestamp`
- `resolved_by: user_id`
- `resolution_note: nota`

**Errores**:
- `404`: Alerta no encontrada
- `400`: Alerta ya resuelta

**Permisos**: Usuario autenticado

**Ejemplo**:
```bash
curl -X PATCH "http://localhost:8000/alerts/123/resolve" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"resolution_note": "Precio ajustado manualmente"}'
```

---

### 5. `POST /alerts/bulk-resolve` - Resolver múltiples alertas

**Body**:
```json
{
  "alert_ids": [123, 456, 789],
  "resolution_note": "Revisión masiva de precios completada"
}
```

**Respuesta**:
```json
{
  "resolved_count": 3,
  "message": "3 alerta(s) marcada(s) como resuelta(s)"
}
```

**Límites**:
- Mínimo 1 ID
- Máximo 100 IDs por request

**Permisos**: Usuario autenticado

**Ejemplo**:
```bash
curl -X POST "http://localhost:8000/alerts/bulk-resolve" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"alert_ids": [123, 456], "resolution_note": "Batch review"}'
```

---

### 6. `DELETE /alerts/{id}` - Eliminar alerta

**Respuesta**:
```json
{
  "message": "Alerta eliminada exitosamente"
}
```

**Errores**:
- `404`: Alerta no encontrada

**Permisos**: `admin` only

**Ejemplo**:
```bash
curl -X DELETE "http://localhost:8000/alerts/123" \
  -H "Authorization: Bearer $TOKEN"
```

---

## Integración con Frontend

### Lista de Productos del Módulo Mercado

**Endpoint modificado**: `GET /market/products`

**Campos agregados al schema `MarketProductItem`**:
- `has_active_alerts` (bool): Indica si hay alertas activas
- `active_alerts_count` (int): Número de alertas activas

**Respuesta**:
```json
{
  "items": [
    {
      "product_id": 456,
      "preferred_name": "Tornillo M8 x 50mm",
      "sale_price": 1000.00,
      "market_price_reference": 1400.00,
      "has_active_alerts": true,
      "active_alerts_count": 2,
      "..."
    }
  ],
  "..."
}
```

**Implementación UI (sugerido)**:
```jsx
{item.has_active_alerts && (
  <Badge color="warning">
    🚨 {item.active_alerts_count} alerta{item.active_alerts_count > 1 ? 's' : ''}
  </Badge>
)}
```

---

### Dashboard de Alertas (Pendiente)

Componente dedicado para visualizar y gestionar alertas:

**Funcionalidades sugeridas**:
- Tabla con filtros (severity, tipo, producto)
- Indicadores visuales por severidad:
  - 🔴 `critical`
  - 🟠 `high`
  - 🟡 `medium`
  - 🟢 `low`
- Acciones:
  - Ver detalle de producto
  - Marcar como resuelta (modal con nota)
  - Selección múltiple + resolución en lote
- Estadísticas en cards:
  - Alertas activas
  - Críticas sin resolver
  - Alertas últimas 24h

**Ruta sugerida**: `/mercado/alertas`

---

## Sistema de Notificaciones

### Estado Actual: Placeholder

La función `schedule_alert_notification()` está implementada como placeholder.

**Ubicación**: `services/market/alerts.py`

```python
async def schedule_alert_notification(
    db: AsyncSession,
    alert: MarketAlert,
    product: CanonicalProduct
) -> None:
    """
    TODO: Implementar sistema real de notificaciones
    
    Opciones:
    1. Email vía SMTP
    2. WebSocket push al frontend
    3. Notificaciones Telegram
    4. Cola Dramatiq para procesamiento asíncrono
    """
    pass
```

### Implementación Futura

#### Opción 1: Email (SMTP)

**Variables de entorno requeridas**:
```bash
ALERT_EMAIL_ENABLED=true
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=alerts@growen.com
SMTP_PASSWORD=xxxxx
ALERT_EMAIL_RECIPIENTS=admin@growen.com,sales@growen.com
```

**Template de email**:
```html
<h2>🚨 Alerta de Precio - {product_name}</h2>
<p><strong>Tipo:</strong> {alert_type}</p>
<p><strong>Severidad:</strong> {severity}</p>
<p><strong>Precio anterior:</strong> ${old_value}</p>
<p><strong>Precio nuevo:</strong> ${new_value}</p>
<p><strong>Cambio:</strong> {delta_percentage}%</p>
<p><a href="https://growen.com/mercado/alertas/{alert_id}">Ver detalles</a></p>
```

#### Opción 2: WebSocket

Enviar evento en tiempo real al frontend:
```python
from services.websocket import notify_users

await notify_users(
    event_type="market_alert",
    data={
        "alert_id": alert.id,
        "product_id": alert.product_id,
        "severity": alert.severity,
        "message": alert.message
    },
    roles=["admin", "colaborador"]
)
```

#### Opción 3: Telegram

Integración con bot de Telegram:
```python
from services.integrations.telegram import send_message

await send_message(
    chat_id=ALERTS_CHAT_ID,
    text=f"🚨 {alert.message}\nProducto: {product.name}\nSKU: {product.ng_sku}"
)
```

---

## Troubleshooting

### Problema: No se generan alertas

**Diagnóstico**:
1. Verificar que el worker de scraping esté ejecutándose:
   ```bash
   # Windows
   scripts\start_worker_market.cmd
   
   # Linux/Mac
   dramatiq workers.market_scraping --queues market
   ```

2. Verificar logs del worker:
   ```bash
   tail -f logs/worker_market.log | grep "🚨"
   ```

3. Verificar umbral de configuración:
   ```bash
   # .env
   ALERT_THRESHOLD_SALE_VS_MARKET=0.15  # ¿Es muy alto?
   ```

4. Verificar que haya variación real:
   ```sql
   SELECT 
       id, 
       name, 
       sale_price, 
       market_price_reference 
   FROM canonical_products 
   WHERE market_price_reference IS NOT NULL
   LIMIT 10;
   ```

---

### Problema: Alertas duplicadas

**Diagnóstico**:
1. Verificar cooldown:
   ```bash
   ALERT_COOLDOWN_HOURS=24  # ¿Es suficiente?
   ```

2. Verificar alertas recientes:
   ```sql
   SELECT 
       product_id, 
       alert_type, 
       COUNT(*) as count,
       MAX(created_at) as last_created
   FROM market_alerts
   WHERE created_at > NOW() - INTERVAL '24 hours'
   GROUP BY product_id, alert_type
   HAVING COUNT(*) > 1;
   ```

3. Verificar lógica de prevención en código:
   ```python
   # services/market/alerts.py
   recent_alert = await check_recent_alert_exists(...)
   if recent_alert:
       logger.info(f"[ALERT] Ya existe alerta reciente...")
       continue
   ```

---

### Problema: Severidad incorrecta

**Diagnóstico**:
1. Revisar cálculo de `delta_percentage`:
   ```python
   delta_percentage = calculate_percentage_change(old_value, new_value)
   # Debe retornar valor absoluto (ej: 0.25 para 25%)
   ```

2. Verificar lógica de `determine_severity()`:
   ```python
   # services/market/alerts.py línea ~100
   def determine_severity(delta_percentage: float, alert_type: str) -> str:
       # Revisar umbrales por tipo
   ```

3. Logs de debugging:
   ```python
   logger.debug(f"Delta: {delta_percentage}, Type: {alert_type}, Severity: {severity}")
   ```

---

### Problema: API devuelve 500

**Diagnóstico**:
1. Verificar logs del backend:
   ```bash
   tail -f logs/backend.log | grep "ERROR"
   ```

2. Verificar migración aplicada:
   ```bash
   alembic current
   alembic history | grep "market_alert"
   ```

3. Verificar permisos de usuario:
   ```sql
   SELECT id, email, role FROM users WHERE id = <user_id>;
   ```

4. Test manual del endpoint:
   ```bash
   curl -X GET "http://localhost:8000/alerts/stats" \
     -H "Authorization: Bearer $TOKEN" \
     -v
   ```

---

### Problema: Frontend no muestra indicador

**Diagnóstico**:
1. Verificar respuesta del endpoint:
   ```bash
   curl -X GET "http://localhost:8000/market/products?page=1" \
     -H "Authorization: Bearer $TOKEN" \
     | jq '.items[0] | {has_active_alerts, active_alerts_count}'
   ```

2. Verificar query de alertas en backend:
   ```python
   # services/routers/market.py
   # Verificar que alert_subquery esté correctamente joinado
   ```

3. Verificar componente React:
   ```jsx
   console.log('Alert data:', item.has_active_alerts, item.active_alerts_count);
   ```

---

## Resumen de Comandos Útiles

```bash
# Verificar alertas activas
psql -d growen -c "SELECT COUNT(*) FROM market_alerts WHERE resolved = false;"

# Alertas por severidad
psql -d growen -c "SELECT severity, COUNT(*) FROM market_alerts WHERE resolved = false GROUP BY severity;"

# Producto con más alertas
psql -d growen -c "
  SELECT 
    cp.ng_sku, 
    cp.name, 
    COUNT(ma.id) as alert_count
  FROM canonical_products cp
  JOIN market_alerts ma ON cp.id = ma.product_id
  WHERE ma.resolved = false
  GROUP BY cp.id
  ORDER BY alert_count DESC
  LIMIT 10;
"

# Limpiar alertas viejas resueltas (>30 días)
psql -d growen -c "
  DELETE FROM market_alerts 
  WHERE resolved = true 
    AND resolved_at < NOW() - INTERVAL '30 days';
"

# Estadísticas rápidas
curl -s http://localhost:8000/alerts/stats | jq
```

---

## Referencias

- **Worker de Scraping**: `workers/market_scraping.py`
- **Servicio de Alertas**: `services/market/alerts.py`
- **Modelo de Datos**: `db/models.py` → `MarketAlert`
- **API Router**: `services/routers/alerts.py`
- **Frontend Integration**: `services/routers/market.py` → `list_market_products()`
- **Configuración**: `.env.alerts.example`

---

**Última actualización**: 2025-01-10  
**Versión del sistema**: 1.0.0
