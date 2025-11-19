# Diagnóstico de Conectividad MCP Web Search

## Problema

Error `network_failure` en la función `call_mcp_web_search` del módulo `workers/discovery/source_finder.py`:

```python
except httpx.RequestError as e:
    logger.error(f"[discovery] Error de red llamando MCP Web Search: {e}")
    return {"error": "network_failure"}
```

El backend intenta conectar a `http://mcp_web_search:8002` pero falla con `httpx.RequestError`.

## Arquitectura

```
┌─────────────────┐         HTTP (red Docker)        ┌──────────────────────┐
│  Backend API    │ ─────────────────────────────────▶│  MCP Web Search      │
│  (growen-api)   │   http://mcp_web_search:8002     │  (growen-mcp-web-    │
│                 │                                   │   search)            │
│  Puerto: 8000   │                                   │  Puerto interno: 8002│
└─────────────────┘                                   │  Puerto host: 8102   │
                                                      └──────────────────────┘
```

## Configuración Actual (docker-compose.yml)

```yaml
mcp_web_search:
  build:
    context: .
    dockerfile: mcp_servers/web_search_server/Dockerfile
  container_name: growen-mcp-web-search
  depends_on:
    - api
  environment:
    LOG_LEVEL: info
  ports:
    - "8102:8002"  # Puerto host:contenedor
  restart: unless-stopped
```

**Nota importante**: 
- **Desde el host**: `http://localhost:8102`
- **Desde Docker (red interna)**: `http://mcp_web_search:8002`

## Scripts de Diagnóstico

Se han creado dos scripts para diagnosticar el problema:

### 1. Script Python (multiplataforma)

**Ubicación**: `scripts/diagnose_mcp_connection.py`

**Uso**:

```bash
# Desde el host (requiere Python + httpx)
python scripts/diagnose_mcp_connection.py

# Desde dentro del contenedor backend
docker exec -it growen-api-1 python scripts/diagnose_mcp_connection.py
```

**Tests que ejecuta**:
1. ✅ **Resolución DNS**: Verifica que `mcp_web_search` resuelva a una IP
2. ✅ **Conexión TCP**: Verifica que el puerto 8002 esté escuchando
3. ✅ **Endpoint `/health`**: Verifica que el servicio responda
4. ✅ **Endpoint `/invoke_tool`**: Prueba una búsqueda web de ejemplo

### 2. Script PowerShell (Windows)

**Ubicación**: `scripts/diagnose_mcp.ps1`

**Uso**:

```powershell
# Ejecuta en ambos contextos (host + docker)
.\scripts\diagnose_mcp.ps1

# Solo desde el host
.\scripts\diagnose_mcp.ps1 -Mode host

# Solo desde Docker
.\scripts\diagnose_mcp.ps1 -Mode docker
```

## Verificación Manual

### 1. Verificar que el contenedor esté corriendo

```bash
docker ps --filter name=mcp_web_search
```

**Salida esperada**:
```
CONTAINER ID   IMAGE                    STATUS         PORTS
abc123def456   growen/mcp-web-search   Up 5 minutes   0.0.0.0:8102->8002/tcp
```

### 2. Verificar logs del servicio

```bash
docker logs growen-mcp-web-search --tail 50
```

**Salida esperada** (servidor iniciado):
```
INFO:     Started server process [1]
INFO:     Waiting for application startup.
INFO:     Application startup complete.
INFO:     Uvicorn running on http://0.0.0.0:8002 (Press CTRL+C to quit)
```

### 3. Probar endpoint desde el HOST

```powershell
# Windows PowerShell
Invoke-WebRequest http://localhost:8102/health

# Linux/Mac
curl http://localhost:8102/health
```

**Respuesta esperada**:
```json
{"status": "ok"}
```

### 4. Probar endpoint desde DENTRO del contenedor backend

```bash
docker exec -it growen-api-1 sh -c "curl http://mcp_web_search:8002/health"
```

**Respuesta esperada**:
```json
{"status": "ok"}
```

## Solución de Problemas

### Error: "Contenedor no está corriendo"

```bash
# Iniciar el servicio
docker-compose up -d mcp_web_search

# Verificar logs
docker logs growen-mcp-web-search
```

### Error: "DNS resolution failed"

**Causas comunes**:
- Los contenedores no están en la misma red Docker
- El nombre del servicio está mal escrito

**Solución**:
```bash
# Verificar red Docker
docker network inspect growen_default

# Verificar que ambos contenedores estén en la misma red
docker inspect growen-api-1 | grep NetworkMode
docker inspect growen-mcp-web-search | grep NetworkMode
```

### Error: "Connection refused"

**Causas comunes**:
- El servicio no está escuchando en el puerto 8002
- El Dockerfile no tiene `EXPOSE 8002`
- El comando CMD no inició uvicorn correctamente

**Solución**:
```bash
# Verificar que uvicorn esté corriendo dentro del contenedor
docker exec -it growen-mcp-web-search ps aux | grep uvicorn

# Verificar puerto EXPOSE en Dockerfile
cat mcp_servers/web_search_server/Dockerfile | grep EXPOSE
```

### Error: "Timeout"

**Causas comunes**:
- El servicio tarda mucho en iniciar
- Problemas de red Docker

**Solución**:
```bash
# Incrementar timeout en httpx
# Editar workers/discovery/source_finder.py línea ~258
async with httpx.AsyncClient(timeout=30.0) as client:  # Aumentar de 10.0 a 30.0
```

## Configuración de Variables de Entorno

### En docker-compose.yml (servicio `api`):

```yaml
api:
  environment:
    MCP_WEB_SEARCH_URL: "http://mcp_web_search:8002/invoke_tool"
    AI_USE_WEB_SEARCH: "1"
```

### En .env (desarrollo local):

```bash
# Si ejecutas la API fuera de Docker
MCP_WEB_SEARCH_URL=http://localhost:8102/invoke_tool
AI_USE_WEB_SEARCH=1
```

## Checklist de Verificación

- [ ] El contenedor `growen-mcp-web-search` está corriendo
- [ ] El contenedor escucha en el puerto 8002 interno
- [ ] El puerto 8102 está mapeado correctamente al host
- [ ] Ambos contenedores están en la misma red Docker
- [ ] El endpoint `/health` responde desde el host (`localhost:8102`)
- [ ] El endpoint `/health` responde desde el contenedor API (`mcp_web_search:8002`)
- [ ] Los logs del MCP no muestran errores de inicio
- [ ] La variable `MCP_WEB_SEARCH_URL` está configurada correctamente

## Comandos Útiles

```bash
# Ver estado de todos los servicios
docker-compose ps

# Reiniciar solo MCP Web Search
docker-compose restart mcp_web_search

# Reconstruir imagen (si cambiaste Dockerfile)
docker-compose build mcp_web_search
docker-compose up -d mcp_web_search

# Ver logs en tiempo real
docker logs growen-mcp-web-search -f

# Entrar al contenedor para debug
docker exec -it growen-mcp-web-search sh

# Inspeccionar red Docker
docker network inspect growen_default

# Ver variables de entorno del contenedor
docker exec growen-mcp-web-search env | grep MCP
```

## Próximos Pasos

1. **Ejecutar diagnóstico completo**:
   ```powershell
   .\scripts\diagnose_mcp.ps1
   ```

2. **Revisar output del diagnóstico** y seguir las recomendaciones

3. **Si todos los tests pasan** pero el error persiste:
   - Verificar que el backend esté usando la URL correcta
   - Revisar logs del backend: `docker logs growen-api-1 | grep "MCP Web Search"`

4. **Si algún test falla**:
   - Seguir las soluciones específicas en la sección "Solución de Problemas"
   - Ejecutar los comandos de debug sugeridos

## Contacto de Soporte

Si el problema persiste después de seguir esta guía:

1. Ejecuta el diagnóstico completo y guarda la salida
2. Recopila logs de ambos servicios:
   ```bash
   docker logs growen-api-1 > api.log
   docker logs growen-mcp-web-search > mcp.log
   ```
3. Incluye la salida de `docker-compose ps` y `docker network inspect growen_default`
