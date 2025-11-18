#!/usr/bin/env python
# NG-HEADER: Nombre de archivo: conftest.py
# NG-HEADER: Ubicación: tests/conftest.py
# NG-HEADER: Descripción: Fixtures y configuración compartida de Pytest.
# NG-HEADER: Lineamientos: Ver AGENTS.md
import os
import sys
from pathlib import Path
from typing import AsyncGenerator
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
from sqlalchemy.ext.asyncio import async_sessionmaker, AsyncSession

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
    """DB limpia por test (SQLite memoria compartida). Retorna sesión para usar en fixtures/tests."""
    engine = _session.engine
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        try:
            await conn.execute(_text(
                "CREATE TABLE IF NOT EXISTS sku_sequences (category_code VARCHAR(3) PRIMARY KEY, next_seq INTEGER NOT NULL)"
            ))
        except Exception:
            pass
    
    # Crear y retornar sesión para que fixtures puedan usarla
    async with _session.SessionLocal() as session:
        yield session
    
    # Cleanup
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


# -------- Overrides de auth/CSRF y utilidades comunes --------
from services.api import app  # noqa: E402
from services.auth import current_session, require_csrf, SessionData  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from httpx import AsyncClient  # noqa: E402
from starlette.middleware.base import BaseHTTPMiddleware  # noqa: E402
from starlette.requests import Request  # noqa: E402


# Middleware para tests que respeta headers X-User-Roles y X-User-Id
class TestAuthMiddleware(BaseHTTPMiddleware):
    """Middleware que permite controlar auth via headers en tests."""
    async def dispatch(self, request: Request, call_next):
        # Solo override si hay header explícito de rol
        if "X-User-Roles" in request.headers:
            role = request.headers.get("X-User-Roles")
            user_id_str = request.headers.get("X-User-Id")
            user_id = int(user_id_str) if user_id_str and user_id_str.isdigit() else None
            
            # Override temporal para esta request
            def override_session():
                return SessionData(user_id, None, role)
            
            original = app.dependency_overrides.get(current_session)
            app.dependency_overrides[current_session] = override_session
            
            try:
                response = await call_next(request)
                return response
            finally:
                # Restaurar override original
                if original:
                    app.dependency_overrides[current_session] = original
                else:
                    # Default admin para otros tests
                    app.dependency_overrides[current_session] = lambda: SessionData(None, None, "admin")
        else:
            # Sin headers: dejar que el sistema maneje auth normalmente
            response = await call_next(request)
            return response


# Agregar middleware a app de tests
app.add_middleware(TestAuthMiddleware)

# Overrides globales inmediatos para cubrir clientes creados a nivel módulo
app.dependency_overrides[current_session] = lambda: SessionData(None, None, "admin")
app.dependency_overrides[require_csrf] = lambda: None


@pytest.fixture(autouse=True)
def _force_admin_and_disable_csrf(request):
    """Reafirma overrides por test para evitar contaminación entre módulos.
    Se desactiva si el test tiene marker 'no_auth_override'."""
    
    # Skip override si el test pide auth real
    if "no_auth_override" in request.keywords:
        # Limpiar override para que use auth real
        app.dependency_overrides.pop(current_session, None)
        app.dependency_overrides[require_csrf] = lambda: None
        yield
        # Restaurar default después del test
        app.dependency_overrides[current_session] = lambda: SessionData(None, None, "admin")
        return
    
    # Comportamiento normal: forzar admin
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
 

# -------- Clientes HTTP asíncronos para tests --------
@pytest_asyncio.fixture
async def client() -> AsyncGenerator[AsyncClient, None]:
    """Cliente HTTP async genérico con contexto admin."""
    async with AsyncClient(app=app, base_url="http://test") as ac:
        yield ac


@pytest_asyncio.fixture
async def client_admin() -> AsyncGenerator[AsyncClient, None]:
    """Cliente HTTP async con rol admin explícito."""
    async with AsyncClient(app=app, base_url="http://test") as ac:
        yield ac


@pytest_asyncio.fixture
async def client_collab() -> AsyncGenerator[AsyncClient, None]:
    """Cliente HTTP async con rol colaborador."""
    # Override temporal para este cliente
    original_override = app.dependency_overrides.get(current_session)
    app.dependency_overrides[current_session] = lambda: SessionData(None, None, "colaborador")
    
    async with AsyncClient(app=app, base_url="http://test") as ac:
        yield ac
    
    # Restaurar override original
    if original_override:
        app.dependency_overrides[current_session] = original_override
    else:
        app.dependency_overrides[current_session] = lambda: SessionData(None, None, "admin")


@pytest_asyncio.fixture
async def db() -> AsyncGenerator[AsyncSession, None]:
    """Alias de AsyncSession para tests que esperan 'db' en lugar de 'db_session'."""
    from db.session import SessionLocal
    async with SessionLocal() as session:
        yield session
