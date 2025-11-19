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

### 1. Levantar Solo Infraestructura en Docker

```powershell
# Solo PostgreSQL (y servicios externos si necesitas)
docker compose up -d db

# O todo menos API si quieres probar workers
docker compose up -d db mcp_products mcp_web_search
```

**Puertos expuestos**:
- PostgreSQL: `5433` (mapeado para evitar colisión con Postgres local si existe)
- MCP Products: `8100`
- MCP Web Search: `8102`

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
# DB_URL=postgresql+psycopg://growen:password@localhost:5433/growen

# Servicios externos (si usas Docker)
MCP_WEB_SEARCH_URL=http://localhost:8102/invoke_tool
AI_USE_WEB_SEARCH=1

# Scheduler (deshabilitado en dev local)
MARKET_SCHEDULER_ENABLED=false

# Workers Dramatiq (manual en dev)
REDIS_URL=redis://localhost:6379/0

# Logging
DEBUG_SQL=0  # Cambia a 1 para ver queries SQL
```

### 3. Activar Virtual Environment

```powershell
# Si no existe, crear
python -m venv .venv

# Activar
.\.venv\Scripts\Activate.ps1

# Instalar dependencias
pip install -r requirements.txt

# Verificar instalación
python scripts/check_admin_user.py
```

## Flujo de Desarrollo Diario

### Iniciar Sesión de Trabajo

**Opción 1: Usando start.bat (Recomendado)**
```powershell
# Ejecuta directamente para desarrollo local
.\start.bat

# El script automáticamente:
# - Levanta DB Docker (puerto 5433)
# - Inicia API local con hot-reload (puerto 8000)
# - Hace build del frontend si es necesario
# - Ejecuta migraciones Alembic
```

**Opción 2: Manual (más control)**
```powershell
# Terminal 1: DB en Docker (una vez al día)
docker compose up -d db

# Terminal 2: API local con hot-reload
python -m uvicorn services.api:app --reload --port 8000 --log-level info

# Terminal 3: Frontend local (desarrollo)
cd frontend
npm run dev
```

**URLs de desarrollo**:
- Frontend: `http://127.0.0.1:5173` (Vite dev server)
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
   - Frontend en `5173` conecta a API local `8000`
   - Logs en tiempo real en terminal
   - Debugger disponible (breakpoints)

3. **Ejecutar tests**
   ```powershell
   # Tests unitarios (rápidos)
   pytest tests/test_auth.py -v
   
   # Tests de integración (usan DB Docker)
   pytest tests/test_market_api.py -v
   
   # Suite completa (cuando terminas feature)
   pytest -q
   ```

4. **Workers manuales** (solo cuando necesitas)
   ```powershell
   # Procesar una imagen específica
   python -c "from workers.images import process_image; import asyncio; asyncio.run(process_image(product_id=123))"
   
   # Actualizar precio de un producto
   python scripts/run_market_update.ps1 -ProductId 456
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

# El script verifica que API (8000), DB (5433) y Frontend (5173) respondan
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
# Navegación rápida
function gw { cd C:\Proyectos\NiceGrow\Growen }

# Desarrollo rápido
function dev-start {
    docker compose up -d db
    python -m uvicorn services.api:app --reload --port 8000
}

function dev-stop {
    docker compose stop db
}

function dev-test {
    pytest -q
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
python -m uvicorn services.api:app --reload

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
# 1. Tests locales pasan
pytest -q

# 2. Linting OK
ruff check .
black --check .

# 3. No hay imports rotos
python verify_imports.py

# 4. (Opcional) Test Docker completo
docker compose up -d --build
# Probar en navegador
docker compose down
```

## Troubleshooting Común

### Problema: "DB connection refused"

**Causa**: PostgreSQL Docker no arrancó
```powershell
# Verificar (contenedor se llama growen-db)
docker compose ps db

# Logs
docker compose logs db --tail 20

# Reiniciar
docker compose restart db
```

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

### Problema: "Port 8000 already in use"

**Causa**: Otra instancia de API corriendo
```powershell
# Ver qué usa el puerto
netstat -ano | findstr :8000

# Matar proceso
taskkill /PID <numero> /F
```

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
4. PR a `main` → CI/CD → deploy

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
.\start.bat                                      # API local + DB Docker (todo automático)

# Día a día (OPCIÓN 2 - Manual)
docker compose up -d db                          # Infra
python -m uvicorn services.api:app --reload      # API local
cd frontend && npm run dev                        # Frontend local

# Antes de commit
pytest -q                                         # Tests
SET USE_DOCKER_STACK=1 && .\start.bat            # Validar stack Docker
docker compose down                               # Limpiar
```

**Beneficios**:
- ⚡ Desarrollo 10x más rápido (hot reload ~1s vs rebuild 3-5min)
- 🐛 Debugging directo con breakpoints
- 💾 Menos uso de recursos (solo DB en Docker)
- 🎯 Docker solo cuando importa (integración/producción)
- 🚀 `start.bat` automatiza setup completo
