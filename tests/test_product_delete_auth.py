#!/usr/bin/env python
# NG-HEADER: Nombre de archivo: test_product_delete_auth.py
# NG-HEADER: Ubicación: tests/test_product_delete_auth.py
# NG-HEADER: Descripción: Regresión de autorización real para el borrado protegido de productos.
# NG-HEADER: Lineamientos: Ver AGENTS.md

import pytest
from fastapi.testclient import TestClient

from db.models import Product, User
from services.api import app
from services.auth import hash_pw


@pytest.mark.no_auth_override
@pytest.mark.asyncio
async def test_cliente_no_puede_borrar_producto_con_sesion_y_csrf_reales(db_session):
    user = User(
        identifier="cliente-delete-product-test",
        password_hash=hash_pw("segura-test-123"),
        role="cliente",
    )
    product = Product(sku_root="DELETE-AUTH", title="Producto protegido", stock=0)
    db_session.add_all([user, product])
    await db_session.commit()

    with TestClient(app) as client:
        login = client.post(
            "/auth/login",
            json={"identifier": user.identifier, "password": "segura-test-123"},
        )
        assert login.status_code == 200

        current = client.get("/auth/me")
        assert current.status_code == 200
        assert current.json()["role"] == "cliente"

        csrf = client.cookies.get("csrf_token")
        response = client.request(
            "DELETE",
            "/catalog/products",
            headers={"X-CSRF-Token": csrf},
            json={"ids": [product.id]},
        )
        assert response.status_code == 403
