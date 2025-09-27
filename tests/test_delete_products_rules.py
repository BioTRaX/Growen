# NG-HEADER: Nombre de archivo: test_delete_products_rules.py
# NG-HEADER: Ubicación: tests/test_delete_products_rules.py
# NG-HEADER: Descripción: Pruebas para reglas de eliminación de productos
# NG-HEADER: Lineamientos: Ver AGENTS.md

import os
import pytest
from fastapi.testclient import TestClient
from services.api import app
from services.auth import current_session, require_csrf, SessionData
from db.session import SessionLocal
from db.models import Product, Variant, Inventory, Purchase, PurchaseLine, Supplier
import uuid

client = TestClient(app)
app.dependency_overrides[current_session] = lambda: SessionData(None, None, "admin")
app.dependency_overrides[require_csrf] = lambda: None

@pytest.mark.asyncio
async def _create_product_with_stock(stock: int = 1) -> int:
    async with SessionLocal() as s:
        sku = f"PX-{uuid.uuid4().hex[:6]}"
        p = Product(sku_root=sku, title=f"Prod X {uuid.uuid4().hex[:6]}", stock=stock)
        s.add(p)
        await s.flush()
        v = Variant(product_id=p.id, sku=sku)
        s.add(v)
        await s.flush()
        inv = Inventory(variant_id=v.id, stock_qty=stock)
        s.add(inv)
        await s.commit()
        return p.id

@pytest.mark.asyncio
async def _create_purchase_referencing_product(pid: int) -> None:
    async with SessionLocal() as s:
        su = uuid.uuid4().hex[:6]
        sup = Supplier(slug=f"sdel-{su}", name=f"S Del {su}")
        s.add(sup)
        await s.flush()
        pur = Purchase(supplier_id=sup.id, remito_number="R-DEL", remito_date=__import__("datetime").date.today())
        s.add(pur)
        await s.flush()
        s.add(PurchaseLine(purchase_id=pur.id, product_id=pid, qty=1, unit_cost=1, title="Ref prod"))
        await s.commit()


@pytest.mark.asyncio
async def test_delete_blocked_by_stock():
    pid = await _create_product_with_stock(2)
    r = client.request("DELETE", "/catalog/products", json={"ids": [pid]})
    assert r.status_code == 400


@pytest.mark.asyncio
async def test_delete_blocked_by_refs():
    pid = await _create_product_with_stock(0)
    await _create_purchase_referencing_product(pid)
    r = client.request("DELETE", "/catalog/products", json={"ids": [pid]})
    assert r.status_code == 409


@pytest.mark.asyncio
async def test_delete_success():
    pid = await _create_product_with_stock(0)
    r = client.request("DELETE", "/catalog/products", json={"ids": [pid]})
    assert r.status_code == 200
    data = r.json()
    assert pid in data["deleted"]
