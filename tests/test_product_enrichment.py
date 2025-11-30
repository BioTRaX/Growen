# NG-HEADER: Nombre de archivo: test_product_enrichment.py
# NG-HEADER: Ubicación: tests/test_product_enrichment.py
# NG-HEADER: Descripción: Pruebas rápidas de enriquecimiento: force/reenrich, delete y bulk.
# NG-HEADER: Lineamientos: Ver AGENTS.md
import os
import json
import pytest
import asyncio
import httpx
from httpx import ASGITransport
import time
from unittest.mock import patch, AsyncMock
from fastapi.testclient import TestClient

# Configuración mínima de entorno para tests
os.environ.setdefault("DB_URL", "sqlite+aiosqlite:///:memory:")
os.environ.setdefault("SECRET_KEY", "test")
os.environ.setdefault("ADMIN_PASS", "test")
os.environ.setdefault("AUTH_ENABLED", "true")
os.environ.setdefault("MEDIA_ROOT", "./ImagenesTest")
os.environ.setdefault("AI_DISABLE_OLLAMA", "1")  # evita depender de daemon local

from services.api import app
from services.auth import SessionData, current_session, require_csrf
from db.models import Product
from db.session import SessionLocal, engine
from db.base import Base

client = TestClient(app)
app.dependency_overrides[current_session] = lambda: SessionData(None, None, "admin")
app.dependency_overrides[require_csrf] = lambda: None


def _mock_web_search_response():
    """Mock response del servicio MCP Web Search"""
    return {
        "status": "success",
        "results": [
            {
                "title": "Producto Test",
                "url": "https://example.com/producto",
                "snippet": "Descripción del producto de prueba"
            }
        ]
    }


@pytest.fixture(scope="function", autouse=True)
async def setup_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


# Skip message para tests que requieren MCP Web Search
MCP_WEB_SEARCH_SKIP = pytest.mark.skip(
    reason="Requiere servicio MCP Web Search (mcp_web_search:8002) - ejecutar con Docker Compose"
)


@MCP_WEB_SEARCH_SKIP
@pytest.mark.asyncio
async def test_enrich_force_and_delete(monkeypatch):
    # Forzar IA a devolver JSON válido
    from ai.router import AIRouter
    def _fake_run(self, task, prompt: str) -> str:
        data = {
            "Descripción para Nice Grow": "Descripción breve del producto.",
            "Fuentes": {"Manual": "https://example.com/manual.pdf"},
            "Peso KG": 1.2,
            "Alto CM": 10,
            "Ancho CM": 5,
            "Profundidad CM": 2,
            "Valor de mercado estimado": "999.99",
        }
        return json.dumps(data)
    monkeypatch.setattr(AIRouter, "run", _fake_run)

    # Crear producto
    async with SessionLocal() as db:
        p = Product(sku_root="SKU1", title="Producto X")
        db.add(p)
        await db.commit()
        await db.refresh(p)
        pid = p.id

    # Enrich inicial
    r = client.post(f"/products/{pid}/enrich")
    assert r.status_code == 200, r.text
    data = r.json()
    assert data.get("status") == "ok"
    # Verificar que GET devuelve descripción y sources_url
    g = client.get(f"/products/{pid}")
    assert g.status_code == 200
    prod = g.json()
    assert prod.get("description_html")
    first_url = prod.get("enrichment_sources_url")

    # Reenrich (force=true)
    r2 = client.post(f"/products/{pid}/enrich?force=true")
    assert r2.status_code == 200, r2.text
    g2 = client.get(f"/products/{pid}")
    assert g2.status_code == 200
    prod2 = g2.json()
    # Debe persistir descripción, y potentially cambiar la URL (puede coincidir si cae mismo segundo)
    assert prod2.get("description_html")
    # Limpieza: eliminar enriquecimiento
    r3 = client.delete(f"/products/{pid}/enrichment")
    assert r3.status_code == 200
    g3 = client.get(f"/products/{pid}")
    pr3 = g3.json()
    assert pr3.get("description_html") in (None, "")
    assert pr3.get("enrichment_sources_url") in (None, "")
    # Campos técnicos
    assert pr3.get("weight_kg") is None
    assert pr3.get("height_cm") is None
    assert pr3.get("width_cm") is None
    assert pr3.get("depth_cm") is None
    assert pr3.get("market_price_reference") is None


@MCP_WEB_SEARCH_SKIP
@pytest.mark.asyncio
async def test_enrich_multiple_mixed(monkeypatch):
    # IA fake JSON
    from ai.router import AIRouter
    monkeypatch.setattr(
        AIRouter,
        "run",
        lambda self, task, prompt: json.dumps({"Descripción para Nice Grow": "Texto.", "Fuentes": {"Ref": "https://ref.example"}}),
    )

    # Crear 3 productos: uno OK, uno sin título, uno ya enriquecido
    async with SessionLocal() as db:
        p1 = Product(sku_root="A", title="Prod A")
        p2 = Product(sku_root="B", title="")
        p3 = Product(sku_root="C", title="Prod C", description_html="ya tiene")
        db.add_all([p1, p2, p3])
        await db.commit()
        await db.refresh(p1); await db.refresh(p2); await db.refresh(p3)
        ids = [p1.id, p2.id, p3.id]

    r = client.post("/products/enrich-multiple", json={"ids": ids})
    assert r.status_code == 200, r.text
    out = r.json()
    # p1 enriquecido, p2 sin título (skip), p3 ya enriquecido (skip)
    assert out.get("enriched") == 1
    assert out.get("skipped") == 2


@MCP_WEB_SEARCH_SKIP
@pytest.mark.asyncio
async def test_enrich_concurrency_lock(monkeypatch):
    """Verifica que el bloqueo de concurrencia funciona."""
    from ai.router import AIRouter

    # Mock de AIRouter.run para simular un proceso largo y síncrono
    def _delayed_run(self, task, prompt: str) -> str:
        time.sleep(0.4)
        return json.dumps({"Descripción para Nice Grow": "Descripción final."})

    monkeypatch.setattr(AIRouter, "run", _delayed_run)

    # Crear un producto para el test
    async with SessionLocal() as db:
        p = Product(sku_root="SKU_CONCUR", title="Producto Concurrente")
        db.add(p)
        await db.commit()
        await db.refresh(p)
        pid = p.id

    # Usar un cliente asíncrono para llamadas concurrentes
    # FastAPI corre el endpoint síncrono en un threadpool, permitiendo que el event loop
    # procese otras corutinas (como la segunda request) en paralelo.
    async with httpx.AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as aclient:
        # Lanzar dos llamadas de enriquecimiento al mismo tiempo
        task1 = aclient.post(f"/products/{pid}/enrich")
        # Pequeña demora para asegurar que la primera llamada llegue al servidor y adquiera el bloqueo
        await asyncio.sleep(0.1)
        task2 = aclient.post(f"/products/{pid}/enrich")

        responses = await asyncio.gather(task1, task2)

        # Verificar que una tuvo éxito (200) y la otra fue rechazada (409)
        status_codes = sorted([res.status_code for res in responses])
        assert status_codes == [200, 409]

    # Verificar que el producto final no está bloqueado
    async with SessionLocal() as db:
        p_final = await db.get(Product, pid)
        assert p_final is not None
        assert not p_final.is_enriching
        # Y que la descripción fue actualizada por la llamada exitosa
        assert p_final.description_html == "Descripción final."
