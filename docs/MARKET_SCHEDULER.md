<!-- NG-HEADER: Nombre de archivo: MARKET_SCHEDULER.md -->
<!-- NG-HEADER: Ubicación: docs/MARKET_SCHEDULER.md -->
<!-- NG-HEADER: Descripción: Documentación del scheduler de actualización automática de precios -->
<!-- NG-HEADER: Lineamientos: Ver AGENTS.md -->

# Scheduler de Actualización Automática de Precios de Mercado

## Resumen

Sistema de programación automática para mantener actualizados los precios de mercado mediante scraping periódico. Utiliza APScheduler + Dramatiq para ejecutar tareas de forma distribuida y resiliente.

## Arquitectura

```
┌─────────────────────────────────────────────────────────────┐
│                       APScheduler                           │
│  (Programación periódica según cron expression)            │
└──────────────────────┬──────────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────────┐
│           services/jobs/market_scheduler.py                 │
│  • Filtra productos desactualizados                         │
│  • Prioriza productos con fuentes obligatorias              │
│  • Limita productos por tanda                               │
│  • Encola tareas en Dramatiq                                │
└──────────────────────┬──────────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────────┐
│                   Dramatiq (cola 'market')                  │
│  Worker: refresh_market_prices_task                         │
└──────────────────────┬──────────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────────┐
│            workers/market_scraping.py                       │
│  • Scraping estático (requests + BeautifulSoup)             │
│  • Scraping dinámico (Playwright)                           │
│  • Actualiza MarketSource.last_price                        │
│  • Actualiza CanonicalProduct.market_price_updated_at       │
└─────────────────────────────────────────────────────────────┘
```

## Componentes

### 1. Scheduler Service (`services/jobs/market_scheduler.py`)

Módulo principal que gestiona la lógica de programación y selección de productos.

**Funciones principales:**

- `schedule_market_updates()`: Job ejecutado periódicamente por APScheduler
- `get_products_needing_update()`: Selecciona productos candidatos a actualización
- `get_scheduler_status()`: Obtiene métricas y configuración actual
- `run_manual_update()`: Ejecuta actualización fuera del scheduler
- `start_scheduler()` / `stop_scheduler()`: Control del lifecycle

### 2. Script Standalone (`scripts/run_market_update.py`)

Script para ejecutar actualizaciones desde cron o tareas programadas del SO.

**Uso:**
```bash
# Actualización con configuración por defecto
python scripts/run_market_update.py

# Con parámetros personalizados
python scripts/run_market_update.py --max-products 100 --days-threshold 7

# Solo verificar estado
python scripts/run_market_update.py --status-only
```

### 3. API Router (`services/routers/market_scheduler.py`)

Endpoints para control y monitoreo desde la UI o integraciones.

**Endpoints:**

- `GET /market/scheduler/status` - Estado y estadísticas
- `POST /market/scheduler/trigger` - Ejecución manual
- `POST /market/scheduler/enable` - Habilitar scheduler
- `POST /market/scheduler/disable` - Deshabilitar scheduler

### 4. Worker Dramatiq (`workers/market_scraping.py`)

Worker que ejecuta el scraping real de cada producto.

**Actor:**
- `refresh_market_prices_task(product_id)` - Cola: `market`, timeout: 5 min

## Configuración

### Variables de Entorno

Todas las variables se configuran en el archivo `.env`:

```bash
# ============================================
# SCHEDULER DE PRECIOS DE MERCADO
# ============================================

# Habilitar/deshabilitar scheduler automático
# Valores: true | false
MARKET_SCHEDULER_ENABLED=false

# Frecuencia de actualización (días)
# Productos cuyo market_price_updated_at sea mayor a N días serán candidatos
# Rango recomendado: 1-7 días
MARKET_UPDATE_FREQUENCY_DAYS=2

# Máximo de productos a procesar por ejecución
# Limita la carga por tanda para evitar saturación
# Rango recomendado: 20-100 productos
MARKET_MAX_PRODUCTS_PER_RUN=50

# Priorizar productos con fuentes obligatorias
# Si true, productos con al menos una fuente is_mandatory=True se procesan primero
# Valores: true | false
MARKET_PRIORITIZE_MANDATORY=true

# Horario de ejecución (cron expression) - DEPRECADO
# Ahora se configura desde la UI usando hora de inicio e intervalo
# Formato: "minuto hora día_mes mes día_semana"
# Ejemplos:
#   "0 2 * * *"     -> Todos los días a las 2:00 AM
#   "0 */12 * * *"  -> Cada 12 horas
#   "0 2 * * 0"     -> Domingos a las 2:00 AM
#   "0 3 */2 * *"   -> Cada 2 días a las 3:00 AM
MARKET_CRON_SCHEDULE="0 2 * * *"

# Hora de inicio (formato HH:MM en GMT-3, Argentina)
# Configurable desde la UI en /admin/scheduler
MARKET_SCHEDULER_START_HOUR="02:00"

# Intervalo entre ejecuciones (en horas, 1-24)
# Configurable desde la UI en /admin/scheduler
MARKET_SCHEDULER_INTERVAL_HOURS=24
```

### Configuración Recomendada por Entorno

#### Desarrollo
```bash
MARKET_SCHEDULER_ENABLED=false  # Ejecución manual
MARKET_UPDATE_FREQUENCY_DAYS=1
MARKET_MAX_PRODUCTS_PER_RUN=10
MARKET_CRON_SCHEDULE="0 */6 * * *"  # Cada 6 horas (testing)
```

#### Producción
```bash
MARKET_SCHEDULER_ENABLED=true
MARKET_UPDATE_FREQUENCY_DAYS=2
MARKET_MAX_PRODUCTS_PER_RUN=50
MARKET_PRIORITIZE_MANDATORY=true
MARKET_CRON_SCHEDULE="0 2 * * *"  # 2 AM diario
```

#### Alta Frecuencia (e-commerce activo)
```bash
MARKET_SCHEDULER_ENABLED=true
MARKET_UPDATE_FREQUENCY_DAYS=1
MARKET_MAX_PRODUCTS_PER_RUN=100
MARKET_PRIORITIZE_MANDATORY=true
MARKET_CRON_SCHEDULE="0 */8 * * *"  # Cada 8 horas
```

## Criterios de Selección de Productos

El scheduler selecciona productos basándose en:

1. **Productos con fuentes de mercado** (`MarketSource`)
2. **Estado de actualización:**
   - `market_price_updated_at IS NULL` (nunca actualizado)
   - `market_price_updated_at < (NOW - UPDATE_FREQUENCY_DAYS)` (desactualizado)

3. **Priorización (si `PRIORITIZE_MANDATORY=true`):**
   - Primero: productos con al menos una fuente `is_mandatory=True`
   - Después: resto de productos ordenados por antigüedad

4. **Límite:** Máximo `MAX_PRODUCTS_PER_RUN` productos por ejecución

### Ejemplo SQL de Selección

```sql
-- Productos candidatos (simplificado)
SELECT DISTINCT cp.id
FROM canonical_products cp
INNER JOIN market_sources ms ON cp.id = ms.product_id
WHERE 
    cp.market_price_updated_at IS NULL
    OR cp.market_price_updated_at < (NOW() - INTERVAL '2 days')
ORDER BY cp.created_at ASC
LIMIT 50;
```

## Integración con Dramatiq

### Worker de Mercado

El scheduler encola tareas en la cola `market` de Dramatiq:

```python
# Encolar tarea
refresh_market_prices_task.send(product_id)
```

### Iniciar Worker de Mercado

```bash
# Worker standalone (solo cola market)
python -m dramatiq workers.market_scraping --queues market --processes 2 --threads 4

# O usar script existente
./scripts/start_worker_market.cmd
```

### Configuración de Workers

Para producción, ajustar concurrencia según recursos:

```bash
# Servidor pequeño (1-2 CPUs, 2-4GB RAM)
dramatiq workers.market_scraping --queues market --processes 1 --threads 2

# Servidor mediano (4 CPUs, 8GB RAM)
dramatiq workers.market_scraping --queues market --processes 2 --threads 4

# Servidor grande (8+ CPUs, 16GB+ RAM)
dramatiq workers.market_scraping --queues market --processes 4 --threads 8
```

## Uso

### Opción 1: APScheduler Integrado (Recomendado)

Habilitar en `.env`:
```bash
MARKET_SCHEDULER_ENABLED=true
```

El scheduler se iniciará automáticamente al arrancar la aplicación.

**Integración en `services/api.py`:**
```python
from services.jobs.market_scheduler import start_scheduler, stop_scheduler

@app.on_event("startup")
async def startup():
    # ... otros inits
    start_scheduler()  # Iniciar scheduler de mercado

@app.on_event("shutdown")
async def shutdown():
    # ... otros cleanups
    stop_scheduler()  # Detener scheduler
```

### Opción 2: Cron Separado (Linux/Unix)

Si prefieres gestión externa con cron del sistema:

1. Mantener `MARKET_SCHEDULER_ENABLED=false` en `.env`

2. Configurar crontab:
```bash
crontab -e
```

3. Agregar entrada:
```bash
# Actualización diaria a las 2 AM
0 2 * * * cd /app && /usr/bin/python scripts/run_market_update.py >> /var/log/market_cron.log 2>&1

# Cada 12 horas
0 */12 * * * cd /app && /usr/bin/python scripts/run_market_update.py >> /var/log/market_cron.log 2>&1

# Fines de semana (sábado 3 AM)
0 3 * * 6 cd /app && /usr/bin/python scripts/run_market_update.py --max-products 200 >> /var/log/market_cron.log 2>&1
```

### Opción 3: Windows Task Scheduler

1. Abrir "Programador de Tareas" (Task Scheduler)
2. Crear nueva tarea básica:
   - **Nombre:** Actualización Precios Mercado
   - **Desencadenador:** Diariamente a las 2:00 AM
   - **Acción:** Iniciar programa
     - **Programa:** `C:\Python311\python.exe`
     - **Argumentos:** `scripts\run_market_update.py`
     - **Iniciar en:** `C:\Proyectos\NiceGrow\Growen`

### Opción 4: Panel de Control Web (Recomendado)

Acceder a `http://localhost:5175/admin/scheduler` para:

- **Ver estado**: OFF / Running / Working
- **Toggle**: Activar/Desactivar scheduler con un switch
- **Configurar**: Hora de inicio (GMT-3) e intervalo (horas)
- **Ejecutar manualmente**: Forzar sincronización inmediata

La configuración se persiste y se aplica automáticamente al reiniciar el scheduler.

### Opción 5: Ejecución Manual desde API

```bash
# Trigger manual con configuración por defecto
curl -X POST http://localhost:8000/admin/scheduler/run-now \
  -H "Authorization: Bearer YOUR_TOKEN"

# Con parámetros personalizados
curl -X POST http://localhost:8000/admin/scheduler/run-now \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"max_products": 100, "days_threshold": 7}'

# Actualizar configuración
curl -X POST http://localhost:8000/admin/scheduler/config \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"start_hour": "03:00", "interval_hours": 12}'

# Alternar estado
curl -X POST http://localhost:8000/admin/scheduler/toggle \
  -H "Authorization: Bearer YOUR_TOKEN"
```

## Monitoreo y Logging

### Verificar Estado del Scheduler

**Desde API:**
```bash
curl http://localhost:8000/admin/scheduler/status \
  -H "Authorization: Bearer YOUR_TOKEN"
```

**Desde Panel Web:**
Acceder a `http://localhost:5175/admin/scheduler` - El estado se actualiza automáticamente cada 30 segundos.

**Desde script:**
```bash
python scripts/run_market_update.py --status-only
```

**Respuesta ejemplo:**
```json
{
  "running": true,
  "enabled": true,
  "working": false,
  "cron_schedule": "0 2 * * *",
  "start_hour": "02:00",
  "interval_hours": 24,
  "next_run_time": "2025-11-30T05:00:00Z",
  "update_frequency_days": 2,
  "max_products_per_run": 50,
  "prioritize_mandatory": true,
  "stats": {
    "total_products_with_sources": 350,
    "never_updated": 45,
    "outdated": 120,
    "pending_update": 165,
    "total_sources": 890
  }
}
```

**Estados del scheduler:**
- `OFF`: Scheduler detenido
- `Running`: Scheduler activo, esperando próxima ejecución
- `Working`: Scheduler ejecutando una tarea ahora mismo

### Logs del Scheduler

El scheduler emite logs detallados con prefijo `[MARKET SCHEDULER]`:

```
[MARKET SCHEDULER] Iniciando job de actualización automática de precios
[MARKET SCHEDULER] Productos seleccionados para actualización: 50
[MARKET SCHEDULER] Total de fuentes a scrapear: 150 (75 obligatorias)
[MARKET SCHEDULER] Tarea encolada: producto 123
[MARKET SCHEDULER] Job completado en 2.45s
[MARKET SCHEDULER] Resumen: 50 tareas encoladas, 0 fallos, 150 fuentes totales
```

### Logs de Workers

Los workers emiten logs con prefijo `[scraping]`:

```
[scraping] Iniciando actualización de precios para producto ID: 123
[scraping] Producto encontrado: 'Notebook Lenovo IdeaPad'
[scraping] Procesando 3 fuentes de mercado
[scraping] ✓ Fuente 1/3: Mercado Libre - Precio: $850000.00 ARS
[scraping] ✓ Actualización exitosa: 3/3 fuentes actualizadas
```

### Archivo de Log

Si usas cron, redirigir a archivo:

```bash
# Crear directorio de logs
mkdir -p /var/log/growen

# Cron con logging
0 2 * * * cd /app && python scripts/run_market_update.py >> /var/log/growen/market_cron.log 2>&1
```

Rotar logs con logrotate:

```bash
# /etc/logrotate.d/growen-market
/var/log/growen/market_cron.log {
    daily
    missingok
    rotate 30
    compress
    delaycompress
    notifempty
    copytruncate
}
```

## Métricas y Auditoría

### Campos de Auditoría en BD

**CanonicalProduct:**
- `market_price_updated_at`: Timestamp de última actualización exitosa
- `market_price_reference`: Precio promedio calculado

**MarketSource:**
- `last_checked_at`: Timestamp de último scraping (exitoso o fallido)
- `last_price`: Último precio obtenido

**MarketPriceHistory:**
- Registro histórico de todos los precios scrapeados

### Consultas SQL Útiles

**Productos nunca actualizados:**
```sql
SELECT cp.id, cp.name, COUNT(ms.id) as sources_count
FROM canonical_products cp
INNER JOIN market_sources ms ON cp.id = ms.product_id
WHERE cp.market_price_updated_at IS NULL
GROUP BY cp.id, cp.name
ORDER BY sources_count DESC;
```

**Productos desactualizados (>7 días):**
```sql
SELECT cp.id, cp.name, cp.market_price_updated_at,
       EXTRACT(day FROM NOW() - cp.market_price_updated_at) as days_old
FROM canonical_products cp
INNER JOIN market_sources ms ON cp.id = ms.product_id
WHERE cp.market_price_updated_at < (NOW() - INTERVAL '7 days')
GROUP BY cp.id, cp.name, cp.market_price_updated_at
ORDER BY days_old DESC;
```

**Historial de precios (últimos 30 días):**
```sql
SELECT p.name, ms.source_name, mph.price, mph.currency, mph.created_at
FROM market_price_history mph
INNER JOIN canonical_products p ON mph.product_id = p.id
INNER JOIN market_sources ms ON mph.source_id = ms.id
WHERE mph.created_at > (NOW() - INTERVAL '30 days')
ORDER BY mph.created_at DESC;
```

## Prevención de Sobrecarga

### Limitaciones Implementadas

1. **Límite de productos por ejecución:** `MAX_PRODUCTS_PER_RUN`
2. **Límite de browsers Playwright:** Semáforo de 3 instancias simultáneas (ver `workers/scraping/dynamic_scraper.py`)
3. **Timeout por producto:** 5 minutos (`time_limit=300000` en Dramatiq)
4. **Retries limitados:** Máximo 3 reintentos (`max_retries=3` en Dramatiq)
5. **Queue dedicada:** Cola `market` separada de `images` y `default`

### Recomendaciones Adicionales

1. **Rate limiting por dominio:**
   - Implementar delays entre requests al mismo sitio
   - Usar `time.sleep()` o `asyncio.sleep()` entre scraping de fuentes del mismo proveedor

2. **User-Agent rotation:**
   - Rotar User-Agents para evitar bloqueos
   - Implementado en `dynamic_scraper.py`

3. **Proxy rotation (futuro):**
   - Para volúmenes altos, usar pool de proxies
   - Integraciones: ScraperAPI, Bright Data, etc.

4. **Backoff exponencial:**
   - Dramatiq ya implementa backoff en retries
   - Configurar `max_backoff` si es necesario

5. **Monitoreo de errores:**
   - Alertar si tasa de fallos > 20%
   - Deshabilitar fuentes problemáticas temporalmente

## Deshabilitación Temporal

### Deshabilitar Scheduler

**Opción 1: Variable de entorno**
```bash
# En .env
MARKET_SCHEDULER_ENABLED=false
```

**Opción 2: Desde API**
```bash
curl -X POST http://localhost:8000/market/scheduler/disable \
  -H "Authorization: Bearer YOUR_TOKEN"
```

**Opción 3: Script Python**
```python
from services.jobs.market_scheduler import stop_scheduler
stop_scheduler()
```

### Deshabilitar Fuente Específica

Si una fuente causa problemas (timeouts, bloqueos, etc.):

```sql
-- Marcar fuente como no obligatoria temporalmente
UPDATE market_sources
SET is_mandatory = false
WHERE source_name = 'Sitio Problemático';

-- O eliminar temporalmente
DELETE FROM market_sources
WHERE source_name = 'Sitio Problemático';
```

## Troubleshooting

### Problema: Scheduler no ejecuta tareas

**Síntomas:** No hay logs de `[MARKET SCHEDULER]` en el horario esperado

**Solución:**
1. Verificar `MARKET_SCHEDULER_ENABLED=true` en `.env`
2. Comprobar que la aplicación se reinició tras cambiar `.env`
3. Verificar logs de startup: `start_scheduler()` debe aparecer
4. Validar cron expression con https://crontab.guru

### Problema: Workers no procesan tareas

**Síntomas:** Productos encolados pero sin scraping real

**Solución:**
1. Verificar que worker de mercado esté corriendo:
   ```bash
   ps aux | grep dramatiq
   ```
2. Iniciar worker si falta:
   ```bash
   python -m dramatiq workers.market_scraping --queues market
   ```
3. Verificar Redis (broker de Dramatiq) esté activo:
   ```bash
   redis-cli ping
   ```

### Problema: Demasiadas tareas pendientes

**Síntomas:** Cola de Dramatiq saturada, workers lentos

**Solución:**
1. Reducir `MAX_PRODUCTS_PER_RUN`
2. Aumentar workers concurrentes
3. Deshabilitar fuentes lentas temporalmente
4. Revisar timeout de scraping

### Problema: Scraping falla constantemente

**Síntomas:** Alta tasa de errores en logs de workers

**Solución:**
1. Verificar conectividad a sitios externos
2. Revisar si sitios cambiaron estructura HTML (selectores)
3. Validar que Playwright esté instalado correctamente:
   ```bash
   python -m playwright install
   ```
4. Verificar timeouts configurados

## Performance

### Estimación de Tiempos

Asumiendo:
- 50 productos por ejecución
- 3 fuentes promedio por producto
- 2-5 segundos por scraping
- 4 workers concurrentes

**Tiempo estimado por ejecución:** 5-10 minutos

### Optimización de Recursos

**Memoria:**
- Playwright browsers: ~150MB cada uno (máx 3 simultáneos = 450MB)
- Workers Dramatiq: ~100MB cada uno
- **Total recomendado:** 2GB RAM mínimo para workers

**CPU:**
- Scraping estático: bajo consumo
- Scraping dinámico (Playwright): medio-alto consumo
- **Recomendado:** 2-4 cores para 4 workers

**Red:**
- Bandwidth: ~1-5 Mbps para scraping normal
- Latencia: depende de sitios externos

## Próximos Pasos

### Mejoras Planificadas

1. **Dashboard de Monitoreo:**
   - Visualización de métricas en tiempo real
   - Gráficos de evolución de precios
   - Alertas de anomalías

2. **Machine Learning:**
   - Predicción de cambios de precio
   - Detección de outliers
   - Recomendaciones de ajuste de precios propios

3. **Integración con Notifications:**
   - Alertar cuando precio de mercado cae significativamente
   - Notificar productos con fuentes rotas

4. **API pública de precios:**
   - Endpoint para consultar historial
   - Webhook para cambios significativos

5. **Cache de resultados:**
   - Redis cache para precios recientes
   - Reducir hits a BD

## Referencias

- **APScheduler:** https://apscheduler.readthedocs.io/
- **Dramatiq:** https://dramatiq.io/
- **Cron expressions:** https://crontab.guru
- **Playwright:** https://playwright.dev/python/
- **Documentación relacionada:**
  - `docs/API_MARKET.md` - Endpoints de mercado
  - `docs/PERFORMANCE_TESTS.md` - Tests de performance
  - `workers/market_scraping.py` - Implementación del worker
  - `AGENTS.md` - Lineamientos generales del proyecto

---

**Última actualización:** 2025-11-12  
**Versión:** 1.0  
**Autor:** Sistema de Automatización Growen
