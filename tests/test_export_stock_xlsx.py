#!/usr/bin/env python
# NG-HEADER: Nombre de archivo: test_export_stock_xlsx.py
# NG-HEADER: Ubicación: tests/test_export_stock_xlsx.py
# NG-HEADER: Descripción: Pruebas del exportador XLS de stock (prioridad canónica y estilos básicos).
# NG-HEADER: Lineamientos: Ver AGENTS.md
import io
import os
import asyncio

# Forzar entorno de pruebas aislado (SQLite en memoria)
os.environ["DB_URL"] = "sqlite+aiosqlite:///:memory:"
os.environ["SECRET_KEY"] = "test"
os.environ["AUTH_ENABLED"] = "true"

from fastapi.testclient import TestClient
from openpyxl import load_workbook

from services.api import app
from services.auth import current_session, require_csrf, SessionData
from db.base import Base
from db.session import engine, SessionLocal
from db.models import Product, Supplier, SupplierProduct, ProductEquivalence, CanonicalProduct


async def _init_db() -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


asyncio.get_event_loop().run_until_complete(_init_db())

client = TestClient(app)
app.dependency_overrides[current_session] = lambda: SessionData(None, None, "admin")
app.dependency_overrides[require_csrf] = lambda: None


def _seed_basic():
    async def _tx():
        async with SessionLocal() as s:  # type: ignore
            sup = Supplier(slug="acme", name="ACME")
            s.add(sup)
            await s.flush()
            p = Product(sku_root="SKU1", title="Producto X")
            s.add(p)
            await s.flush()
            sp = SupplierProduct(supplier_id=sup.id, supplier_product_id="P1", title="Prod X", internal_product_id=p.id)
            sp.current_sale_price = 123.45
            s.add(sp)
            await s.flush()
            cp = CanonicalProduct(name="Canon X", sku_custom="AAA_0001_BBB")
            cp.sale_price = 99.99
            s.add(cp)
            await s.flush()
            eq = ProductEquivalence(supplier_id=sup.id, supplier_product_id=sp.id, canonical_product_id=cp.id, source="test")
            s.add(eq)
            await s.commit()
            return p.id
    return asyncio.get_event_loop().run_until_complete(_tx())


def test_exporter_prefers_canonical_and_styles_header():
    pid = _seed_basic()
    r = client.get("/stock/export.xlsx")
    assert r.status_code == 200
    content = r.content
    wb = load_workbook(io.BytesIO(content))
    ws = wb.active
    # Encabezados
    headers = [c.value for c in ws[1]]
    assert headers == ["NOMBRE DE PRODUCTO", "PRECIO DE VENTA", "CATEGORIA", "SKU PROPIO"]
    # Buscar la fila del producto sembrado (Canon X)
    found = None
    for r in range(2, ws.max_row + 1):
        if ws.cell(row=r, column=1).value == "Canon X":
            found = r
            break
    assert found is not None, "No se encontró la fila de Canon X en el XLS"
    assert float(ws.cell(row=found, column=2).value) == 99.99  # precio canónico domina
    # Estilo básico del header (negrita)
    assert ws.cell(row=1, column=1).font.bold is True
