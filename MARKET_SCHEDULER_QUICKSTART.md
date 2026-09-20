<!-- NG-HEADER: Nombre de archivo: MARKET_SCHEDULER_QUICKSTART.md -->
<!-- NG-HEADER: Ubicación: MARKET_SCHEDULER_QUICKSTART.md -->
<!-- NG-HEADER: Descripción: Guía rápida del scheduler de precios de mercado. -->
<!-- NG-HEADER: Lineamientos: Ver AGENTS.md -->

# Scheduler de Precios de Mercado - Guía Rápida

## Instalación

### 1. Instalar Dependencias

```bash
pip install apscheduler
```

O reinstalar todo:
```bash
pip install -r requirements.txt
```

### 2. Configurar Variables de Entorno

Copiar ejemplo y configurar:
```bash
cp .env.market_scheduler.example .env
```

Editar `.env` y agregar:
```bash
MARKET_SCHEDULER_ENABLED=true
MARKET_UPDATE_FREQUENCY_DAYS=2
MARKET_MAX_PRODUCTS_PER_RUN=50
MARKET_PRIORITIZE_MANDATORY=true
MARKET_CRON_SCHEDULE="0 2 * * *"
```

### 3. Integrar Scheduler en API

Editar `services/api.py`:

```python
from services.jobs.market_scheduler import start_scheduler, stop_scheduler

@app.on_event("startup")
async def startup():
    # ... otros inits
    start_scheduler()  # ← AGREGAR ESTO

@app.on_event("shutdown")
async def shutdown():
    # ... otros cleanups
    stop_scheduler()  # ← AGREGAR ESTO
```

### 4. Registrar Router (Opcional)

Para endpoints de control, editar `services/api.py`:

```python
from services.routers import market_scheduler

app.include_router(market_scheduler.router)
```

### 5. Iniciar Worker de Mercado

```bash
# En terminal separada
python -m dramatiq workers.market_scraping --queues market --processes 2 --threads 4
```

O usar script existente:
```bash
./scripts/start_worker_market.cmd
```

## Uso

### Opción 1: Scheduler Automático (APScheduler)

Ya está configurado si `MARKET_SCHEDULER_ENABLED=true` y la API está corriendo.

Verificar en logs al iniciar API:
```
[MARKET SCHEDULER] Scheduler iniciado correctamente
[MARKET SCHEDULER] Próxima ejecución: 2025-11-13 02:00:00
```

### Opción 2: Ejecución Manual con Script Python

```bash
# Ejecución estándar
python scripts/run_market_update.py

# Con parámetros personalizados
python scripts/run_market_update.py --max-products 100 --days-threshold 7

# Solo verificar estado
python scripts/run_market_update.py --status-only
```

### Opción 3: Ejecución Manual con PowerShell (Windows)

```powershell
# Ejecución estándar
.\scripts\run_market_update.ps1

# Con parámetros
.\scripts\run_market_update.ps1 -MaxProducts 100 -DaysThreshold 7

# Solo estado
.\scripts\run_market_update.ps1 -StatusOnly
```

### Opción 4: Cron (Linux/Unix)

```bash
# Editar crontab
crontab -e

# Agregar línea (diariamente a las 2 AM)
0 2 * * * cd /app && python scripts/run_market_update.py >> /var/log/market_cron.log 2>&1
```

### Opción 5: API Endpoints

```bash
# Ver estado
curl http://localhost:8000/market/scheduler/status

# Ejecutar manualmente
curl -X POST http://localhost:8000/market/scheduler/trigger

# Habilitar scheduler
curl -X POST http://localhost:8000/market/scheduler/enable

# Deshabilitar scheduler
curl -X POST http://localhost:8000/market/scheduler/disable
```

## Verificación

### 1. Verificar Estado del Scheduler

```bash
python scripts/run_market_update.py --status-only
```

Salida esperada:
```
📊 ESTADO DEL SCHEDULER:
  • Habilitado: True
  • Cron: 0 2 * * *
  • Frecuencia: cada 2 días
  • Máx productos/ejecución: 50
  • Priorizar obligatorios: True

📈 ESTADÍSTICAS:
  • Total productos con fuentes: 350
  • Nunca actualizados: 45
  • Desactualizados: 120
  • Pendientes actualización: 165
  • Total fuentes: 890
```

### 2. Verificar Logs

```bash
# Ver logs de API (scheduler)
tail -f logs/backend.log | grep "MARKET SCHEDULER"

# Ver logs de workers (scraping)
tail -f logs/worker_market.log | grep "scraping"
```

### 3. Probar Actualización Manual

```bash
# Ejecutar con pocos productos para testing
python scripts/run_market_update.py --max-products 5
```

## Configuraciones Recomendadas

### Desarrollo
```bash
MARKET_SCHEDULER_ENABLED=false  # Manual
MARKET_UPDATE_FREQUENCY_DAYS=1
MARKET_MAX_PRODUCTS_PER_RUN=10
```

### Producción Ligera
```bash
MARKET_SCHEDULER_ENABLED=true
MARKET_UPDATE_FREQUENCY_DAYS=2
MARKET_MAX_PRODUCTS_PER_RUN=50
MARKET_CRON_SCHEDULE="0 2 * * *"  # 2 AM diario
```

### Producción Intensiva
```bash
MARKET_SCHEDULER_ENABLED=true
MARKET_UPDATE_FREQUENCY_DAYS=1
MARKET_MAX_PRODUCTS_PER_RUN=100
MARKET_CRON_SCHEDULE="0 */8 * * *"  # Cada 8 horas
```

## Troubleshooting

### Scheduler no ejecuta tareas

1. Verificar `MARKET_SCHEDULER_ENABLED=true`
2. Reiniciar API tras cambiar `.env`
3. Verificar logs de startup
4. Validar cron expression en https://crontab.guru

### Workers no procesan tareas

1. Verificar worker corriendo: `ps aux | grep dramatiq`
2. Iniciar worker: `python -m dramatiq workers.market_scraping --queues market`
3. Verificar Redis: `redis-cli ping`

### Alta tasa de errores

1. Verificar conectividad a sitios externos
2. Revisar selectores HTML en fuentes
3. Validar instalación de Playwright: `python -m playwright install`
4. Revisar logs detallados de workers

## Documentación Completa

Ver `docs/MARKET_SCHEDULER.md` para:
- Arquitectura detallada
- Configuración avanzada
- Monitoreo y métricas
- Prevención de sobrecarga
- Consultas SQL útiles
- Performance tuning

## Archivos Relacionados

- `services/jobs/market_scheduler.py` - Lógica del scheduler
- `services/routers/market_scheduler.py` - API endpoints
- `scripts/run_market_update.py` - Script Python standalone
- `scripts/run_market_update.ps1` - Script PowerShell (Windows)
- `workers/market_scraping.py` - Worker de scraping
- `docs/MARKET_SCHEDULER.md` - Documentación completa
