#!/usr/bin/env python
# NG-HEADER: Nombre de archivo: test_product_tags_api.py
# NG-HEADER: Ubicación: tests/test_product_tags_api.py
# NG-HEADER: Descripción: Pruebas de tags normalizados, búsqueda AND y sesión/CSRF reales.
# NG-HEADER: Lineamientos: Ver AGENTS.md
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select

from db.models import Product, ProductTag, Tag, User
from services.api import app
from services.auth import hash_pw


@pytest.mark.no_auth_override
@pytest.mark.asyncio
async def test_tags_require_real_session_csrf_and_search_by_tag(db_session) -> None:
    user = User(identifier="tags-admin", password_hash=hash_pw("segura-test-123"), role="admin")
    product = Product(sku_root="TAG-001", title="Maceta técnica", description_html="Uso interior")
    db_session.add_all([user, product])
    await db_session.commit()

    with TestClient(app) as client:
        login = client.post("/auth/login", json={"identifier": user.identifier, "password": "segura-test-123"})
        assert login.status_code == 200
        assert client.get("/auth/me").json()["is_authenticated"] is True

        assert client.post("/tags", json={"name": "  Cultivo   Interior "}).status_code == 403
        csrf = client.cookies.get("csrf_token")
        first = client.post("/tags", headers={"X-CSRF-Token": csrf}, json={"name": "  Cultivo   Interior "})
        duplicate = client.post("/tags", headers={"X-CSRF-Token": csrf}, json={"name": "cultivo interior"})
        assert first.status_code == duplicate.status_code == 200
        assert first.json()["id"] == duplicate.json()["id"]
        assigned = client.post(
            f"/tags/products/{product.id}/tags",
            headers={"X-CSRF-Token": csrf},
            json={"tag_names": ["Cultivo Interior", " CULTIVO INTERIOR "]},
        )
        assert assigned.status_code == 200, assigned.text
        found = client.get("/catalog/search", params={"q": "maceta interior"})
        assert found.status_code == 200
        assert [row["id"] for row in found.json()] == [product.id]
        assert found.json()[0]["tags"] == ["#Cultivo Interior"]

    assert await db_session.scalar(select(func.count(Tag.id))) == 1
    assert await db_session.scalar(select(func.count(ProductTag.product_id))) == 1
