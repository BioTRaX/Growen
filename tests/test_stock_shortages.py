# NG-HEADER: Nombre de archivo: test_stock_shortages.py
# NG-HEADER: Ubicación: tests/test_stock_shortages.py
# NG-HEADER: Descripción: Pruebas de faltantes de stock (shortages) - creación, listado y estadísticas
# NG-HEADER: Lineamientos: Ver AGENTS.md
import pytest
from fastapi.testclient import TestClient
from services import api
from db.session import SessionLocal
from sqlalchemy import select
from db.models import Product, StockShortage, StockLedger

client = TestClient(api.app)


def _create_product(title: str, stock: int, price: float) -> int:
    """Crear producto auxiliar para los tests."""
    sku_root = ''.join(ch for ch in title.upper() if ch.isalnum())[:12] or 'SKU1'
    r = client.post("/catalog/products", json={
        "title": title,
        "sku": sku_root,
        "initial_stock": stock,
        "sale_price": price
    })
    assert r.status_code == 200, r.text
    return r.json()["id"]


@pytest.mark.asyncio
async def test_create_shortage_success():
    """Crear faltante debe descontar stock del producto."""
    pid = _create_product("Prod Shortage Test", 50, 100)
    
    r = client.post("/stock/shortages", json={
        "product_id": pid,
        "quantity": 5,
        "reason": "GIFT",
        "observation": "Muestra para cliente"
    })
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["product_id"] == pid
    assert data["quantity"] == 5
    assert data["new_stock"] == 45  # 50 - 5
    assert "warning" not in data
    
    # Verificar stock en DB
    async with SessionLocal() as s:
        prod = await s.get(Product, pid)
        assert prod.stock == 45


@pytest.mark.asyncio
async def test_create_shortage_records_ledger():
    """Crear faltante debe registrar movimiento en StockLedger."""
    pid = _create_product("Prod Ledger Short", 30, 80)
    
    r = client.post("/stock/shortages", json={
        "product_id": pid,
        "quantity": 3,
        "reason": "UNKNOWN"
    })
    assert r.status_code == 200
    shortage_id = r.json()["id"]
    
    # Verificar ledger
    async with SessionLocal() as s:
        rows = (await s.execute(
            select(StockLedger)
            .where(StockLedger.source_type == "shortage")
            .where(StockLedger.source_id == shortage_id)
        )).scalars().all()
        assert len(rows) == 1
        ledger = rows[0]
        assert ledger.delta == -3
        assert ledger.balance_after == 27  # 30 - 3


@pytest.mark.asyncio
async def test_create_shortage_negative_stock_allowed():
    """Stock puede quedar negativo con warning."""
    pid = _create_product("Prod Negative", 5, 50)
    
    r = client.post("/stock/shortages", json={
        "product_id": pid,
        "quantity": 10,  # Más de lo disponible
        "reason": "PENDING_SALE"
    })
    assert r.status_code == 200
    data = r.json()
    assert data["new_stock"] == -5  # 5 - 10
    assert "warning" in data
    assert "-5" in data["warning"]


def test_list_shortages_with_filters():
    """Listado paginado con filtros funciona correctamente."""
    # Crear algunos faltantes
    pid = _create_product("Prod List Test", 100, 50)
    for reason in ["GIFT", "UNKNOWN", "GIFT"]:
        client.post("/stock/shortages", json={
            "product_id": pid,
            "quantity": 1,
            "reason": reason
        })
    
    # Listar todos
    r = client.get("/stock/shortages")
    assert r.status_code == 200
    data = r.json()
    assert "items" in data
    assert "total" in data
    assert data["total"] >= 3
    
    # Listar solo GIFT
    r = client.get("/stock/shortages?reason=GIFT")
    assert r.status_code == 200
    for item in r.json()["items"]:
        assert item["reason"] == "GIFT"


def test_shortages_stats():
    """Estadísticas devuelven datos correctos."""
    r = client.get("/stock/shortages/stats")
    assert r.status_code == 200
    data = r.json()
    assert "total_items" in data
    assert "total_quantity" in data
    assert "by_reason" in data
    assert "this_month" in data
    assert isinstance(data["by_reason"], dict)


def test_create_shortage_invalid_product():
    """Error 404 si el producto no existe."""
    r = client.post("/stock/shortages", json={
        "product_id": 99999,
        "quantity": 1,
        "reason": "GIFT"
    })
    assert r.status_code == 404


def test_create_shortage_invalid_reason():
    """Error 422 si el motivo es inválido."""
    pid = _create_product("Prod Invalid Reason", 10, 20)
    r = client.post("/stock/shortages", json={
        "product_id": pid,
        "quantity": 1,
        "reason": "INVALID_REASON"
    })
    assert r.status_code == 422
