# NG-HEADER: Nombre de archivo: test_stock_ledger_basic.py
# NG-HEADER: Ubicación: tests/test_stock_ledger_basic.py
# NG-HEADER: Descripción: Pruebas básicas de creación de movimientos en StockLedger (venta y devolución)
# NG-HEADER: Lineamientos: Ver AGENTS.md
import pytest
from fastapi.testclient import TestClient
from services import api
from db.session import SessionLocal, engine
from sqlalchemy import text, select
from db.models import Product, StockLedger, SaleLine

client = TestClient(api.app)


def _create_product(title: str, stock: int, price: float) -> int:
    # SKU simple alfanumérico requerido por validación (evitar guiones si la política los rechaza)
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
async def test_stock_ledger_sale_and_return_flow():
    pid = _create_product("Prod Ledger", 20, 50)
    # Crear venta borrador
    r = client.post("/sales", json={
        "customer": {"name": "Cliente Ledger"},
        "items": [{"product_id": pid, "qty": 3, "unit_price": 50}],
    })
    assert r.status_code == 200, r.text
    sale_id = r.json()["sale_id"]
    # Confirmar
    rc = client.post(f"/sales/{sale_id}/confirm")
    assert rc.status_code == 200, rc.text
    # Verificar ledger - delta negativo
    async with SessionLocal() as s:  # type: ignore
        rows = (await s.execute(select(StockLedger).where(StockLedger.source_type=="sale", StockLedger.source_id==sale_id))).scalars().all()
        assert len(rows) == 1
        row = rows[0]
        assert row.delta == -3
        assert row.balance_after == 17

    # Devolver 2 unidades
    async with SessionLocal() as s:  # type: ignore
        line = (await s.execute(select(SaleLine).where(SaleLine.sale_id==sale_id))).scalars().first()
        line_id = line.id

    rret = client.post(f"/sales/{sale_id}/returns", json={
        "items": [{"sale_line_id": line_id, "qty": 2}],
        "reason": "ajuste test"
    })
    assert rret.status_code == 200, rret.text

    async with SessionLocal() as s:  # type: ignore
        rows = (await s.execute(select(StockLedger).where(StockLedger.source_type=="return", StockLedger.source_id==rret.json()["return_id"]))).scalars().all()
        assert len(rows) == 1
        row = rows[0]
        assert row.delta == 2
        assert row.balance_after == 19  # 17 + 2 devueltos
