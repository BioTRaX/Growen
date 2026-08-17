# NG-HEADER: Nombre de archivo: test_price_lookup.py
# NG-HEADER: Ubicación: tests/test_price_lookup.py
# NG-HEADER: Descripción: Pruebas unitarias para extractor y ranking del lookup de productos
# NG-HEADER: Lineamientos: Ver AGENTS.md
import uuid
import pytest

from services.chat.price_lookup import (
    ProductEntry,
    ProductLookupResult,
    ProductQuery,
    extract_product_query,
    render_product_response_for_role,
    resolve_product_info,
)

async def _create_supplier(client, slug: str, name: str) -> int:
    resp = await client.post("/suppliers", json={"slug": slug, "name": name})
    assert resp.status_code in (200, 201)
    data = resp.json()
    if isinstance(data, dict) and "id" in data:
        return data["id"]
    suppliers = (await client.get("/suppliers")).json()
    return suppliers[-1]["id"]


async def _create_product(client, title: str, supplier_id: int, sku: str, sale_price: float, stock: int) -> dict:
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
    resp = await client.post("/catalog/products", json=payload)
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


@pytest.mark.asyncio
async def test_resolve_product_info_prioritizes_stock(client):
    from db.session import SessionLocal
    sup_id = await _create_supplier(client, "sup-rank", "Proveedor Ranking")
    await _create_product(client, "Kit Ranking Plus", sup_id, "KIT-R-1", 120.0, stock=5)
    await _create_product(client, "Kit Ranking Basic", sup_id, "KIT-R-2", 95.0, stock=0)

    query = extract_product_query("precio kit ranking")
    assert query is not None

    async with SessionLocal() as session:
        result = await resolve_product_info(query, session)
        assert result.entries, result
        first = result.entries[0]
        assert first.stock_status != "out"
        assert first.name.lower().startswith("kit ranking")
        stocks = [entry.stock_status for entry in result.entries]
        assert "out" in stocks

def test_extract_product_query_ignores_smalltalk():
    assert extract_product_query('Hola como estas?') is None
    assert extract_product_query('Hola, ¿estás funcionando?') is None


@pytest.mark.parametrize(
    "message",
    (
        "Contame un chiste",
        "Necesito ayuda con mi cultivo",
        "¿Quién sos?",
        "Gracias, funciona perfecto",
    ),
)
def test_extract_product_query_requires_explicit_product_signal(message):
    assert extract_product_query(message) is None


def test_extract_product_query_keeps_explicit_catalog_queries():
    assert extract_product_query("precio de maceta soplada") is not None
    assert extract_product_query("hay stock de sustrato?") is not None
    assert extract_product_query("información del producto 6584") is not None


def test_extract_product_query_does_not_match_keyword_substrings():
    assert extract_product_query("Preparame un informe general") is None
    assert extract_product_query("Estoy disponible para continuar") is None


def test_public_product_response_hides_operational_fields():
    query = ProductQuery("precio maceta", "precio maceta", ["maceta"], [], True, False, "price")
    entry = ProductEntry(
        name="Maceta de prueba",
        price=100,
        currency="ARS",
        source_detail="test",
        stock_qty=17,
        stock_status="ok",
        supplier_name="Proveedor privado",
        sku="SKU-PRIVADO",
    )
    result = ProductLookupResult(query=query, status="ok", entries=[entry])

    rendered = render_product_response_for_role(result, "guest")

    assert "ARS 100,00" in rendered
    assert "disponibilidad" in rendered.lower()
    assert "17" not in rendered
    assert "SKU-PRIVADO" not in rendered
    assert "Proveedor privado" not in rendered


def test_extract_product_query_ignores_recommendations():
    assert extract_product_query('puedes recomendarme un sustrato?') is None
