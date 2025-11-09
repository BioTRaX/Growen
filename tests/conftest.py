#!/usr/bin/env python
# NG-HEADER: Nombre de archivo: conftest.py
# NG-HEADER: Ubicación: tests/conftest.py
# NG-HEADER: Descripción: Fixtures y configuración compartida de Pytest.
# NG-HEADER: Lineamientos: Ver AGENTS.md
import os
import sys
from pathlib import Path
import pytest
import pytest_asyncio

# Asegurar path del proyecto antes de importar módulos internos
project_root = Path(__file__).resolve().parents[1]
if str(project_root) not in sys.path:
    sys.path.append(str(project_root))

# -------- Entorno base de tests --------
# DB en memoria y flags por defecto que suavizan validaciones durante tests
os.environ["DB_URL"] = "sqlite+aiosqlite:///:memory:"
# En el entorno de tests usamos modo NO estricto por defecto para no exigir category_name
# en creaciones simples y mantener compatibilidad con payloads legacy.
os.environ.setdefault("CANONICAL_SKU_STRICT", "0")
os.environ.setdefault("SALES_RATE_LIMIT_DISABLED", "0")  # mantener activo pero limpiar bucket por test
os.environ.setdefault("AUTH_ENABLED", "true")

# Recargar módulo de sesión para que tome DB_URL
import db.session as _session  # type: ignore
import db.base as _base  # noqa: E402
import db.models  # noqa: F401,E402
from sqlalchemy import text as _text  # noqa: E402

from sqlalchemy.pool import StaticPool
from sqlalchemy.ext.asyncio import create_async_engine as _create_engine
from sqlalchemy.ext.asyncio import async_sessionmaker

if str(_session.engine.url).startswith("postgres"):
    mem_url = "sqlite+aiosqlite:///file:memdb1?mode=memory&cache=shared"
    engine = _create_engine(mem_url, connect_args={"uri": True}, poolclass=StaticPool)
    _session.engine = engine  # type: ignore
    _session.SessionLocal = async_sessionmaker(engine, expire_on_commit=False, class_=_session.AsyncSession)  # type: ignore
else:
    engine = _session.engine

Base = _base.Base


@pytest_asyncio.fixture(scope="function", autouse=True)
async def db_session():
    """DB limpia por test (SQLite memoria compartida)."""
    engine = _session.engine
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        try:
            await conn.execute(_text(
                "CREATE TABLE IF NOT EXISTS sku_sequences (category_code VARCHAR(3) PRIMARY KEY, next_seq INTEGER NOT NULL)"
            ))
        except Exception:
            pass
    yield
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


# -------- Overrides de auth/CSRF y utilidades comunes --------
from services.api import app  # noqa: E402
from services.auth import current_session, require_csrf, SessionData  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

# Overrides globales inmediatos para cubrir clientes creados a nivel módulo
app.dependency_overrides[current_session] = lambda: SessionData(None, None, "admin")
app.dependency_overrides[require_csrf] = lambda: None


@pytest.fixture(autouse=True)
def _force_admin_and_disable_csrf():
    """Reafirma overrides por test para evitar contaminación entre módulos."""
    app.dependency_overrides[current_session] = lambda: SessionData(None, None, "admin")
    app.dependency_overrides[require_csrf] = lambda: None
    yield
    app.dependency_overrides[current_session] = lambda: SessionData(None, None, "admin")
    app.dependency_overrides[require_csrf] = lambda: None


@pytest.fixture(autouse=True)
def _clear_sales_rate_limit_bucket():
    """Limpia el bucket de rate-limit de ventas antes de cada test."""
    try:
        from services.routers import sales as _sales
        _sales._RL_BUCKET.clear()
    except Exception:
        pass
    yield


@pytest.fixture()
def admin_client() -> TestClient:
    """Cliente HTTP con contexto admin y CSRF coherente (por si algún endpoint valida)."""
    c = TestClient(app)
    c.cookies.set("csrf_token", "test-csrf")
    c.headers.update({"X-CSRF-Token": "test-csrf"})
    return c


@pytest.fixture()
def product_payload_factory():
    """Factory de payloads para POST /catalog/products con defaults útiles.

    - category_name/subcategory_name: "general"
    - generate_canonical: False por defecto (tests deciden activarlo)
    """
    def _make(
        *,
        title: str,
        supplier_id: int | None = None,
        supplier_sku: str | None = None,
        sku: str | None = None,
        purchase_price: float | None = None,
        sale_price: float | None = None,
        initial_stock: int | None = None,
        category_name: str = "general",
        subcategory_name: str | None = None,
        generate_canonical: bool = False,
    ) -> dict:
        payload: dict = {
            "title": title,
            "initial_stock": initial_stock or 0,
            "category_name": category_name,
            "subcategory_name": subcategory_name or category_name,
            "generate_canonical": bool(generate_canonical),
        }
        if supplier_id is not None:
            payload["supplier_id"] = supplier_id
        if supplier_sku is not None:
            payload["supplier_sku"] = supplier_sku
        if sku is not None:
            payload["sku"] = sku
        if purchase_price is not None:
            payload["purchase_price"] = purchase_price
        if sale_price is not None:
            payload["sale_price"] = sale_price
        return payload

    return _make
