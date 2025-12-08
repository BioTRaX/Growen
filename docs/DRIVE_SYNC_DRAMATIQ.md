<!-- NG-HEADER: Nombre de archivo: DRIVE_SYNC_DRAMATIQ.md -->
<!-- NG-HEADER: Ubicación: docs/DRIVE_SYNC_DRAMATIQ.md -->
<!-- NG-HEADER: Descripción: Documentación técnica de sincronización Drive con Dramatiq y Redis Pub/Sub. -->
<!-- NG-HEADER: Lineamientos: Ver AGENTS.md -->

# Sincronización Drive con Dramatiq y Redis Pub/Sub

Este documento describe la arquitectura y funcionamiento de la sincronización de imágenes desde Google Drive usando Dramatiq para procesamiento asíncrono y Redis Pub/Sub para progreso en tiempo real.

## Arquitectura

### Flujo de Ejecución

```
Frontend → API Endpoint → Dramatiq Queue → Worker Dramatiq
                                              ↓
                                         Redis Pub/Sub
                                              ↓
                                         API Subscribe
                                              ↓
                                         WebSocket
                                              ↓
                                          Frontend
```

### Componentes

1. **API Endpoint** (`services/routers/drive_sync.py`):
   - Recibe solicitud de inicio de sincronización
   - Encola tarea en Dramatiq (`sync_drive_images_task.send()`)
   - Inicia suscripción a Redis Pub/Sub para recibir progreso
   - Reenvía progreso vía WebSocket al frontend

2. **Worker Dramatiq** (`services/jobs/drive_sync.py`):
   - Actor Dramatiq en cola `drive_sync`
   - Ejecuta `sync_drive_images()` con callback Redis
   - Publica progreso a canal `drive_sync:progress`

3. **Worker de Sincronización** (`workers/drive_sync.py`):
   - Lógica de negocio: listar archivos, validar SKU, procesar imágenes
   - Usa callback para reportar progreso (publica a Redis)

4. **Redis Pub/Sub**:
   - Canal: `drive_sync:progress`
   - Formato mensaje: `{"sync_id": "...", "status": "...", "current": N, "total": M, ...}`

## Configuración

### Variables de Entorno Requeridas

```env
# Google Drive
GOOGLE_APPLICATION_CREDENTIALS=./certs/growen-drive.json
DRIVE_SOURCE_FOLDER_ID=tu_folder_id
DRIVE_PROCESSED_FOLDER_NAME=Procesados
DRIVE_SIN_SKU_FOLDER_NAME=SIN_SKU
DRIVE_ERRORS_FOLDER_NAME=Errores_SKU

# Redis (para Dramatiq y Pub/Sub)
REDIS_URL=redis://localhost:6379/0
```

### Dependencias

- `dramatiq[redis]>=1.15.0`: Framework de tareas asíncronas
- `redis`: Cliente Redis (síncrono o async según versión)
- `google-api-python-client>=2.0.0`: API de Google Drive
- `google-auth>=2.0.0`: Autenticación Google

## Iniciar Worker

### Opción 1: Worker Local (Desarrollo)

```bash
# Worker específico de drive_sync
scripts\start_worker_drive_sync.cmd

# O worker unificado (todas las colas)
scripts\start_worker_all.cmd drive_sync
scripts\start_worker_all.cmd all  # Incluye images, market y drive_sync
```

**Logs:** `logs/worker_drive_sync.log`

### Opción 2: Docker (Producción)

**Nota:** Redis se gestiona exclusivamente a través de `docker-compose.yml`. Los scripts (`start.bat`, `start_stack.ps1`) migran automáticamente contenedores Redis creados manualmente a docker-compose.

```bash
# Iniciar Redis (requerido para Dramatiq)
docker compose up -d redis

# Iniciar servicio dramatiq
docker compose up -d dramatiq

# Ver logs
docker logs -f growen-dramatiq
```

**Requisitos:**
- Servicio `redis` corriendo (incluido en docker-compose)
- Servicio `db` corriendo
- Variables de entorno configuradas en `.env`

## Monitoreo

### Ver Estado de Cola

```bash
# Ver estado de Dramatiq (requiere endpoint /health/dramatiq)
curl http://localhost:8000/health/dramatiq

# Ver cola directamente en Redis
docker exec growen-redis redis-cli LLEN "dramatiq:drive_sync.DQ"
```

### Logs

**Worker Local:**
- `logs/worker_drive_sync.log`: Logs del worker específico
- `logs/worker_all.log`: Logs del worker unificado (modo `all`)

**Worker Docker:**
```bash
docker logs growen-dramatiq
docker logs -f growen-dramatiq  # Seguir logs en tiempo real
```

### Verificar Progreso en Redis

```bash
# Suscribirse al canal de progreso (para debugging)
docker exec -it growen-redis redis-cli
> SUBSCRIBE drive_sync:progress
```

## Troubleshooting

### Error: "Worker no procesa tareas"

**Causas posibles:**
1. Worker no está corriendo
2. Redis no está disponible
3. Cola incorrecta

**Solución:**
```bash
# Verificar worker
Get-Process | Where-Object {$_.CommandLine -like "*dramatiq*drive_sync*"}

# Verificar Redis
docker ps | findstr redis
# O
redis-cli ping

# Verificar cola
docker exec growen-redis redis-cli LLEN "dramatiq:drive_sync.DQ"
```

### Error: "No se recibe progreso en frontend"

**Causas posibles:**
1. Suscripción Redis no iniciada
2. WebSocket desconectado
3. Mensajes no se publican a Redis

**Solución:**
1. Verificar logs de API: buscar "Suscripción Redis iniciada"
2. Verificar conexión WebSocket en consola del navegador
3. Verificar publicación en Redis: `redis-cli MONITOR` o suscribirse al canal

### Error: "GOOGLE_APPLICATION_CREDENTIALS no está definido"

**Solución:**
1. Verificar variable en `.env`
2. En Docker: verificar que volumen `./certs:/app/certs:ro` esté montado
3. Verificar que archivo exista: `ls certs/growen-drive.json`

### Error: "Error en suscripción Redis"

**Causas:**
1. Redis no disponible
2. `redis.asyncio` no instalado (fallback a polling)

**Solución:**
```bash
# Verificar Redis
docker ps | findstr redis
redis-cli ping

# Instalar redis async (si falta)
pip install redis[async]
```

## Arquitectura de Progreso

### Mensajes de Progreso

Formato estándar publicado a Redis:

```json
{
  "sync_id": "uuid-único",
  "status": "processing|completed|error",
  "current": 5,
  "total": 20,
  "remaining": 15,
  "sku": "ABC_1234_XYZ",
  "filename": "ABC_1234_XYZ 1.jpg",
  "message": "Procesando SKU ABC_1234_XYZ (5/20, faltan 15)",
  "error": "",
  "stats": {
    "processed": 3,
    "errors": 1,
    "no_sku": 1
  }
}
```

### Flujo de Suscripción

1. **Inicio:** Endpoint encola tarea y crea `sync_id`
2. **Suscripción:** API se suscribe a `drive_sync:progress` filtrando por `sync_id`
3. **Publicación:** Worker publica progreso con `sync_id`
4. **Filtrado:** API filtra mensajes por `sync_id` y reenvía vía WebSocket
5. **Finalización:** Cuando `status=completed|error`, suscripción se cierra

## Ventajas de Dramatiq

1. **Robustez:** Tareas persisten en Redis, no se pierden si API se reinicia
2. **Escalabilidad:** Múltiples workers pueden procesar la misma cola
3. **Monitoreo:** Estado de colas visible en Redis
4. **Reintentos:** Configurables por actor (`max_retries`)
5. **Timeout:** Límite de tiempo por tarea (`time_limit`)

## Comparación con Ejecución Directa

| Aspecto | Directa (`asyncio.create_task`) | Dramatiq |
|---------|--------------------------------|----------|
| Persistencia | ❌ Se pierde si API reinicia | ✅ Persiste en Redis |
| Escalabilidad | ❌ Un solo proceso | ✅ Múltiples workers |
| Monitoreo | ⚠️ Solo logs | ✅ Estado en Redis |
| Robustez | ⚠️ Depende de API | ✅ Independiente |
| Complejidad | ✅ Simple | ⚠️ Requiere Redis |

## Referencias

- `docs/GOOGLE_DRIVE_SETUP.md`: Configuración inicial de Google Drive
- `docs/GOOGLE_DRIVE_SYNC.md`: Documentación general de sincronización
- `services/jobs/drive_sync.py`: Implementación del actor Dramatiq
- `workers/drive_sync.py`: Lógica de sincronización
- `services/routers/drive_sync.py`: Endpoints API y WebSocket

