<!-- NG-HEADER: Nombre de archivo: DEVELOPMENT_WORKFLOW.md -->
<!-- NG-HEADER: Ubicación: docs/DEVELOPMENT_WORKFLOW.md -->
<!-- NG-HEADER: Descripción: Flujo de trabajo recomendado para desarrollo local vs Docker -->
<!-- NG-HEADER: Lineamientos: Ver AGENTS.md -->

# Flujo de Trabajo: Desarrollo Local → Docker Producción

Guía para optimizar el ciclo de desarrollo usando servicios locales y reservar Docker para testing de integración y producción.

## Filosofía

**Desarrollo**: Local, rápido, debuggeable
**Testing Integración**: Docker Compose (replica producción)
**Producción**: Docker (idéntico a testing)

## Setup Inicial

### 1. Levantar Infraestructura en Docker (primer inicio)

```powershell
# Paso 1: MCP servers (si vas a usar herramientas IA)
docker compose up -d mcp_products mcp_web_search

# Paso 2: Base de datos
docker compose up -d db

# Alternativa en un solo comando
# docker compose up -d db mcp_products mcp_web_search
```

**Puertos expuestos**:
- PostgreSQL: `5433` (mapeado para evitar colisión con Postgres local si existe)
- Redis: `6379` cuando se inicia para workers locales
- MCP Products: `8100`
- MCP Web Search: `8102`

PostgreSQL y Redis participan de dos redes Compose: `backend`, interna para el tráfico entre contenedores, y `host_access`, usada exclusivamente para conservar los bindings loopback requeridos por la API y los workers locales. No quitar `host_access` mientras el desarrollo use `127.0.0.1:5433` o `127.0.0.1:6379`: Docker Engine no publica puertos de un contenedor conectado únicamente a una red `internal`.

### 2. Configurar Entorno Local

**Archivo `.env` (raíz del proyecto)**:
```bash
# Base de datos (apunta a Docker)
DB_HOST=localhost
DB_PORT=5433  # Puerto mapeado de Docker
DB_USER=growen
DB_PASS=tu_password_aqui
DB_NAME=growen

# O usar DB_URL completa
# DB_URL=postgresql+psycopg://<usuario>:<password>@localhost:5433/growen

# Servicios externos (si usas Docker)
MCP_PRODUCTS_URL=http://localhost:8100/mcp
MCP_WEB_SEARCH_URL=http://localhost:8102/mcp
AI_USE_WEB_SEARCH=1

# Scheduler (deshabilitado en dev local)
MARKET_SCHEDULER_ENABLED=false

# Workers Dramatiq (manual en dev)
REDIS_URL=redis://localhost:6379/0

# Logging
DEBUG_SQL=0  # Cambia a 1 para ver queries SQL
```

### 3. Crear o reparar el entorno Python 3.14.6+

```powershell
.\scripts\bootstrap-dev.ps1

# Si existe una venv rota o de otra versión
.\scripts\bootstrap-dev.ps1 -RecreateVenv
```

### 4. Levantar Backend + Frontend

**Opción recomendada (automática):**

```powershell
.\scripts\start-dev.ps1

# Incluye Redis + Dramatiq para altas canónicas masivas
.\scripts\start-dev.ps1 -WithCatalogWorker

# Incluye Redis + worker Mercado Docker con Chromium
.\scripts\start-dev.ps1 -WithMarketWorker
```

`start-dev.ps1` orquesta validaciones, migraciones y arranque local de API, MCP Products y Vue. Con `-WithCatalogWorker` levanta Redis y Dramatiq. Con `-WithMarketWorker` inicia Redis y compila/levanta el contenedor dedicado `market_worker` sin recrear PostgreSQL; verifica consumidor y health antes de continuar.

El panel Administración → Workers reconcilia el estado de `market_worker` con Docker Compose aunque el contenedor haya sido iniciado desde el launcher o Docker Desktop. La detección de Docker admite la latencia normal de Docker Desktop mediante `DOCKER_PROBE_TIMEOUT_S` (8 segundos por defecto), mientras que el health operativo de Mercado se obtiene del broker y del heartbeat del consumidor.

**Opción manual (más control):**

```powershell
# Terminal 1: API local
.\.venv\Scripts\python.exe -m uvicorn services.api:app --reload --port 8000 --log-level info

# Terminal 2: Frontend Vue
cd frontend-vue
npm run dev
```

### 5. Primer arranque del frontend Vue durante la migración

El frontend Vue se ejecuta en paralelo y no reemplaza todavía al contenedor ni al directorio React. El método oficial de trabajo diario es el script único, ejecutado desde la raíz:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\start-dev.ps1
```

El script utiliza Docker para PostgreSQL. Después aplica migraciones y levanta API, MCP Products y Vue como procesos locales. `-WithCatalogWorker` agrega Redis y Dramatiq; `-McpMode All` agrega Web Search; `-McpMode Off` omite MCP y `-CheckOnly` no inicia servicios ni aplica migraciones. Si `db` figura `running` pero no publica `127.0.0.1:5433`, el launcher ejecuta `docker compose up -d db` para reconciliar la configuración antes del timeout final.

Verificaciones y diagnóstico:

- API: `http://127.0.0.1:8000/health`.
- MCP Products: `http://127.0.0.1:8100/mcp`.
- MCP Web Search opcional: `http://127.0.0.1:8102/mcp`.
- Login Vue: `http://127.0.0.1:5176/login`.
- Logs por ejecución: `logs/dev/<fecha-hora>/`.
- `start-dev.log` contiene la secuencia general; los archivos `*.stdout.log` y `*.stderr.log` separan la salida de API y Vue.
- Los archivos stdout/stderr se crean en la ejecución que inicia cada proceso. Si API, MCP o Vue se reutilizan, continúan escribiendo en los logs de su ejecución original; el nuevo `state.json` los marca como reutilizados y agrega `*_log_source_hint` cuando puede localizar ese origen.
- Para el worker Docker, `state.json` registra `catalog_worker_log_command`; los eventos NDJSON `actor_received`, `job_claimed`, `item_started`, `item_succeeded|item_failed` y `job_finished` incluyen IDs y duración.
- El worker `catalog_worker` iniciado desde Administración escribe stdout/stderr en `logs/worker_catalog.log`; no usa pipes sin lector. Si convive con Dramatiq Docker, cada mensaje lo consume sólo uno de ellos. `start-dev.ps1` advierte esta competencia y registra los PID locales en `catalog_worker_competing_local_pids`.
- `start-dev.ps1` exporta `GROWEN_DEV_RUN_LOG_DIR` a los procesos hijos. Servicios → Mantenimiento de logs y `scripts/cleanup_logs.py` usan ese dato más los PID de `state.json` para proteger ejecuciones activas y eliminan las ejecuciones antiguas como carpetas completas. Ver `docs/LOG_CLEANUP.md`.
- Si un servicio local ya responde correctamente, se reutiliza. Un puerto ocupado por un servicio no saludable detiene el arranque con código de error.
- El servicio Compose `frontend` continúa correspondiendo a React; no es necesario levantarlo para trabajar en Vue.
- Una pantalla Vue oscura que permanece cargando suele indicar que `/auth/me` no pudo alcanzar la API.
- Estado detallado y fases: `docs/FRONTEND_MIGRATION_VUE.md`.

Los comandos individuales se conservan en las secciones de troubleshooting para diagnóstico, no como flujo normal de inicio.

## Desarrollo LAN (Compartir con otros dispositivos)

Si necesitas probar la aplicación desde otro dispositivo en la misma red (celular, tablet, otra PC), sigue estos pasos:

### 1. Obtener tu IP local

```powershell
# Windows
ipconfig
# Buscar "IPv4 Address" en tu adaptador de red activo (ej: 192.168.1.50)

# Linux/Mac
ip addr  # o ifconfig
```

### 2. Configurar el Frontend

El servidor Vite ya está configurado para escuchar en todas las interfaces (`host: true`). Al iniciar verás:

```
  VITE v5.x.x  ready in XXX ms

  ➜  Local:   http://localhost:5175/
  ➜  Network: http://192.168.1.50:5175/   ← Usar esta URL
```

**Opcional**: Crear archivo `frontend/.env.development.local` para forzar la URL de API:

```bash
# frontend/.env.development.local
# Reemplazar 192.168.1.X con tu IP real
VITE_API_URL=http://192.168.1.X:8000
VITE_PORT=5175
```

> **Nota**: El cliente HTTP (`http.ts`) usa `window.location.hostname` automáticamente, por lo que normalmente NO necesitas este archivo.

### 3. Configurar la API

La API también debe escuchar en `0.0.0.0`. `start.bat` ya lo hace por defecto.

**Inicio manual** (si no usas start.bat):

```powershell
# Con --host 0.0.0.0 para aceptar conexiones externas
.\.venv\Scripts\python.exe -m uvicorn services.api:app --reload --host 0.0.0.0 --port 8000
```

### 4. Verificar Firewall

Asegúrate de que Windows Firewall permita conexiones entrantes en:
- Puerto `5175` (Frontend Vite)
- Puerto `8000` (API FastAPI)

```powershell
# Agregar reglas de firewall (ejecutar como Admin)
netsh advfirewall firewall add rule name="Vite Dev" dir=in action=allow protocol=tcp localport=5175
netsh advfirewall firewall add rule name="FastAPI Dev" dir=in action=allow protocol=tcp localport=8000
```

### 5. Acceder desde otro dispositivo

Desde el otro dispositivo en la misma red, abrir:
- **Frontend**: `http://192.168.1.X:5175` (reemplazar con tu IP)
- **API Swagger**: `http://192.168.1.X:8000/docs`

### Troubleshooting LAN

| Problema | Solución |
|----------|----------|
| "Connection refused" | Verificar firewall, verificar que API/Vite estén corriendo |
| HMR no funciona | Refrescar página manualmente (F5), WebSocket puede estar bloqueado |
| CORS errors | La API ya permite CORS, pero verificar que la IP sea correcta |
| Login no persiste | Verificar que accedes por IP (no localhost) en ambos servicios |

---

## Flujo de Desarrollo Diario

### Iniciar Sesión de Trabajo

**Opción 1: Usando start-dev.ps1 (Recomendado)**
```powershell
# Ejecuta directamente para desarrollo local
.\scripts\start-dev.ps1

# El script automáticamente:
# - Levanta DB Docker (puerto 5433)
# - Inicia API local con hot-reload (puerto 8000)
# - Ejecuta migraciones Alembic
# - Inicia MCP Products y Vue (puerto 5176)
```

**Opción 2: Manual (más control)**
```powershell
# Terminal 1: DB en Docker (una vez al día)
docker compose up -d db

# Terminal 2: API local con hot-reload
.\.venv\Scripts\python.exe -m uvicorn services.api:app --reload --port 8000 --log-level info

# Terminal 3: Frontend local (desarrollo)
cd frontend-vue
npm run dev
```

**URLs de desarrollo**:
- Frontend Vue: `http://127.0.0.1:5176` (Vite dev server)
- API: `http://127.0.0.1:8000` (uvicorn local)
- Swagger: `http://127.0.0.1:8000/docs`

### Variables de Entorno para start.bat

El script `start.bat` soporta las siguientes variables para casos especiales:

```powershell
# Desarrollo Local (DEFAULT) - API local + DB Docker
.\start.bat

# Testing con Stack Docker Completo
SET USE_DOCKER_STACK=1
.\start.bat

# Forzar inicio de Redis (necesario para workers)
SET REQUIRE_REDIS=1
.\start.bat

# Permitir SQLite si Docker falla (solo desarrollo)
SET ALLOW_SQLITE_FALLBACK=1
.\start.bat
```

**Modos de operación**:
- `USE_DOCKER_STACK=0` (default): Inicia API local con hot-reload + DB Docker
- `USE_DOCKER_STACK=1`: Solo valida que contenedores Docker estén corriendo (no inicia nada)

### Workflow Típico

1. **Hacer cambios en código** (API, workers, etc.)
   - Guardas archivo
   - Uvicorn detecta cambio y recarga (~1s)
   - Refrescas navegador

2. **Probar cambios**
   - Frontend Vue en `5176` conecta a API local `8000` mediante `/api`
   - Logs en tiempo real en terminal
   - Debugger disponible (breakpoints)

3. **Ejecutar tests**
   ```powershell
   # Tests unitarios (rápidos)
   .\.venv\Scripts\python.exe -m pytest tests/test_auth.py -v
   
   # Tests de integración (usan DB Docker)
   .\.venv\Scripts\python.exe -m pytest tests/test_market_api.py -v
   
   # Suite completa (cuando terminas feature)
   .\.venv\Scripts\python.exe -m pytest -q
   ```

4. **Workers manuales** (solo cuando necesitas)
   ```powershell
   # Procesar una imagen específica
   .\.venv\Scripts\python.exe -c "from workers.images import process_image; import asyncio; asyncio.run(process_image(product_id=123))"
   
   # Actualizar precio de un producto
   powershell.exe -NoProfile -ExecutionPolicy Bypass -File scripts/run_market_update.ps1 -ProductId 456
   ```

## Testing de Integración (Docker)

**Cuándo usar Docker completo**:
- ✅ Antes de merge a main
- ✅ Probar cambios en Dockerfile
- ✅ Verificar variables de entorno
- ✅ Testing de workers/scheduler en background
- ✅ Simular entorno de producción

**Modo 1: Testing con start.bat**
```powershell
# Primero levanta el stack Docker completo
docker compose up -d

# Luego valida con start.bat
SET USE_DOCKER_STACK=1
.\start.bat

# Este flujo pertenece al launcher heredado. Para Vue, validar API 8000, DB 5433 y frontend 5176 con scripts/start-dev.ps1 -CheckOnly.
# No inicia servicios, solo valida
```

**Modo 2: Testing manual**
```powershell
# Rebuild y levantar todo
docker compose build
docker compose up -d

# Verificar logs
docker compose logs api --tail 50 -f

# Probar en:
# http://127.0.0.1:5173 (nginx frontend)
# http://127.0.0.1:8000/docs (API)

# Detener cuando termines
docker compose down
```

## Comparación de Velocidades

| Acción | Local | Docker |
|--------|-------|--------|
| **Cambio en código** | ~1s (hot reload) | 3-5 min (rebuild) |
| **Ver logs** | Terminal directo | `docker compose logs` |
| **Debugger** | Directo (pdb/debugpy) | Remoto (complejo) |
| **Tests unitarios** | ~5s | ~10s (overhead contenedor) |
| **Inicio completo** | ~10s | ~2 min (pull/build) |

## Tips de Productividad

### 1. Aliases PowerShell

Agrega a tu `$PROFILE` (edita con `notepad $PROFILE`):

```powershell
# Ajustar una vez a la ubicación local del clon
$GrowenRoot = 'C:\ruta\al\repositorio\Growen'

function gw { Set-Location $GrowenRoot }

# Inicio oficial de desarrollo
function dev-start {
    powershell.exe -NoProfile -ExecutionPolicy Bypass -File (Join-Path $GrowenRoot 'scripts\start-dev.ps1')
}

# Detener sólo la DB después de cerrar los procesos locales
function dev-db-stop {
    Push-Location $GrowenRoot
    docker compose stop db
    Pop-Location
}

function dev-test {
    & (Join-Path $GrowenRoot '.venv\Scripts\python.exe') -m pytest -q
}

# Docker completo
function prod-test {
    docker compose up -d --build
    docker compose logs api -f
}
```

### 2. VS Code Tasks

Crea `.vscode/tasks.json`:

```json
{
  "version": "2.0.0",
  "tasks": [
    {
      "label": "Dev: Start API",
      "type": "shell",
      "command": "python -m uvicorn services.api:app --reload --port 8000",
      "problemMatcher": [],
      "isBackground": true
    },
    {
      "label": "Dev: Start DB",
      "type": "shell",
      "command": "docker compose up -d db",
      "problemMatcher": []
    },
    {
      "label": "Dev: Stop All",
      "type": "shell",
      "command": "docker compose stop",
      "problemMatcher": []
    }
  ]
}
```

Luego: `Ctrl+Shift+P` → "Tasks: Run Task"

### 3. Watch Mode para Tests

```powershell
# Auto-ejecutar tests al guardar
pytest-watch -c  # -c para clear screen
```

### 4. Hot Reload Frontend + API

```powershell
# Terminal 1: API
.\.venv\Scripts\python.exe -m uvicorn services.api:app --reload

# Terminal 2: Frontend
cd frontend
npm run dev

# Ambos con hot reload automático
```

## Cuándo Recompilar Docker

### ❌ NO recompilar por:
- Cambios en Python/TypeScript (usa local)
- Probar nueva feature
- Debugging
- Cambios en lógica de negocio

### ✅ SÍ recompilar por:
- Nuevas dependencias en `requirements.txt`
- Cambios en `Dockerfile.*`
- Cambios en `docker-compose.yml`
- Variables de entorno nuevas
- Antes de merge a main
- Deploy a producción

## Checklist Pre-Commit

Antes de hacer commit/push:

```powershell
# 1. Gate canónico: venv 3.14.6, lint, seguridad, tests y frontends
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\check-quality.ps1

# 2. Verificar whitespace y alcance exacto
git diff --check
git status --short

# 3. (Opcional) Test Docker completo antes de merge/deploy
docker compose up -d --build
# Probar en navegador
docker compose down
```

Antes del push, auditar secretos sin imprimir valores, resolver `git remote get-url origin` y confirmar rama/destino. Usar staging por rutas explícitas; no usar `git add .`. Si el remoto no puede verificarse como confiable o privado, detenerse hasta contar con aprobación explícita informada. Ver `docs/SECURITY.md` y `.agents/skills/git-commit-push/SKILL.md`.

## Troubleshooting Común

### Problema: UI queda "Cargando" y se resuelve al presionar tecla en terminal

**Causa**: Modo **QuickEdit** de la consola de Windows está habilitado.

Cuando QuickEdit está activo (comportamiento por defecto en Windows):
1. Si haces clic en la ventana de la terminal (aunque sea accidentalmente)
2. La consola entra en "modo de selección"
3. **PAUSA completamente** la ejecución del proceso (uvicorn, node, etc.)
4. Presionar cualquier tecla (espacio, Enter) "despausa" la ejecución

**Solución 1: Deshabilitar QuickEdit permanentemente (Recomendado)**
1. Click derecho en la barra de título de la ventana CMD/PowerShell
2. Seleccionar **"Propiedades"** (Properties)
3. En pestaña **"Opciones"** (Options)
4. **Desmarcar** la casilla **"QuickEdit Mode"** / "Modo de edición rápida"
5. Click en **OK**

**Solución 2: Script de inicio que deshabilita QuickEdit**

Usar `scripts/start_api_noquickedit.ps1` que deshabilita QuickEdit automáticamente:
```powershell
.\scripts\start_api_noquickedit.ps1
```

**Solución 3: Ejecutar sin ventana interactiva (Background)**

Si no necesitas ver los logs en tiempo real:
```powershell
# API en background con logs a archivo
Start-Process -NoNewWindow -FilePath .\.venv\Scripts\python.exe -ArgumentList "-m uvicorn services.api:app --reload --port 8000" -RedirectStandardOutput "logs\api_stdout.log" -RedirectStandardError "logs\api_stderr.log"

# Ver logs cuando quieras
Get-Content logs\api_stdout.log -Tail 50 -Wait
```

**Nota**: Este problema NO ocurre en:
- Windows Terminal (la app nueva de Microsoft)
- Terminales integradas de VS Code/Cursor (aunque pueden tener configuración similar)
- Linux/Mac

---

### Problema: "DB connection refused"

**Causa**: PostgreSQL Docker no arrancó o está saludable sólo dentro de una red interna sin publicar `5433` al host.
```powershell
# Verificar el servicio y el binding efectivo
docker compose ps db
docker port growen-postgres

# Logs
docker compose logs db --tail 20

# Reiniciar
docker compose restart db
```

Si `docker compose ps db` muestra `healthy` pero omite `127.0.0.1:5433->5432/tcp`, comprobar `docker inspect growen-postgres` y los listeners de Windows. `db` debe participar en `backend` y `host_access`: Docker no publica puertos de un contenedor conectado únicamente a una red `internal`. No eliminar el volumen `pgdata` para reparar este caso.

### Problema: "Redis connection refused"

**Causa**: Redis Docker no arrancó o no está disponible
```powershell
# Verificar (contenedor se llama growen-redis)
docker compose ps

# Ver solo Redis
docker ps --filter "name=growen-redis"

# Logs
docker compose logs redis --tail 20

# Reiniciar
docker compose restart redis
```

Para el alta canónica batch también debe existir un consumidor de la cola `catalog`; un Redis saludable por sí solo no procesa jobs. Iniciar el entorno con `start-dev.ps1 -WithCatalogWorker`, verificar `docker compose --profile optional ps dramatiq` y el estado persistido en `canonical_batch_jobs`. Un HTTP 202 sólo confirma recepción/idempotencia, no finalización. Desde Administración, iniciar `catalog_worker` ahora inicia/verifica primero Redis y falla explícitamente si el broker no publica el puerto host.

Evitar dos consumidores de desarrollo para la misma cola. Si `state.json` informa `catalog_worker_competing_local_pids`, revisar tanto `logs/worker_catalog.log` como `docker compose --profile optional logs dramatiq` y detener de forma coordinada el modo que no se utilizará; no asumir que la ausencia de un evento en Docker implica que el job no fue consumido.

### Problema: la ejecución nueva no contiene logs de la API

`start-dev.ps1` puede reutilizar una API saludable iniciada por un run anterior. En ese caso el proceso continúa escribiendo en el `api.stderr.log` de la ejecución que lo creó, mientras la carpeta nueva registra que fue reutilizado. Consultar `api_log_source_hint` y correlacionar timestamps/PID de `state.json`; no asumir que un log nuevo vacío significa que la petición no llegó.

### Seguridad al inspeccionar Compose

No incluir la salida completa de `docker compose config` en reportes: Compose expande valores de `.env`. Preferir `docker compose config --quiet`, `docker compose config --services`, `docker compose ps`, `docker port` e inspecciones focales sin variables de entorno.

### Problema: "Port 8000 already in use"

**Causa**: otra instancia de API corriendo. En Windows pueden coexistir dos listeners sobre `127.0.0.1:8000`; en ese estado un `/health` exitoso no garantiza qué proceso ni qué versión atendió una petición.

```powershell
# Enumerar todos los listeners y sus PID
netstat -ano -p TCP | Select-String "127.0.0.1:8000"

# Correlacionar PID, hora de inicio y proceso padre
Get-CimInstance Win32_Process -Filter "ProcessId=<PID>" |
    Select-Object ProcessId, ParentProcessId, CreationDate, CommandLine

# Detener desde el launcher o terminal que lo inició. Sólo con autorización:
taskkill /PID <PID> /T /F
```

El estado esperado es un único listener. Si `taskkill` devuelve `Acceso denegado`, cerrar o reiniciar el launcher con los mismos privilegios que creó el proceso; no asumir que el hot reload actualizó ambas instancias. Después del reinicio, volver a enumerar el puerto antes de validar contratos en la UI.

### Problema: "Module not found"

**Causa**: Virtual environment no activado o dependencias faltantes
```powershell
# Activar venv
.\.venv\Scripts\Activate.ps1

# Reinstalar
pip install -r requirements.txt
```

### Problema: Hot reload no funciona

**Causa**: Archivo fuera de watch path
```powershell
# Reiniciar uvicorn con watch explícito
uvicorn services.api:app --reload --reload-dir services --reload-dir db --reload-dir workers
```

## Variables de Entorno: Local vs Docker

### Local (.env)
```bash
DB_HOST=localhost
DB_PORT=5433  # Mapeado de Docker
DB_USER=growen
DB_PASS=local_password
```

### Docker (docker-compose.yml)
```yaml
environment:
  DB_HOST: db  # Nombre del servicio
  DB_PORT: "5432"  # Puerto interno
  DB_USER: growen
  DB_PASS: ${POSTGRES_PASSWORD}
```

## Estrategia de Branches

```
main (protegida)
  ↑
  merge después de testing Docker
  ↑
develop (tu branch de trabajo)
  ↑
  desarrollo local rápido
  ↑
feature/nueva-funcionalidad
```

**Workflow**:
1. Desarrollar en `feature/*` con API local
2. Tests pasan → merge a `develop`
3. Testing Docker en `develop` → todo OK
4. Ejecutar localmente `scripts/check-quality.ps1`.
5. Si se necesita una validación remota limpia, lanzar manualmente `Quality gate manual` en GitHub Actions.

El workflow remoto usa `workflow_dispatch`: no tiene triggers de `push` ni `pull_request`, por lo que no consume créditos automáticamente. CI significa repetir instalación, lint, tests y build en un runner limpio para detectar dependencias implícitas o diferencias respecto de la máquina local.

Las instalaciones oficiales usan locks con hashes. `scripts/update-locks.ps1` regenera los locks por servicio y `scripts/generate-sbom.ps1` actualiza el inventario CycloneDX. Ambos deben ejecutarse al cambiar dependencias y luego validarse con `scripts/check-quality.ps1`.

## Recursos Útiles

- **Logs API local**: Terminal donde corre uvicorn
- **Logs DB Docker**: `docker compose logs db -f`
- **Logs frontend**: Terminal donde corre `npm run dev`
- **DB GUI**: pgAdmin (`localhost:5433`) o DBeaver

## Resumen

**Regla de Oro**: 
> Desarrolla local (rápido), testa en Docker (antes de merge), deploya Docker (producción)

**Comandos Esenciales**:
```powershell
# Día a día (OPCIÓN 1 - Recomendada)
.\scripts\start-dev.ps1                         # DB + API + Products MCP + Vue

# Día a día (OPCIÓN 2 - Manual)
docker compose up -d db                          # Infra
.\.venv\Scripts\python.exe -m uvicorn services.api:app --reload --port 8000
cd frontend-vue && npm run dev                    # Frontend Vue local

# Quality gate Vue aislado
cd frontend-vue
npm run typecheck
npm test
npm run test:e2e
npm run build
npm audit --audit-level=high

# Antes de commit
.\.venv\Scripts\python.exe -m pytest -q          # Tests
SET USE_DOCKER_STACK=1 && .\start.bat            # Validar stack Docker
docker compose down                               # Limpiar
```

**Beneficios**:
- ⚡ Desarrollo 10x más rápido (hot reload ~1s vs rebuild 3-5min)
- 🐛 Debugging directo con breakpoints
- 💾 Menos uso de recursos (solo DB en Docker)
- 🎯 Docker solo cuando importa (integración/producción)
- 🚀 `start.bat` automatiza setup completo
