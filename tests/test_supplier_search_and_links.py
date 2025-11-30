# NG-HEADER: Nombre de archivo: test_supplier_search_and_links.py
# NG-HEADER: Ubicación: tests/test_supplier_search_and_links.py
# NG-HEADER: Descripción: Tests de endpoints suppliers/search, variants sku update y supplier-products link
# NG-HEADER: Lineamientos: Ver AGENTS.md
import json
import pytest
from httpx import AsyncClient, ASGITransport
from pathlib import Path

import services.api as api
from services.auth import require_csrf as _require_csrf, require_roles as _require_roles

@pytest.mark.asyncio
async def test_supplier_search_and_links_flow(monkeypatch):
    app = api.app

    # Utilidades mock de auth: bypass CSRF y roles para pruebas
    async def ok_csrf():
        return True
    async def ok_roles():
        return True
    app.dependency_overrides[_require_csrf] = ok_csrf
    # Simular sesión admin para pasar require_roles en endpoints protegidos
    async def fake_current_session():
        from services.auth import SessionData
        return SessionData(None, None, "admin")
    from services.auth import current_session as _current_session
    app.dependency_overrides[_current_session] = fake_current_session

    # La fixture de conftest se encarga de la DB
    from db.session import SessionLocal
    from sqlalchemy import text
    async with SessionLocal() as s:  # type: ignore
        # Insertar datos
        from secrets import token_hex
        slug = f"santaplanta_{token_hex(3)}"
        await s.execute(text("INSERT INTO suppliers (slug, name, created_at) VALUES (:slug,'Santa Planta', CURRENT_TIMESTAMP)").bindparams(slug=slug))
        await s.execute(text("INSERT INTO products (sku_root, title, created_at, updated_at, stock) VALUES ('SKU-ROOT','Producto X', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP, 0)"))
        await s.execute(text("INSERT INTO variants (product_id, sku, created_at, updated_at) VALUES (1,'SKU-ROOT', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)"))
        await s.commit()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # Buscar supplier por nombre
        r = await client.get("/suppliers/search", params={"q": "Santa"})
        assert r.status_code == 200
        data = r.json()
        assert any(x["name"] == "Santa Planta" or x["slug"].startswith("santaplanta") for x in data)

        # Actualizar SKU de la variante
        r = await client.put("/variants/1/sku", json={"sku": "SKU-NEW-01"})
        assert r.status_code == 200
        assert r.json()["sku"] == "SKU-NEW-01"

        # Intentar duplicado de SKU
        # Crear otra variante con ese SKU root para probar conflicto
        async with SessionLocal() as s:  # type: ignore
            await s.execute(text("INSERT INTO products (sku_root, title, created_at, updated_at, stock) VALUES ('P2','P2', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP, 0)"))
            await s.execute(text("INSERT INTO variants (product_id, sku, created_at, updated_at) VALUES (2,'SKU-OTHER', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)"))
            await s.commit()
        # Cambiar a SKU existente
        r = await client.put("/variants/2/sku", json={"sku": "SKU-NEW-01"})
        assert r.status_code == 409

        # Linkear supplier product a variant 1
        r = await client.post("/supplier-products/link", json={
            "supplier_id": 1,
            "supplier_product_id": "C123",
            "internal_variant_id": 1,
            "title": "Cosa 5L"
        })
        assert r.status_code == 200
        sp = r.json()
        assert sp["supplier_id"] == 1
        assert sp["supplier_product_id"] == "C123"
        assert sp["internal_variant_id"] == 1

        # Upsert (actualización): cambiar variant a 2
        r = await client.post("/supplier-products/link", json={
            "supplier_id": 1,
            "supplier_product_id": "C123",
            "internal_variant_id": 2,
        })
        assert r.status_code == 200
        sp = r.json()
        assert sp["internal_variant_id"] == 2

    # Limpiar overrides
    app.dependency_overrides = {}
