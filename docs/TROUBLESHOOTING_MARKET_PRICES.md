<!-- NG-HEADER: Nombre de archivo: TROUBLESHOOTING_MARKET_PRICES.md -->
<!-- NG-HEADER: Ubicación: docs/TROUBLESHOOTING_MARKET_PRICES.md -->
<!-- NG-HEADER: Descripción: Guía de troubleshooting para actualización de precios de mercado -->
<!-- NG-HEADER: Lineamientos: Ver AGENTS.md -->

# Troubleshooting: Actualización de Precios de Mercado

## Síntoma: "No se tomaron precios" después de refresh

### Caso Analizado (2025-11-19)

**Logs observados**:
```
16:23:34 | POST /market/products/23/refresh-market -> 202
16:23:37 | GET /market/products/23/sources -> 200
16:24:57 | POST /market/products/20/sources -> 201
16:25:00 | POST /market/products/20/refresh-market -> 202
16:25:03 | GET /market/products/20/sources -> 200
```

**Problema**: 
- Endpoint retorna `202 Accepted` (tarea encolada)
- No hay actualizaciones de precios después
- GET sources retorna mismos datos (sin nuevos precios)

### Diagnóstico

#### 1. Verificar Worker de Market Scraping

El sistema usa **Dramatiq** (task queue) para procesar scraping de forma asíncrona.

**Verificar si el worker está corriendo**:
```powershell
# Listar procesos Python
Get-Process python | ForEach-Object { 
    $cmd = (Get-CimInstance Win32_Process -Filter "ProcessId = $($_.Id)").CommandLine
    if ($cmd -like "*dramatiq*" -or $cmd -like "*market_scraping*") {
        Write-Host "Worker encontrado: PID $($_.Id)"
        Write-Host $cmd
    }
}
```

**Si no hay output**: ❌ El worker NO está corriendo (causa más común)

#### 2. Iniciar Worker Manualmente

**Opción 1: Worker dedicado de market**:
```powershell
cd C:\Proyectos\NiceGrow\Growen
.\scripts\start_worker_market.cmd
```

**Opción 2: Worker unificado (market + images)**:
```powershell
.\scripts\start_worker_all.cmd
```

**Verificar inicio exitoso**:
```powershell
# Ver logs
Get-Content .\logs\worker_market.log -Tail 20 -Wait

# Deberías ver:
# [dramatiq] Broker: <RedisBroker ...>
# [dramatiq] Registered middleware: ...
# [dramatiq] Discovered tasks: refresh_market_prices_task
# [dramatiq] Worker started
```

#### 3. Verificar Redis (Message Broker)

Dramatiq necesita Redis para la cola de mensajes.

**Verificar contenedor**:
```powershell
docker ps --filter "name=redis"
```

**Debe mostrar**:
```
CONTAINER ID   NAMES          STATUS         PORTS
xxx            growen-redis   Up XX minutes  0.0.0.0:6379->6379/tcp
```

**Si no está corriendo**:
```powershell
docker compose up -d redis
```

**Verificar conectividad**:
```powershell
# Desde PowerShell con redis-cli (si tienes instalado)
redis-cli -h localhost -p 6379 ping
# Respuesta esperada: PONG

# O con Docker
docker exec growen-redis redis-cli ping
# Respuesta esperada: PONG
```

#### 4. Verificar Cola de Mensajes

**Ver mensajes pendientes en la cola**:
```powershell
docker exec growen-redis redis-cli LLEN dramatiq:market.DQ
```

**Si hay números > 0**: Hay tareas encoladas esperando ser procesadas

**Limpiar cola si es necesario** (⚠️ CUIDADO: elimina tareas pendientes):
```powershell
docker exec growen-redis redis-cli DEL dramatiq:market.DQ
```

#### 5. Verificar Configuración de Entorno

**Archivo `.env` debe tener**:
```bash
REDIS_URL=redis://localhost:6379/0
```

**Verificar desde código**:
```powershell
python -c "import os; from agent_core.config import settings; print('REDIS_URL:', os.getenv('REDIS_URL') or 'redis://localhost:6379/0')"
```

### Flujo Completo de Actualización

1. **Usuario hace clic en "Actualizar precios"**
   - Frontend: `POST /market/products/{id}/refresh-market`

2. **API encola tarea**:
   - Verifica que producto exista
   - Importa `refresh_market_prices_task` de `workers.market_scraping`
   - Envía mensaje a cola Redis con `.send(product_id)`
   - Retorna `202 Accepted` con `job_id`

3. **Worker procesa tarea** (si está corriendo):
   - Lee mensaje de cola Redis
   - Obtiene fuentes del producto desde DB
   - Para cada fuente:
     - Ejecuta scraping (static o dynamic según `source_type`)
     - Extrae precio y moneda
     - Actualiza `MarketSource` en DB
   - Actualiza `last_checked_at` en todas las fuentes

4. **Frontend refresca datos**:
   - Polling cada 3s: `GET /market/products/{id}/sources`
   - Muestra nuevos precios cuando estén disponibles

### Checklist de Resolución

- [ ] Redis está corriendo (`docker ps | grep redis`)
- [ ] Worker de market está corriendo (ver logs en `logs/worker_market.log`)
- [ ] Variable `REDIS_URL` configurada correctamente en `.env`
- [ ] No hay errores en logs de worker (`Get-Content logs\worker_market.log -Tail 50`)
- [ ] Fuentes tienen URLs válidas (`SELECT url FROM market_sources WHERE product_id = X`)
- [ ] Playwright instalado si hay fuentes `source_type='dynamic'` (`playwright install chromium`)

### Comandos de Diagnóstico Rápido

**Script PowerShell para diagnóstico completo**:
```powershell
# Guardar como diagnose_market.ps1
Write-Host "=== Diagnóstico de Market Scraping ===" -ForegroundColor Cyan

# 1. Redis
Write-Host "`n[1/5] Verificando Redis..." -ForegroundColor Yellow
docker ps --filter "name=redis" --format "{{.Names}}: {{.Status}}"

# 2. Worker
Write-Host "`n[2/5] Verificando Worker..." -ForegroundColor Yellow
$workerProcess = Get-Process python -ErrorAction SilentlyContinue | Where-Object {
    (Get-CimInstance Win32_Process -Filter "ProcessId = $($_.Id)").CommandLine -like "*market_scraping*"
}
if ($workerProcess) {
    Write-Host "Worker CORRIENDO (PID: $($workerProcess.Id))" -ForegroundColor Green
} else {
    Write-Host "Worker NO ENCONTRADO" -ForegroundColor Red
}

# 3. Cola Redis
Write-Host "`n[3/5] Verificando cola de mensajes..." -ForegroundColor Yellow
docker exec growen-redis redis-cli LLEN dramatiq:market.DQ

# 4. Logs recientes
Write-Host "`n[4/5] Últimos logs del worker..." -ForegroundColor Yellow
if (Test-Path "logs\worker_market.log") {
    Get-Content "logs\worker_market.log" -Tail 5
} else {
    Write-Host "No hay logs de worker" -ForegroundColor Red
}

# 5. Variable REDIS_URL
Write-Host "`n[5/5] Verificando REDIS_URL..." -ForegroundColor Yellow
python -c "import os; print(os.getenv('REDIS_URL', 'NO CONFIGURADA'))"
```

**Ejecutar**:
```powershell
.\diagnose_market.ps1
```

### Solución Rápida (Caso Común)

**Si el worker NO está corriendo**:

1. Abrir nueva terminal PowerShell
2. Ejecutar:
   ```powershell
   cd C:\Proyectos\NiceGrow\Growen
   .\scripts\start_worker_market.cmd
   ```
3. Dejar la terminal abierta (el worker corre en foreground)
4. Volver al navegador y hacer clic en "Actualizar precios"
5. Esperar 5-10 segundos
6. Los precios deberían aparecer

**Notas**:
- El worker procesa tareas en background pero el proceso corre en foreground
- Si cierras la terminal, el worker se detiene
- Para producción, usar `systemd` (Linux) o Windows Service

### Integración con start.bat

El script `start.bat` **NO inicia workers automáticamente** (por diseño).

**Razón**: Workers consumen recursos y no siempre son necesarios en desarrollo local.

**Para iniciar worker automáticamente**, modificar `start.bat`:
```batch
REM Después de iniciar API y antes de iniciar frontend
start "Worker Market" cmd /k "%ROOT%scripts\start_worker_market.cmd"
```

**O mejor**: Crear `start_with_workers.bat`:
```batch
@echo off
call start.bat
timeout /t 5 /nobreak >nul
start "Worker Market" cmd /k "%~dp0scripts\start_worker_market.cmd"
```

### Logs Importantes

**Ubicación**:
- Worker market: `logs/worker_market.log`
- API backend: `logs/backend.log`
- Worker images: `logs/worker_images.log`

**Qué buscar en `worker_market.log`**:
```
✓ Precio extraído exitosamente de fuente 'XXX': 1234.56 ARS
⚠ Precio no encontrado en la página - fuente 'YYY'
✗ Error de red: timeout - fuente 'ZZZ'
```

**Errores comunes**:
- `Connection refused`: Redis no está corriendo
- `ImportError: cannot import name 'refresh_market_prices_task'`: Código desactualizado
- `TimeoutError`: Sitio web muy lento o no responde
- `PriceNotFoundError`: Selectores CSS desactualizados (sitio cambió estructura)

### Desarrollo vs Producción

**Desarrollo Local** (recomendado):
- API local con hot reload
- Redis en Docker
- Worker manual (iniciar solo cuando necesites scraping)

**Producción** (Docker):
- Todo en containers
- Workers inician automáticamente con `docker-compose up -d`
- Healthchecks y restart policies configurados

Ver `docs/DEVELOPMENT_WORKFLOW.md` para más detalles.

### Preguntas Frecuentes

**P: ¿Por qué 202 Accepted y no 200 OK?**
R: Porque el scraping es asíncrono. La API solo encola la tarea, no espera el resultado.

**P: ¿Cuánto demora el scraping?**
R: Depende:
- 1 fuente estática: ~2-5 segundos
- 1 fuente dinámica (Playwright): ~10-15 segundos
- 10 fuentes: ~30-60 segundos (procesamiento paralelo limitado)

**P: ¿Cómo sé si terminó?**
R: El frontend hace polling cada 3s. Cuando veas `last_checked_at` actualizado, terminó.

**P: ¿Puedo forzar scraping inmediato sin worker?**
R: Sí, para testing:
```python
import asyncio
from workers.market_scraping import refresh_market_prices_task_impl

# Ejecutar directamente (sync)
asyncio.run(refresh_market_prices_task_impl(product_id=123))
```

**P: ¿Qué pasa si el worker se cae mientras procesa?**
R: Dramatiq reintenta automáticamente (max_retries=3). Si falla 3 veces, la tarea se mueve a DLQ (dead letter queue).

### Mejoras Futuras

- [ ] Dashboard de monitoreo de workers (Flower o similar)
- [ ] Notificaciones cuando scraping falla
- [ ] Healthcheck endpoint `/market/worker-status`
- [ ] Auto-restart de worker en desarrollo (watchdog)
- [ ] Rate limiting por dominio (evitar bloqueos)

---

Actualizado: 2025-11-19
