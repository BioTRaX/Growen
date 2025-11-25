<!-- NG-HEADER: Nombre de archivo: TESTING.md -->
<!-- NG-HEADER: Ubicación: docs/TESTING.md -->
<!-- NG-HEADER: Descripción: Lineamientos completos de testing para el proyecto Growen -->
<!-- NG-HEADER: Lineamientos: Ver AGENTS.md -->

# Testing en Growen

Este documento centraliza todos los lineamientos, convenciones y troubleshooting relacionados con la ejecución de tests en el proyecto.

## Requisitos previos

### Entorno virtual (OBLIGATORIO)

**SIEMPRE activar la venv antes de ejecutar tests:**

```powershell
# Opción 1: Activar venv explícitamente (RECOMENDADO para agentes)
& C:/Proyectos/NiceGrow/Growen/.venv/Scripts/Activate.ps1
pytest tests/ -v

# Opción 2: Usar el ejecutable Python de la venv directamente
C:/Proyectos/NiceGrow/Growen/.venv/Scripts/python.exe -m pytest tests/ -v

# Opción 3: Desde directorio del proyecto con venv activada
.venv\Scripts\activate
pytest -q
```

**NUNCA ejecutar `pytest` directamente sin verificar que la venv esté activa.** Hacerlo puede usar un intérprete incorrecto o dependencias del sistema.

### Dependencias de testing

```bash
pip install pytest pytest-asyncio httpx respx
```

Verificar que `pytest.ini` esté configurado correctamente (ya incluido en el repo).

---

## Comandos de prueba

### Ejecución básica

```powershell
# Todos los tests (modo silencioso)
pytest -q

# Todos los tests con verbose
pytest tests/ -v

# Un archivo específico
pytest tests/test_canonical_helpers.py -v

# Tests por patrón de nombre
pytest -k "canonical" -v

# Tests por marker
pytest -m "not performance" -v
pytest -m "slow" -v
```

### Ejecución por carpeta/tipo

```powershell
# Tests unitarios (sin DB, rápidos)
pytest tests/unit/ -v

# Tests de routers/endpoints
pytest tests/routers/ -v

# Tests de performance (requieren más tiempo)
pytest tests/performance/ -v -m performance

# Tests E2E
pytest tests/e2e/ -v
```

### Opciones útiles

```powershell
# Con traceback corto (recomendado para CI)
pytest --tb=short

# Con traceback largo (debug)
pytest --tb=long

# Solo primeros N fallos
pytest --maxfail=3

# Con cobertura
pytest --cov=services --cov-report=html

# Sin paralelismo (más estable para DB compartida)
pytest -p no:randomly

# Ignorar carpeta específica
pytest tests/ --ignore=tests/performance
```

---

## Estructura de tests

```
tests/
├── conftest.py          # Fixtures compartidas (db_session, test_client, etc.)
├── fixtures/            # Datos de prueba (JSON, CSV, etc.)
├── html_fixtures/       # HTML de prueba para parsers
├── unit/                # Tests unitarios puros (sin DB)
│   ├── test_price_normalizer.py
│   └── test_dynamic_scraper.py
├── routers/             # Tests de endpoints API
│   ├── test_products_create.py
│   └── test_chat_http.py
├── performance/         # Tests de carga y stress
│   ├── conftest.py      # Fixtures específicas de performance
│   └── test_market_*.py
├── e2e/                 # Tests end-to-end
├── manual/              # Tests manuales/interactivos
└── test_*.py            # Tests de integración general
```

---

## Fixtures importantes

### `db_session` (conftest.py principal)

Sesión async SQLite en memoria para tests aislados. Se crea y destruye por cada test.

```python
@pytest_asyncio.fixture(scope="function", autouse=True)
async def db_session():
    """DB limpia por test (SQLite memoria compartida)."""
    # Crea todas las tablas
    # Yield session
    # Drop all tables
```

### `test_client`

Cliente HTTP síncrono para probar endpoints FastAPI:

```python
@pytest.fixture
def test_client():
    from fastapi.testclient import TestClient
    from services.api import app
    return TestClient(app)
```

### Fixtures de datos

- `sample_product`: Producto de prueba pre-creado
- `sample_category`: Categoría de prueba
- `admin_session`: Sesión con rol admin

---

## Compatibilidad SQLite/PostgreSQL

Los tests usan **SQLite en memoria** para velocidad. La base de producción usa **PostgreSQL**.

### Tipos incompatibles

| PostgreSQL | SQLite Compatible | Uso |
|------------|-------------------|-----|
| `JSONB` | `JSONBCompat` | Ver `db/models.py` |
| `ARRAY` | `JSON` (serializado) | Arrays como JSON |
| `UUID` | `String(36)` | UUIDs como texto |

### JSONBCompat

El proyecto define un tipo compatible en `db/models.py`:

```python
class JSONBCompat(TypeDecorator):
    """JSONB para PostgreSQL, JSON para SQLite."""
    impl = JSON
    cache_ok = True

    def load_dialect_impl(self, dialect):
        if dialect.name == "postgresql":
            from sqlalchemy.dialects.postgresql import JSONB
            return dialect.type_descriptor(JSONB())
        return dialect.type_descriptor(JSON())
```

**Usar `JSONBCompat` en lugar de `JSONB` directo** para columnas JSON en modelos.

### Funciones PostgreSQL-específicas

Evitar en tests:
- `unnest()`, `array_agg()`
- `jsonb_array_elements()`
- `date_trunc()` con timezone

---

## Troubleshooting

### Errores comunes y soluciones

| Error | Causa | Solución |
|-------|-------|----------|
| `ModuleNotFoundError` | venv no activada | Activar venv primero |
| `visit_JSONB` error | Tipo JSONB en SQLite | Usar `JSONBCompat` en modelo |
| `no such table: X` | Tablas no creadas | Verificar `Base.metadata.create_all` en fixture |
| Tests colgados | Fixtures async mal definidas | Usar `@pytest_asyncio.fixture` |
| `'coroutine' object has no attribute` | Fixture no awaiteada | Verificar decorador `@pytest_asyncio.fixture` |
| Errores en teardown | Conflicto en DB compartida | Ejecutar tests individuales o con `-p no:randomly` |
| `CancelledError` en cleanup | Event loop cerrado | Verificar scope de fixture async |

### Fixture async no se espera

**Problema**: `test_category = <coroutine object test_category at ...>`

**Causa**: Falta decorador `@pytest_asyncio.fixture`

**Solución**:
```python
# ❌ Incorrecto
@pytest.fixture
async def my_async_fixture():
    ...

# ✅ Correcto
@pytest_asyncio.fixture
async def my_async_fixture():
    ...
```

### Tests fallan en batch pero pasan individuales

**Causa**: Contaminación de estado entre tests (DB compartida, singletons, caché).

**Soluciones**:
1. Ejecutar sin plugin `randomly`: `pytest -p no:randomly`
2. Verificar que fixtures limpien estado correctamente
3. Usar `scope="function"` en fixtures de DB (no `session`)
4. Evitar modificar singletons globales sin restaurar

### Errores de conexión a DB

**En tests**: Verificar que `DB_URL` apunte a SQLite en memoria:
```python
os.environ["DB_URL"] = "sqlite+aiosqlite:///:memory:"
```

**En integración**: Si necesitas PostgreSQL real, marcar el test:
```python
@pytest.mark.postgres
def test_requires_real_postgres():
    ...
```

---

## Escribir nuevos tests

### Template básico

```python
#!/usr/bin/env python
# NG-HEADER: Nombre de archivo: test_my_feature.py
# NG-HEADER: Ubicación: tests/test_my_feature.py
# NG-HEADER: Descripción: Tests para [descripción]
# NG-HEADER: Lineamientos: Ver AGENTS.md

import pytest
import pytest_asyncio
from httpx import AsyncClient


class TestMyFeature:
    """Tests para la feature X."""

    @pytest.mark.asyncio
    async def test_basic_case(self, db_session):
        """Caso básico: descripción."""
        # Arrange
        ...
        # Act
        ...
        # Assert
        assert result == expected

    @pytest.mark.asyncio
    async def test_edge_case(self, db_session):
        """Caso borde: descripción."""
        ...
```

### Markers disponibles

```python
@pytest.mark.asyncio          # Test async
@pytest.mark.slow             # Test lento (>5s)
@pytest.mark.performance      # Test de performance
@pytest.mark.postgres         # Requiere PostgreSQL real
@pytest.mark.no_auth_override # No forzar admin en auth
```

### Fixtures personalizadas

```python
@pytest_asyncio.fixture
async def product_with_sources(db_session):
    """Producto con fuentes de mercado configuradas."""
    from db.models import Product, MarketSource
    
    product = Product(name="Test", sku="TEST-001")
    db_session.add(product)
    await db_session.flush()
    
    source = MarketSource(product_id=product.id, url="https://example.com")
    db_session.add(source)
    await db_session.commit()
    
    yield product
    
    # Cleanup (opcional si db_session ya lo hace)
```

---

## CI/CD

### Comando recomendado para CI

```bash
pytest tests/ \
    --ignore=tests/performance \
    --ignore=tests/manual \
    -m "not slow" \
    --tb=short \
    --maxfail=10 \
    -q
```

### Variables de entorno para CI

```bash
export DB_URL="sqlite+aiosqlite:///:memory:"
export AUTH_ENABLED="true"
export CANONICAL_SKU_STRICT="0"
export SALES_RATE_LIMIT_DISABLED="1"
```

---

## Tests de Performance

Los tests en `tests/performance/` tienen fixtures especiales en su propio `conftest.py`.

### Requisitos

- Fixtures deben usar `@pytest_asyncio.fixture`
- Marcar con `@pytest.mark.performance`
- Timeout apropiado para operaciones largas

### Ejecutar

```powershell
# Solo performance
pytest tests/performance/ -v -m performance --timeout=300

# Excluir performance (run normal)
pytest tests/ --ignore=tests/performance
```

---

## Checklist para PRs

- [ ] Tests nuevos para features nuevas
- [ ] Tests existentes siguen pasando
- [ ] Sin `JSONB` directo (usar `JSONBCompat`)
- [ ] Fixtures async tienen decorador correcto
- [ ] Tests no dependen de orden de ejecución
- [ ] Cleanup apropiado en fixtures

---

Actualizado: 2025-11-24
