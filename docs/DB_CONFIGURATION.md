<!-- NG-HEADER: Nombre de archivo: DB_CONFIGURATION.md -->
<!-- NG-HEADER: Ubicación: docs/DB_CONFIGURATION.md -->
<!-- NG-HEADER: Descripción: Configuración de conexión a base de datos en distintos entornos -->
<!-- NG-HEADER: Lineamientos: Ver AGENTS.md -->

# Configuración de Base de Datos

Guía para configurar correctamente la conexión a base de datos en desarrollo local y Docker.

## Problema Común: DB_URL Hardcoded

### Síntoma
- **Local (SQLite)**: Funciona correctamente
- **Docker (PostgreSQL)**: Error `Could not parse SQLAlchemy URL from given URL string`
- **Logs**: Traceback en `create_async_engine(DB_URL, future=True)`

### Causa Raíz
Hardcodear un fallback de SQLite impide que el sistema construya la URL de PostgreSQL desde variables de entorno individuales en Docker.

## Patrón Correcto

### ❌ Incorrecto (causa errores en Docker)
```python
import os
from sqlalchemy.ext.asyncio import create_async_engine

DB_URL = os.getenv("DB_URL", "sqlite+aiosqlite:///./growen.db")  # ❌ Fallback hardcoded
engine = create_async_engine(DB_URL, future=True)
```

### ✅ Correcto (funciona en todos los entornos)
```python
import os
from sqlalchemy.ext.asyncio import create_async_engine
from agent_core.config import settings

DB_URL = os.getenv("DB_URL") or settings.db_url  # ✅ Usa settings como fallback
engine = create_async_engine(DB_URL, future=True)
```

## Cómo Funciona

### Desarrollo Local
- `DB_URL` no está seteado → usa `settings.db_url`
- `settings.db_url` por defecto: `sqlite+aiosqlite:///./growen.db`
- ✅ Funciona con SQLite local

### Docker / Producción
En `docker-compose.yml`:
```yaml
environment:
  DB_URL: ""  # Forzado vacío para construir desde componentes
  DB_HOST: db
  DB_PORT: "5432"
  DB_USER: ${POSTGRES_USER:-growen}
  DB_PASS: ${POSTGRES_PASSWORD}
  DB_NAME: ${POSTGRES_DB:-growen}
```

- `DB_URL` está vacío → usa `settings.db_url`
- `settings.db_url` construye: `postgresql+psycopg://user:pass@db:5432/growen`
- ✅ Funciona con PostgreSQL en Docker

## Archivos que DEBEN Usar Este Patrón

### Backend Core
- ✅ `db/session.py` (implementación canónica)

### Workers (Dramatiq)
- ✅ `workers/market_scraping.py`
- ✅ `workers/images.py`

### Servicios / Jobs
- ✅ `services/jobs/market_scheduler.py`

### Al Crear Nuevos Módulos
Cualquier archivo que:
- Importe `create_async_engine` de SQLAlchemy
- Cree su propia instancia de engine/sessionmaker
- No use el engine central de `db/session.py`

## Checklist al Revisar Código

Buscar patrones problemáticos:
```bash
# En Linux/Mac/Git Bash
grep -r 'DB_URL = os.getenv("DB_URL", ' --include="*.py"

# En PowerShell
Select-String -Path "**/*.py" -Pattern 'DB_URL = os\.getenv\("DB_URL", '
```

Si encuentra matches:
1. Agregar import: `from agent_core.config import settings`
2. Cambiar a: `DB_URL = os.getenv("DB_URL") or settings.db_url`
3. Eliminar fallback hardcoded
4. Rebuild contenedor si aplica

## Variables de Entorno Relacionadas

### Desarrollo Local (.env)
```bash
# Opción 1: SQLite (default, no requiere config)
# DB_URL no seteado → usa default de settings

# Opción 2: PostgreSQL local
DB_HOST=localhost
DB_PORT=5432
DB_USER=growen
DB_PASS=tu_password
DB_NAME=growen
```

### Docker (docker-compose.yml)
```yaml
# API service
environment:
  DB_URL: ""  # Importante: forzar vacío
  DB_HOST: db  # Nombre del servicio de PostgreSQL
  DB_PORT: "5432"
  DB_USER: ${POSTGRES_USER:-growen}
  DB_PASS: ${POSTGRES_PASSWORD}
  DB_NAME: ${POSTGRES_DB:-growen}
  PGCONNECT_TIMEOUT: ${PGCONNECT_TIMEOUT:-5}
```

### Producción
```bash
# Opción 1: URL completa (preferido en cloud/managed DB)
DB_URL=postgresql+psycopg://user:pass@host:5432/dbname

# Opción 2: Componentes individuales
DB_HOST=production-db-host
DB_PORT=5432
DB_USER=growen_prod
DB_PASS=secure_password
DB_NAME=growen_prod
```

## Debugging

### Verificar URL Construida
```python
from agent_core.config import settings
print(f"DB URL: {settings.db_url}")
```

### Logs de Contenedor
```bash
# Ver logs del API (contenedor: growen-api)
docker compose logs api --tail 50

# Ver logs de Redis (contenedor: growen-redis)
docker compose logs redis --tail 50

# Verificar estado de servicios
docker compose ps

# Verificar contenedores por nombre
docker ps --filter "name=growen-"

# Buscar error específico
docker compose logs api 2>&1 | grep "Could not parse SQLAlchemy"
```

### Test de Conexión
```python
from db.session import engine

async def test_connection():
    async with engine.begin() as conn:
        result = await conn.execute(text("SELECT 1"))
        print(f"Connection OK: {result.scalar()}")
```

## Historial de Correcciones

### 2025-11-15: Corrección Masiva DB_URL
**Archivos corregidos**:
- `workers/market_scraping.py` línea 27
- `workers/images.py` línea 18
- `services/jobs/market_scheduler.py` línea 44

**Síntoma previo**: API en loop de reinicio con error `Could not parse SQLAlchemy URL`

**Causa**: Hardcoded fallback SQLite en workers/jobs impedía construcción de URL PostgreSQL en Docker

**Solución**: Usar patrón `DB_URL = os.getenv("DB_URL") or settings.db_url`

## Referencias

- Implementación canónica: `db/session.py`
- Config settings: `agent_core/config.py`
- Docker compose: `docker-compose.yml`
- Lineamientos generales: `AGENTS.md` sección "Documentación contextual"
