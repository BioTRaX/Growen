# Sistema de Alertas de Variación de Precios de Mercado

Sistema automatizado para detectar y notificar variaciones significativas en precios de mercado.

## Inicio Rápido

### 1. Configurar Variables de Entorno

Copiar configuración de ejemplo al archivo `.env`:

```bash
# Copiar configuración
cat .env.alerts.example >> .env

# O agregar manualmente:
ALERT_THRESHOLD_SALE_VS_MARKET=0.15
ALERT_THRESHOLD_MARKET_VS_PREVIOUS=0.20
ALERT_THRESHOLD_SPIKE=0.30
ALERT_THRESHOLD_DROP=0.25
ALERT_COOLDOWN_HOURS=24
ALERT_EMAIL_ENABLED=false
```

### 2. Aplicar la migración versionada

```powershell
.\.venv\Scripts\python.exe -m alembic upgrade head
```

`market_alerts` se instala exclusivamente mediante `20260721_market_observability_v1`; no generar SQL ni revisiones locales ad hoc.

### 3. Verificar instalación y worker

```bash
# Verificar tabla creada
psql -d growen -c "\d market_alerts"

# Verificar índices
psql -d growen -c "\di market_alerts*"

# Test de API
curl -X GET "http://localhost:8000/alerts/stats" \
  -H "Authorization: Bearer $TOKEN"
```

## Arquitectura

```
Worker Scraping → Detección Automática → Base de Datos → API REST → Frontend
                  (services/market/      (market_alerts)  (6 endpoints)
                   alerts.py)
```

## Tipos de Alerta

| Tipo | Descripción | Umbral Default |
|------|-------------|----------------|
| `sale_vs_market` | Diferencia venta vs mercado | 15% |
| `market_vs_previous` | Cambio histórico de mercado | 20% |
| `market_spike` | Aumento repentino | 30% |
| `market_drop` | Caída repentina | 25% |

## API Endpoints

| Método | Ruta | Descripción |
|--------|------|-------------|
| GET | `/alerts` | Lista paginada con filtros |
| GET | `/alerts/stats` | Estadísticas globales |
| GET | `/alerts/{id}` | Detalle de alerta |
| PATCH | `/alerts/{id}/resolve` | Marcar como resuelta |
| POST | `/alerts/bulk-resolve` | Resolver múltiples |
| DELETE | `/alerts/{id}` | Eliminar (admin) |

## Ejemplos de Uso

### Listar alertas críticas sin resolver

```bash
curl -X GET "http://localhost:8000/alerts?resolved=false&severity=critical" \
  -H "Authorization: Bearer $TOKEN"
```

### Obtener estadísticas

```bash
curl -X GET "http://localhost:8000/alerts/stats" \
  -H "Authorization: Bearer $TOKEN"
```

### Resolver alerta

```bash
curl -X PATCH "http://localhost:8000/alerts/123/resolve" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"resolution_note": "Precio ajustado manualmente"}'
```

### Resolver múltiples alertas

```bash
curl -X POST "http://localhost:8000/alerts/bulk-resolve" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "alert_ids": [123, 456, 789],
    "resolution_note": "Revisión masiva completada"
  }'
```

## Integración con Frontend

El endpoint `GET /market/products` ahora incluye:

```json
{
  "has_active_alerts": true,
  "active_alerts_count": 2
}
```

Ejemplo de uso en React:

```jsx
{item.has_active_alerts && (
  <Badge color="warning">
    🚨 {item.active_alerts_count} alerta{item.active_alerts_count > 1 ? 's' : ''}
  </Badge>
)}
```

## Consultas SQL Útiles

### Alertas activas por producto

```sql
SELECT 
  cp.ng_sku,
  cp.name,
  COUNT(ma.id) as alert_count,
  STRING_AGG(ma.alert_type, ', ') as alert_types
FROM canonical_products cp
JOIN market_alerts ma ON cp.id = ma.product_id
WHERE ma.resolved = false
GROUP BY cp.id
ORDER BY alert_count DESC
LIMIT 10;
```

### Alertas por severidad

```sql
SELECT 
  severity,
  COUNT(*) as count,
  ROUND(AVG(delta_percentage * 100), 2) as avg_delta_pct
FROM market_alerts
WHERE resolved = false
GROUP BY severity
ORDER BY 
  CASE severity
    WHEN 'critical' THEN 1
    WHEN 'high' THEN 2
    WHEN 'medium' THEN 3
    WHEN 'low' THEN 4
  END;
```

### Tendencias de alertas (últimos 7 días)

```sql
SELECT 
  DATE(created_at) as date,
  alert_type,
  COUNT(*) as count
FROM market_alerts
WHERE created_at > NOW() - INTERVAL '7 days'
GROUP BY DATE(created_at), alert_type
ORDER BY date DESC, alert_type;
```

## Troubleshooting

### No se generan alertas

1. Verificar worker corriendo:
   ```bash
   # Windows
   scripts\start-dev.ps1 -WithMarketWorker
   
   # Linux/Mac
   dramatiq workers.market_scraping --queues market
   ```

2. Verificar logs:
   ```bash
   tail -f logs/worker_market.log | grep "🚨"
   ```

3. Verificar umbrales:
   ```bash
   grep "ALERT_THRESHOLD" .env
   ```

### Alertas duplicadas

1. Verificar cooldown configurado:
   ```bash
   grep "ALERT_COOLDOWN_HOURS" .env
   ```

2. Query de diagnóstico:
   ```sql
   SELECT 
     product_id,
     alert_type,
     COUNT(*) as count,
     MAX(created_at) as last_alert
   FROM market_alerts
   WHERE created_at > NOW() - INTERVAL '24 hours'
   GROUP BY product_id, alert_type
   HAVING COUNT(*) > 1;
   ```

### API devuelve 500

1. Verificar logs:
   ```bash
   tail -f logs/backend.log | grep "ERROR"
   ```

2. Verificar migración:
   ```bash
   alembic current
   ```

3. Verificar tabla existe:
   ```bash
   psql -d growen -c "SELECT COUNT(*) FROM market_alerts;"
   ```

## Archivos Principales

| Archivo | Descripción |
|---------|-------------|
| `db/models.py` | Modelo `MarketAlert` |
| `services/market/alerts.py` | Lógica de detección |
| `services/routers/alerts.py` | API endpoints |
| `workers/market_scraping.py` | Integración post-scraping |
| `docs/MARKET_ALERTS.md` | Documentación completa |
| `.env.alerts.example` | Configuración ejemplo |

## Próximos Pasos

- [ ] Implementar envío de emails (SMTP)
- [ ] Dashboard de alertas en frontend
- [ ] Notificaciones WebSocket en tiempo real
- [ ] Integración con Telegram
- [ ] Tests unitarios e integración
- [ ] Métricas de alertas (Prometheus)

## Documentación Completa

Ver `docs/MARKET_ALERTS.md` para:
- Arquitectura detallada
- Diagramas de flujo
- Ejemplos completos
- Guía de troubleshooting extendida
- Referencias de API

---

**Versión**: 1.0.0  
**Última actualización**: 2025-01-10
