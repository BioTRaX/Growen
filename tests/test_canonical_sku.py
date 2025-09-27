#!/usr/bin/env python
# NG-HEADER: Nombre de archivo: test_canonical_sku.py
# NG-HEADER: Ubicación: tests/test_canonical_sku.py
# NG-HEADER: Descripción: Pruebas de creación y validación del SKU canónico.
# NG-HEADER: Lineamientos: Ver AGENTS.md
import os
import uuid
import pytest
from fastapi.testclient import TestClient

os.environ.setdefault("AUTH_ENABLED", "false")

from services.api import app  # noqa: E402

client = TestClient(app)


def _create_supplier() -> int:
    u = uuid.uuid4().hex[:6]
    r = client.post("/suppliers", json={"slug": f"canon-sup-{u}", "name": f"Canon Sup {u}"})
    assert r.status_code in (200, 201, 409)
    if r.status_code in (200, 201):
        return r.json()["id"]
    # fallback: lista
    ls = client.get("/suppliers").json()
    assert ls and isinstance(ls, list)
    return ls[0]["id"]


def test_create_product_with_valid_canonical_sku():
    sup_id = _create_supplier()
    # Generar 3 SKUs válidos dinámicos
    skus = []
    for tag in ("A", "B", "C"):
        u = uuid.uuid4().hex[:6].upper()
        num = int(u[:4], 16) % 9999
        skus.append(f"{tag}{tag}{tag}_{num:04d}_{u[:3]}")
    for sku in skus:
        payload = {
            "title": f"Producto {sku}",
            "initial_stock": 1,
            "supplier_id": sup_id,
            "supplier_sku": f"SUP-{sku}",
            "sku": sku,
        }
        r = client.post("/catalog/products", json=payload, headers={"X-CSRF-Token": "x"})
        assert r.status_code in (200, 201), r.text
        body = r.json()
        assert body["sku_root"] == sku


@pytest.mark.parametrize("sku", ["abc_0001_def", "AB_0001_DEF", "ABCD_0001_DEF", "ABC_001_DEF", "ABC_0001_DEFG", "ABC0001DEF"])
def test_create_product_with_invalid_canonical_sku_rejected(sku):
    sup_id = _create_supplier()
    payload = {
        "title": f"Prod invalido {sku}",
        "initial_stock": 0,
        "supplier_id": sup_id,
        "supplier_sku": f"SUP-{sku}",
        "sku": sku,
    }
    r = client.post("/catalog/products", json=payload, headers={"X-CSRF-Token": "x"})
    assert r.status_code == 422, r.text
    data = r.json()
    # Puede venir como detail dict o error Pydantic extra; aceptamos patrón principal
    assert data.get("detail")


def test_duplicate_supplier_sku_same_supplier_conflict():
    sup_id = _create_supplier()
    sku = "DUP_0001_X1A"
    base_payload = {
        "title": "Producto duplicado",
        "initial_stock": 0,
        "supplier_id": sup_id,
        "supplier_sku": "SUP-DUP-1",
        "sku": sku,
    }
    r1 = client.post("/catalog/products", json=base_payload, headers={"X-CSRF-Token": "x"})
    assert r1.status_code in (200, 201), r1.text
    # Repetimos misma pareja supplier_id + supplier_sku (aunque sku sea igual)
    r2 = client.post("/catalog/products", json=base_payload, headers={"X-CSRF-Token": "x"})
    assert r2.status_code == 409, r2.text
    jd = r2.json()
    # Puede venir detail dict (nuevo) o legacy
    if isinstance(jd.get("detail"), dict):
        assert jd["detail"].get("code") in ("duplicate_supplier_sku", "duplicate_sku")
    else:
        assert jd.get("code") in ("duplicate_supplier_sku", "duplicate_sku")


def test_same_canonical_sku_second_supplier_links_product():
    sku = "LNK_0001_ABC"
    sup1 = _create_supplier()
    sup2 = _create_supplier()
    p1 = {
        "title": "Prod link 1",
        "initial_stock": 0,
        "supplier_id": sup1,
        "supplier_sku": "SUP-LINK-1",
        "sku": sku,
    }
    r1 = client.post("/catalog/products", json=p1, headers={"X-CSRF-Token": "x"})
    assert r1.status_code in (200, 201), r1.text
    p2 = {
        "title": "Prod link 2",  # título diferente no debe crear producto nuevo
        "initial_stock": 0,
        "supplier_id": sup2,
        "supplier_sku": "SUP-LINK-2",
        "sku": sku,
    }
    r2 = client.post("/catalog/products", json=p2, headers={"X-CSRF-Token": "x"})
    # Debe vincular y devolver 200 (no duplicar variant) según lógica actual
    assert r2.status_code == 200, r2.text
    body = r2.json()
    assert body.get("linked") is True
