<!-- NG-HEADER: Nombre de archivo: TESTING.md -->
<!-- NG-HEADER: Ubicación: docs/TESTING.md -->
<!-- NG-HEADER: Descripción: Lineamientos completos de testing para el proyecto Growen -->
<!-- NG-HEADER: Lineamientos: Ver AGENTS.md -->

# Testing

## Suite focal del pipeline automático de Mercado (2026-08-28)

Actualización 2026-08-30: `test_market_api.py`, `test_market_pipeline.py` y
`test_market_worker.py` cubren el job focal por fuente, la persistencia del
precio en cuarentena y la activación únicamente tras validación manual completa.
En Vue, ejecutar también `src/modules/market/api/market.spec.ts` y
`src/modules/market/components/MarketDetailDrawer.spec.ts` para validar los
payloads, el enlace seguro y las acciones visibles del detalle.

```powershell
.\.venv\Scripts\python.exe -m pytest tests\test_market_pipeline.py tests\test_market_api.py tests\test_market_pricing.py tests\test_market_worker.py tests\test_source_finder.py tests\test_health_dramatiq.py tests\test_migrations_fresh_postgres.py -q -p no:randomly
cd frontend-vue
npm.cmd test -- src/modules/market/api/market.spec.ts src/modules/market/priceComparison.spec.ts
npm.cmd run typecheck
npm.cmd run build
```

La suite cubre deduplicación por competidor, tope de cobertura, omisión de MCP con cobertura completa, cierre de leases, contrato de etapas/resultados y rechazo `503` sin job huérfano. También verifica `NullPool` en el worker multihilo y que una respuesta MCP exitosa con `error: null` no se interprete como fallo. Para la cadena limpia, configurar `MIGRATION_TEST_POSTGRES_URL`; debe alcanzar `20260828_market_pipeline_v2`. El smoke operativo requiere Redis, MCP Web Search autenticado y `market_worker` con heartbeat, y debe terminar un lote controlado con hasta tres dominios por producto.

## Suite focal MCP SiYuan

```powershell
.\.venv\Scripts\python.exe -m pytest mcp_servers\siyuan_server\tests tests\test_publish_docs_to_siyuan.py tests\test_siyuan_smoke.py -q -p no:randomly
docker compose --profile siyuan config --quiet
```

La cobertura verifica raíces por rol, autorización previa a exportar, revisión SHA-256, historial obligatorio, ausencia de reintentos de escritura, conflictos, resultado incierto, sincronización Git → SiYuan y manifiestos sin contenido. El smoke de mutación debe ejecutarse sobre un workspace desechable porque no existe borrado automático.

## Suite focal del widget Crono de SiYuan

```powershell
node --test siyuan-widgets/crono/tests/crono-core.test.cjs
.\.venv\Scripts\python.exe -m pytest tests\test_sync_siyuan_widget.py -q -p no:randomly
.\scripts\sync-siyuan-widget.ps1 -WidgetName crono
```

La prueba Node cubre minutos, segundos, estados, serialización de Attribute
Views y categorías. Pytest ejecuta el sincronizador sobre directorios temporales
y comprueba drift, aplicación y exclusión de documentación. El último comando
es un diagnóstico por hash contra el workspace operativo; sólo agregar `-Apply`
con autorización explícita para actualizar archivos runtime.

## Gates Chat/Ollama/Redis/rollout (2026-08-16)

```powershell
.\.venv\Scripts\python.exe -m pytest tests\test_ws_chat.py tests\test_chat_ws_price.py tests\test_ws_role_refresh.py tests\test_ollama_local.py tests\test_chat_runtime_security.py tests\test_chat_rollout.py -q
$env:RUN_REDIS_INTEGRATION="1"
.\.venv\Scripts\python.exe -m pytest tests\test_chat_redis_integration.py tests\test_telegram_backpressure.py -q
.\.venv\Scripts\python.exe scripts\rag_corpus.py --synthetic --curated --dry-run
```

WebSocket usa Uvicorn loopback y `websockets` en el mismo event loop; no debe volver a `TestClient` ni `run_until_complete`. La integración Redis usa dos procesos y un prefijo efímero. El 2026-08-17 aprobaron 38 pruebas backend focales sin warnings, 91 pruebas Vue, typecheck y build. `test_price_lookup.py` migró a la fixture async `client`; `test_chat_api.py` conserva todavía compatibilidad síncrona legacy fuera de este gate.

La prueba `tests/test_worker_runtime_isolation.py` valida que ningún worker
ajeno a Telegram herede sus flags o el archivo del token desde `.env`. Las
pruebas que definen un secreto directo deben eliminar temporalmente su variante
`*_FILE` para no producir una configuración ambigua.

## Suite focalizada de conocimiento canónico

```powershell
.\.venv\Scripts\python.exe -m pytest tests\test_canonical_knowledge.py tests\test_enrichment_v2_rules.py tests\test_enrichment_v2_api_contract.py tests\test_market_pricing.py tests\test_market_validation.py tests\test_market_worker.py -q -p no:randomly
.\.venv\Scripts\python.exe -m pytest tests\test_migrations_fresh_postgres.py -q -p no:randomly
cd frontend-vue
npm.cmd run typecheck
npm.cmd test -- src/modules/products src/modules/knowledge
npm.cmd run build
```

PostgreSQL vacío debe crear `vector`, alcanzar `20260816_chat_rollout_v1` y confirmar ausencia de `market_sources`. `SMOKE_PROCESS_KNOWLEDGE=1` en `scripts/test_login_flow.py` exige login, CSRF, encolado, polling y `completed` sin imprimir secretos.

## Lineamientos generales

## Suite focalizada Enrich v2 y detalle canónico

```powershell
.\.venv\Scripts\python.exe -m pytest tests\test_enrichment_v2_rules.py tests\test_enrichment_v2_api_contract.py tests\test_product_canonical_detail.py mcp_servers\web_search_server\tests -q
.\.venv\Scripts\python.exe -m pytest tests\test_openai_provider.py tests\test_ollama_local.py -q -p no:randomly
cd frontend-vue
npm.cmd test -- src/modules/products src/app/modules/manifest.spec.ts
npm.cmd run typecheck
npm.cmd run build
```

El gate de Enrich verifica además que los fallos OpenAI conserven únicamente
`error.code`, HTTP, `x-request-id` y headers `x-ratelimit-*` permitidos; Ollama
debe discriminar timeout, HTTP, respuesta vacía, JSON inválido y esquema inválido.
La UI debe recuperar el último job y renderizar estos diagnósticos sin depender
del mensaje remoto.

La cobertura del proveedor debe comprobar que `gpt-5.6-luna` usa
`max_completion_tokens`, razonamiento `none`, temperatura determinista y cero
reintentos internos para Enrich. Los códigos permanentes de facturación o clave
deben quedar marcados como no reintentables.

El upgrade PostgreSQL vacío debe crear previamente `vector`, alcanzar `20260725_canonical_enrichment_v2`, crear `canonical_enrichment_jobs` y confirmar la ausencia de `products.market_price_reference`. `alembic check` puede seguir señalando drift histórico ajeno; se clasifica en `MIGRATIONS_NOTES.md` y no se incorpora a esta revisión.

## Suite focalizada de Chat seguro, RAG y MCP

```powershell
.\.venv\Scripts\python.exe -m pytest tests\test_chat_security_policy.py tests\test_chat_api.py tests\test_chat_quality_pipeline.py tests\test_chat_ws_price.py tests\test_ws_chat.py tests\test_rag_search.py tests\test_mcp_client.py tests\test_mcp_find_products.py tests\routers\test_chat_http.py tests\routers\test_chat_http_product_tool.py tests\routers\test_chat_tool_call.py mcp_servers\products_server\tests mcp_servers\web_search_server\tests tests\test_migrations_fresh_postgres.py -q -p no:randomly
cd frontend-vue
npm.cmd run typecheck
npm.cmd test
npm.cmd run build
```

La integración PostgreSQL limpia requiere `MIGRATION_TEST_POSTGRES_URL` y debe alcanzar el head actual `20260816_chat_rollout_v1`. La prueba debe verificar identidades externas, deduplicación Telegram, políticas RAG, observabilidad y las tablas de rollout. Los flags públicos permanecen apagados salvo configuración explícita del caso.

Auditoría 2026-08-15: la suite focal Chat/RAG/MCP aprobó 50 pruebas y omitió 6. Incluye transporte polling-only, presupuesto de historial, refresco de rol WebSocket y trazabilidad por canal. Los seis warnings —deprecación de `TestClient` y conexiones `aiosqlite` heredadas no devueltas al pool— son deuda activa; no deben ignorarse ni silenciarse antes del rollout.

Vue aprobó typecheck, build y 89 pruebas. `ChatView.spec.ts` valida streaming WebSocket sin duplicados, correlación/feedback y sanitización visual de cards; `TelegramIdentityPanel.spec.ts` valida el cierre por flags y la prohibición de autoaprobación administrativa.

## Suite focalizada de Mercado observable y Vue

```powershell
.\.venv\Scripts\python.exe -m pytest tests\test_market_api.py tests\test_market_integration.py tests\test_market_permissions.py tests\test_market_pricing.py tests\test_market_validation.py tests\test_market_worker.py tests\test_health_dramatiq.py tests\test_services_admin_orchestration.py -q -p no:randomly
cd frontend-vue
npm.cmd test -- src/app/modules/manifest.spec.ts src/modules/market/priceComparison.spec.ts
npm.cmd run build
cd ..\frontend
npm.cmd test -- src/__tests__/Market.test.tsx src/__tests__/MarketDetailModal.test.tsx
```

La integración PostgreSQL limpia se habilita con `MIGRATION_TEST_POSTGRES_URL` y debe alcanzar `20260721_market_observability_v1`. El smoke operativo `scripts/smoke_market_job.py` requiere DB/Redis/worker reales, crea dos pedidos para el producto local 1, exige deduplicación y espera un estado terminal.

## Suite focalizada de Compras v2

```powershell
.\.venv\Scripts\python.exe -m pytest tests\test_purchase_domain.py tests\test_purchases_api.py tests\test_purchase_validation.py tests\test_dedupe_import_lines.py tests\test_purchases_iaval.py tests\test_auth_session_cookie.py -q -p no:randomly
cd frontend-vue
npm.cmd test
npm.cmd run build
```

La cobertura incluye validación de cantidades enteras, bonificaciones, alta automática, idempotencia, ledger, historial e inmutabilidad posterior a confirmación.

## Suite focalizada de Productos Vue y alta canónica masiva

```powershell
.\.venv\Scripts\python.exe -m pytest tests\test_canonical_batch.py tests\test_canonical_products_api.py tests\test_canonical_sequence.py -q -p no:randomly
cd frontend-vue
npm.cmd test -- src/modules/products
npm.cmd run typecheck
npm.cmd run build
```

El script `npm test` de `frontend-vue/package.json` ya incluye `vitest --run`. Para ejecutar archivos o carpetas concretos se pasan únicamente sus rutas después de `--`; no debe agregarse un segundo `--run`, porque Vitest rechaza valores duplicados para esa opción.

Cuando se agreguen opciones discriminadas a un selector Vuetify —por ejemplo, un elemento sintético `create: true`— se debe declarar explícitamente el tipo del arreglo antes de insertar la opción y ejecutar `npm.cmd run typecheck`. Las pruebas de componente por sí solas pueden aprobar aunque la inferencia estructural falle durante `vue-tsc`.

Los componentes cuya falla depende de escribir, abrir el menú o seleccionar una opción deben montarse con Vuetify real. El harness de Vitest debe cargar `vite-plugin-vuetify`, incluir `vuetify` como dependencia inline y proveer los APIs de navegador ausentes en JSDOM (`ResizeObserver` o `visualViewport` cuando el componente los use). Al activar auto-imports globales, ejecutar también las pruebas vecinas: un componente real puede reemplazar un stub shallow sin que el test lo advierta explícitamente.

Si una corrida consolidada falla y luego se corrige sólo el módulo afectado, registrar ambos resultados por separado y volver a ejecutar la selección consolidada antes de declararla completamente aprobada.

Para cambios en autenticación o mutaciones protegidas, sumar siempre:

```powershell
.\.venv\Scripts\python.exe -m pytest tests\test_auth_session_cookie.py -q -p no:randomly
```

`@pytest.mark.no_auth_override` deshabilita tanto el rol simulado como el bypass CSRF. Un test de sesión debe cubrir login, `GET /auth/me` y al menos una mutación enviando la cookie y `X-CSRF-Token` reales.

Este documento centraliza todos los lineamientos, convenciones y troubleshooting relacionados con la ejecución de tests en el proyecto.

## Requisitos previos

### Entorno virtual (OBLIGATORIO)

**SIEMPRE activar la venv antes de ejecutar tests:**

```powershell
# Opción 1: Activar venv explícitamente (RECOMENDADO para agentes)
& C:/Proyectos/NiceGrow/Growen/.venv/Scripts/Activate.ps1
.\.venv\Scripts\python.exe -m pytest tests/ -v

# Opción 2: Usar el ejecutable Python de la venv directamente
C:/Proyectos/NiceGrow/Growen/.venv/Scripts/python.exe -m pytest tests/ -v

# Opción 3: Desde directorio del proyecto con venv activada
.venv\Scripts\activate
.\.venv\Scripts\python.exe -m pytest -q
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
.\.venv\Scripts\python.exe -m pytest -q

# Todos los tests con verbose
.\.venv\Scripts\python.exe -m pytest tests/ -v

# Un archivo específico
.\.venv\Scripts\python.exe -m pytest tests/test_canonical_helpers.py -v

# Tests por patrón de nombre
.\.venv\Scripts\python.exe -m pytest -k "canonical" -v

# Tests por marker
.\.venv\Scripts\python.exe -m pytest -m "not performance" -v
.\.venv\Scripts\python.exe -m pytest -m "slow" -v
```

### Ejecución por carpeta/tipo

```powershell
# Tests unitarios (sin DB, rápidos)
.\.venv\Scripts\python.exe -m pytest tests/unit/ -v

# Tests de routers/endpoints
.\.venv\Scripts\python.exe -m pytest tests/routers/ -v

# Tests de performance (requieren más tiempo)
.\.venv\Scripts\python.exe -m pytest tests/performance/ -v -m performance

# Tests E2E
.\.venv\Scripts\python.exe -m pytest tests/e2e/ -v
```

### Opciones útiles

```powershell
# Con traceback corto (recomendado para CI)
.\.venv\Scripts\python.exe -m pytest --tb=short

# Con traceback largo (debug)
.\.venv\Scripts\python.exe -m pytest --tb=long

# Solo primeros N fallos
.\.venv\Scripts\python.exe -m pytest --maxfail=3

# Con cobertura
.\.venv\Scripts\python.exe -m pytest --cov=services --cov-report=html

# Sin paralelismo (más estable para DB compartida)
.\.venv\Scripts\python.exe -m pytest -p no:randomly

# Ignorar carpeta específica
.\.venv\Scripts\python.exe -m pytest tests/ --ignore=tests/performance
```

---

## Estructura de tests

```
tests/
├── conftest.py          # Fixtures compartidas (db_session, client, admin_client, etc.)
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

La base SQLite de pruebas usa `sqlite+aiosqlite:///:memory:` junto con
`StaticPool`. No debe reemplazarse por una URI nombrada `file:...`: en Windows,
SQLAlchemy puede interpretarla como una ruta física y provocar carreras entre
procesos durante `create_all` y `drop_all`.

Sesión async SQLite en memoria para tests aislados. Se crea y destruye por cada test.

```python
@pytest_asyncio.fixture(scope="function", autouse=True)
async def db_session():
    """DB limpia por test (SQLite en memoria aislada por proceso)."""
    # Crea todas las tablas
    # Yield session
    # Drop all tables
```

### Clientes HTTP

La fixture compartida principal es `client`, un `httpx.AsyncClient` con `ASGITransport`. `admin_client` conserva `TestClient` para compatibilidad heredada:

```python
@pytest_asyncio.fixture
async def client():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac
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
| `no such table: X` | Tablas no creadas o teardown concurrente sobre el mismo engine | Verificar `Base.metadata.create_all` y que `DB_URL` conserve `:memory:` con `StaticPool` |
| `table X already exists` durante `create_all` | Una URI SQLite `file:...` se interpretó como archivo físico compartido, especialmente en Windows | No reescribir `:memory:` como URI nombrada; inspeccionar `engine.url` y `dialect.create_connect_args()` |
| Tests colgados | Fixtures async mal definidas | Usar `@pytest_asyncio.fixture` |
| `'coroutine' object has no attribute` | Fixture no awaiteada | Verificar decorador `@pytest_asyncio.fixture` |
| Errores en teardown | Ciclo de esquema duplicado o procesos pytest simultáneos | Confirmar aislamiento `:memory:` y ejecutar un solo pytest por checkout |
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

Las pruebas puras de filesystem o transformaciones que no requieren ORM pueden usar `@pytest.mark.no_db`; el fixture global omite entonces la creación del esquema SQLite. No usar este marker en routers, servicios o lógica que consulte persistencia.

### Migración completa sobre PostgreSQL vacío

La prueba `tests/test_migrations_fresh_postgres.py` valida la cadena Alembic real sin tocar la base configurada: crea una base temporal con prefijo controlado, ejecuta `upgrade head`, audita objetos críticos y la elimina al finalizar.

```powershell
$env:MIGRATION_TEST_POSTGRES_URL="postgresql+psycopg://<usuario>:<password>@127.0.0.1:5433/growen"
.\.venv\Scripts\python.exe -m pytest tests/test_migrations_fresh_postgres.py -v -p no:randomly
```

- No guardar la URL real en archivos versionados.
- El usuario PostgreSQL debe poder crear/eliminar bases temporales y habilitar la extensión `vector`.
- Sin `MIGRATION_TEST_POSTGRES_URL`, el test PostgreSQL se omite; el test de anonimización del auditor sigue ejecutándose.

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

El marker `no_auth_override` también restaura la validación CSRF real. No agregar manualmente overrides dentro de esos tests salvo que el objetivo sea comprobar un bypass específico.

### Serialización de pytest en el workspace compartido

No lanzar dos procesos pytest simultáneos sobre el mismo checkout. SQLite ya queda aislada por proceso mediante `:memory:` y `StaticPool`, pero los procesos todavía pueden competir por `__pycache__`, logs, puertos y recursos externos, o producir diagnósticos difíciles de atribuir. `app.dependency_overrides` se comparte dentro de cada proceso y exige restauración por test. Se puede ejecutar `npm.cmd run build` en paralelo con un único pytest porque no comparte esos recursos Python.

Ante `table already exists`/`no such table` en `create_all` o `drop_all`, comprobar primero cómo SQLAlchemy interpreta la URL. En Windows, `sqlite+aiosqlite:///file:memdb1?mode=memory&cache=shared` puede resolver a una ruta física. La configuración canónica conserva `sqlite+aiosqlite:///:memory:` y agrega solamente `StaticPool`.

### Deuda conocida del cliente síncrono

Los tests que aún usan `fastapi.testclient.TestClient` emiten `StarletteDeprecationWarning` por la transición futura a `httpx2`. No bloquea la suite actual; los tests nuevos deben preferir la fixture async `client`.

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

## Quality gate local y CI manual

La entrada única es:

```powershell
.\scripts\check-quality.ps1
```

El workflow `.github/workflows/quality-manual.yml` ejecuta la misma entrada en un runner limpio y solo se activa mediante `workflow_dispatch`. No se ejecuta automáticamente por push o pull request, evitando consumo involuntario de créditos.

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
.\.venv\Scripts\python.exe -m pytest tests/performance/ -v -m performance --timeout=300

# Excluir performance (run normal)
.\.venv\Scripts\python.exe -m pytest tests/ --ignore=tests/performance
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

Actualizado: 2026-07-14
## Aislamiento de multimedia opcional

`services.media.processor` carga `rembg` de forma diferida únicamente cuando se
invoca `remove_bg`. Las pruebas de API y de catálogo no necesitan inicializar
`numba`/modelos de segmentación al importar `services.api`. Si se prueba quitar
fondo, la dependencia debe estar instalada y el caso debe cubrir explícitamente
el error `rembg no disponible`.
