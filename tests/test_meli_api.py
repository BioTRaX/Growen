#!/usr/bin/env python
# NG-HEADER: Nombre de archivo: test_meli_api.py
# NG-HEADER: Ubicación: tests/test_meli_api.py
# NG-HEADER: Descripción: Pruebas de autorización base para la API administrativa MeLi.
# NG-HEADER: Lineamientos: Ver AGENTS.md

from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient
import httpx
import pytest

from services.routers.meli import router


@pytest.mark.asyncio
async def test_meli_admin_mutations_reject_anonymous_requests() -> None:
    app = FastAPI()
    app.include_router(router)
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://api"
    ) as client:
        oauth = await client.post("/integrations/meli/oauth/authorizations")
        link = await client.post(
            "/integrations/meli/item-links",
            json={"account_id": 1, "product_id": 1, "item_id": "MLA123"},
        )
    assert oauth.status_code in {401, 403}
    assert link.status_code in {401, 403}


@pytest.mark.no_auth_override
@pytest.mark.asyncio
async def test_meli_item_link_uses_real_admin_session_and_csrf(db_session) -> None:
    from db.models import User
    from services.api import app as main_app
    from services.auth import hash_pw

    user = User(
        identifier="admin-meli-session",
        password_hash=hash_pw("segura-test-123"),
        role="admin",
    )
    db_session.add(user)
    await db_session.commit()
    payload = {"account_id": 999, "product_id": 999, "item_id": "MLA123"}
    with TestClient(main_app) as client:
        login = client.post(
            "/auth/login",
            json={"identifier": user.identifier, "password": "segura-test-123"},
        )
        assert login.status_code == 200
        assert client.get("/auth/me").json()["role"] == "admin"
        assert client.post("/integrations/meli/item-links", json=payload).status_code == 403
        csrf = client.cookies.get("csrf_token")
        response = client.post(
            "/integrations/meli/item-links",
            json=payload,
            headers={"X-CSRF-Token": csrf},
        )
    assert response.status_code == 404
    assert response.json()["detail"] == "meli_account_not_found"
