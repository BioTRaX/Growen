# NG-HEADER: Nombre de archivo: test_price_lookup.py
# NG-HEADER: Ubicación: tests/test_price_lookup.py
# NG-HEADER: Descripción: Pruebas unitarias para extractor y ranking del lookup de productos
# NG-HEADER: Lineamientos: Ver AGENTS.md
import asyncio
import os
import uuid
from fastapi.testclient import TestClient

os.environ.setdefault("DB_URL", "sqlite+aiosqlite:///:memory:")

from services.api import app  # noqa: E402
from services.auth import SessionData, current_session, require_csrf  # noqa: E402
from services.chat.price_lookup import extract_product_query, resolve_product_info  # noqa: E402
from db.session import SessionLocal  # noqa: E402

client = TestClient(app)
app.dependency_overrides[current_session] = lambda: SessionData(None, None, "admin")
app.dependency_overrides[require_csrf] = lambda: None


def _create_supplier(slug: str, name: str) -> int:
    resp = client.post("/suppliers", json={"slug": slug, "name": name})
    assert resp.status_code in (200, 201)
    data = resp.json()
    if isinstance(data, dict) and "id" in data:
        return data["id"]
    suppliers = client.get("/suppliers").json()
    return suppliers[-1]["id"]


def _create_product(title: str, supplier_id: int, sku: str, sale_price: float, stock: int) -> dict:
    unique_sku = f"{sku}-{uuid.uuid4().hex[:4]}"
    payload = {
        "title": title,
        "initial_stock": stock,
        "supplier_id": supplier_id,
        "supplier_sku": unique_sku,
        "sku": unique_sku,
        "purchase_price": sale_price,
        "sale_price": sale_price,
    }
    resp = client.post("/catalog/products", json=payload)
    assert resp.status_code == 200, resp.text
    data = resp.json()
    data["unique_sku"] = payload["sku"]
    return data


def test_extract_product_query_stock_intent():
    query = extract_product_query("tenes vamp humuskashi 5630?")
    assert query is not None
    assert query.intent == "stock"
    assert any("5630" in sku for sku in query.sku_candidates)
    assert "vamp" in query.terms


def test_extract_product_query_command_detects_sku():
    query = extract_product_query("/stock 6584")
    assert query is not None
    assert query.intent == "stock"
    assert query.command == "stock"
    assert "6584" in query.sku_candidates


def test_extract_product_query_mixed_intent():
    query = extract_product_query("precio maceta soplada tenes?")
    assert query is not None
    assert query.intent == "mixed"
    assert "maceta" in query.terms


def test_resolve_product_info_prioritizes_stock():
    sup_id = _create_supplier("sup-rank", "Proveedor Ranking")
    _create_product("Kit Ranking Plus", sup_id, "KIT-R-1", 120.0, stock=5)
    _create_product("Kit Ranking Basic", sup_id, "KIT-R-2", 95.0, stock=0)

    query = extract_product_query("precio kit ranking")
    assert query is not None

    async def _run():
        async with SessionLocal() as session:
            result = await resolve_product_info(query, session)
            assert result.entries, result
            first = result.entries[0]
            assert first.stock_status != "out"
            assert first.name.lower().startswith("kit ranking")
            stocks = [entry.stock_status for entry in result.entries]
            assert "out" in stocks
    asyncio.run(_run())
