#!/usr/bin/env python
# NG-HEADER: Nombre de archivo: test_meli_stock_worker.py
# NG-HEADER: Ubicación: tests/test_meli_stock_worker.py
# NG-HEADER: Descripción: Pruebas de stock clásico y procesamiento dedicado del worker MeLi.
# NG-HEADER: Lineamientos: Ver AGENTS.md

from __future__ import annotations

from datetime import datetime, timedelta
from decimal import Decimal

import pytest
from sqlalchemy import select

from db.models import MeliAccount, MeliItemLink, MeliSyncJob, Product
from services.meli.crypto import TokenCipher


def test_build_stock_payload_supports_simple_item_and_variation() -> None:
    """Detecta que se publique una forma de payload incorrecta para variaciones."""
    from services.meli.stock import build_stock_payload

    assert build_stock_payload({"id": "MLA1", "seller_id": 42}, variation_id=None, quantity=Decimal("6")) == {
        "available_quantity": 6
    }
    assert build_stock_payload(
        {"id": "MLA1", "seller_id": 42, "variations": [{"id": 99}]},
        variation_id=99,
        quantity=Decimal("3"),
    ) == {"variations": [{"id": 99, "available_quantity": 3}]}


def test_build_stock_payload_fails_closed_for_multiwarehouse() -> None:
    """Detecta éxito falso al intentar /items sobre inventario multiorigen."""
    from services.meli.stock import MeliStockError, build_stock_payload

    with pytest.raises(MeliStockError, match="unsupported_multiwarehouse"):
        build_stock_payload(
            {"id": "MLA1", "seller_id": 42, "user_product_id": "MLAU1"},
            variation_id=None,
            quantity=Decimal("5"),
        )


class FakeStockClient:
    def __init__(self) -> None:
        self.updated: list[tuple[str, dict, str]] = []

    async def get_resource(self, resource: str, access_token: str) -> dict:
        assert resource == "/items/MLA123"
        assert access_token == "access-opaco"
        return {"id": "MLA123", "seller_id": 42, "available_quantity": 1}

    async def update_item(self, item_id: str, payload: dict, access_token: str) -> dict:
        self.updated.append((item_id, payload, access_token))
        return {"id": item_id, "seller_id": 42, "available_quantity": payload["available_quantity"]}

    async def refresh_token(self, refresh_token: str) -> dict:
        raise AssertionError("el token vigente no debe refrescarse")


@pytest.mark.asyncio
async def test_stock_job_updates_meli_from_growen_and_persists_result(db_session) -> None:
    """Detecta que el job termine sin publicar o sin guardar la cantidad confirmada."""
    from services.meli.stock import sync_stock_link

    cipher = TokenCipher(b"s" * 32)
    account = MeliAccount(
        application_id="123456",
        seller_id=42,
        access_token_ciphertext=cipher.encrypt("access-opaco", purpose="access", account_ref="42"),
        refresh_token_ciphertext=cipher.encrypt("refresh-opaco", purpose="refresh", account_ref="42"),
        token_expires_at=datetime.utcnow() + timedelta(hours=2),
    )
    product = Product(title="Producto MeLi", sku_root="MELI-TST", stock=Decimal("7"))
    db_session.add_all([account, product])
    await db_session.flush()
    link = MeliItemLink(account_id=account.id, product_id=product.id, item_id="MLA123")
    db_session.add(link)
    await db_session.commit()

    result = await sync_stock_link(db_session, link_id=link.id, client=FakeStockClient(), cipher=cipher)

    await db_session.refresh(link)
    assert result.quantity == 7
    assert link.last_synced_quantity == Decimal("7.00")
    assert link.last_error_code is None


@pytest.mark.asyncio
async def test_create_stock_job_deduplicates_active_link_work(db_session) -> None:
    """Detecta múltiples actualizaciones activas del mismo vínculo."""
    from services.meli.jobs import enqueue_stock_sync

    account = MeliAccount(
        application_id="123456",
        seller_id=42,
        access_token_ciphertext="a",
        refresh_token_ciphertext="r",
        token_expires_at=datetime.utcnow() + timedelta(hours=2),
    )
    product = Product(title="Producto MeLi", sku_root="MELI-JOB", stock=Decimal("1"))
    db_session.add_all([account, product])
    await db_session.flush()
    link = MeliItemLink(account_id=account.id, product_id=product.id, item_id="MLA321")
    db_session.add(link)
    await db_session.commit()

    first = await enqueue_stock_sync(db_session, link_id=link.id)
    second = await enqueue_stock_sync(db_session, link_id=link.id)

    assert first.id == second.id
    jobs = list((await db_session.execute(select(MeliSyncJob))).scalars())
    assert len(jobs) == 1
