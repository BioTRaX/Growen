#!/usr/bin/env python
# NG-HEADER: Nombre de archivo: stock.py
# NG-HEADER: Ubicación: services/meli/stock.py
# NG-HEADER: Descripción: Sincronización transaccional de stock clásico Growen hacia Mercado Libre.
# NG-HEADER: Lineamientos: Ver AGENTS.md
"""Publica inventario sólo cuando el ítem pertenece al seller y usa el modelo clásico."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Any, Protocol

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from db.models import MeliAccount, MeliItemLink, Product
from services.meli.crypto import TokenCipher


class MeliStockError(RuntimeError):
    """Error operacional seguro, apto para persistir como código sin secretos."""


class StockClient(Protocol):
    async def get_resource(self, resource: str, access_token: str) -> dict[str, Any]: ...

    async def update_item(
        self, item_id: str, payload: dict[str, Any], access_token: str
    ) -> dict[str, Any]: ...

    async def refresh_token(self, refresh_token: str) -> dict[str, Any]: ...


@dataclass(frozen=True)
class StockSyncResult:
    link_id: int
    item_id: str
    quantity: int


def _integer_quantity(quantity: Decimal) -> int:
    if quantity < 0 or quantity != quantity.to_integral_value():
        raise MeliStockError("stock_quantity_invalid")
    return int(quantity)


def build_stock_payload(
    item: dict[str, Any], *, variation_id: int | None, quantity: Decimal
) -> dict[str, Any]:
    """Construye el PUT clásico y falla cerrado ante señales de inventario multiorigen."""

    multiwarehouse_markers = (
        "user_product_id",
        "inventory_id",
        "stock_locations",
        "seller_warehouse",
    )
    if any(item.get(marker) is not None for marker in multiwarehouse_markers):
        raise MeliStockError("unsupported_multiwarehouse")

    normalized = _integer_quantity(quantity)
    if variation_id is None:
        return {"available_quantity": normalized}

    variation_ids = {int(value["id"]) for value in item.get("variations", []) if "id" in value}
    if variation_id not in variation_ids:
        raise MeliStockError("meli_variation_not_found")
    return {"variations": [{"id": variation_id, "available_quantity": normalized}]}


async def get_access_token(
    account: MeliAccount, *, client: StockClient, cipher: TokenCipher
) -> str:
    account_ref = str(account.seller_id)
    if account.status != "active":
        raise MeliStockError("meli_account_inactive")

    now = datetime.utcnow()
    if account.token_expires_at > now + timedelta(seconds=60):
        return cipher.decrypt(
            account.access_token_ciphertext, purpose="access", account_ref=account_ref
        )

    refresh = cipher.decrypt(
        account.refresh_token_ciphertext, purpose="refresh", account_ref=account_ref
    )
    token_data = await client.refresh_token(refresh)
    access = token_data.get("access_token")
    replacement_refresh = token_data.get("refresh_token")
    expires_in = token_data.get("expires_in")
    user_id = token_data.get("user_id")
    if (
        not isinstance(access, str)
        or not isinstance(replacement_refresh, str)
        or not isinstance(expires_in, int)
        or int(user_id or 0) != account.seller_id
    ):
        account.status = "error"
        account.last_error_code = "meli_refresh_response_invalid"
        raise MeliStockError("meli_refresh_response_invalid")

    account.access_token_ciphertext = cipher.encrypt(
        access, purpose="access", account_ref=account_ref
    )
    account.refresh_token_ciphertext = cipher.encrypt(
        replacement_refresh, purpose="refresh", account_ref=account_ref
    )
    account.token_expires_at = now + timedelta(seconds=expires_in)
    account.token_version += 1
    account.last_error_code = None
    return access


async def sync_stock_link(
    db: AsyncSession,
    *,
    link_id: int,
    client: StockClient,
    cipher: TokenCipher,
) -> StockSyncResult:
    """Sincroniza un vínculo con locks para serializar token y publicación."""

    link = (
        await db.execute(
            select(MeliItemLink).where(MeliItemLink.id == link_id).with_for_update()
        )
    ).scalar_one_or_none()
    if link is None or not link.active:
        raise MeliStockError("meli_item_link_inactive")

    account = (
        await db.execute(
            select(MeliAccount)
            .where(MeliAccount.id == link.account_id)
            .with_for_update()
        )
    ).scalar_one()
    product = await db.get(Product, link.product_id)
    if product is None:
        raise MeliStockError("growen_product_not_found")

    try:
        access_token = await get_access_token(account, client=client, cipher=cipher)
        item = await client.get_resource(f"/items/{link.item_id}", access_token)
        if int(item.get("seller_id") or 0) != account.seller_id:
            raise MeliStockError("meli_item_owner_mismatch")
        payload = build_stock_payload(
            item, variation_id=link.variation_id, quantity=Decimal(product.stock)
        )
        response = await client.update_item(link.item_id, payload, access_token)
        if str(response.get("id")) != link.item_id:
            raise MeliStockError("meli_stock_response_invalid")
        quantity = _integer_quantity(Decimal(product.stock))
        link.last_synced_quantity = Decimal(quantity)
        link.last_synced_at = datetime.utcnow()
        link.last_error_code = None
        await db.commit()
        return StockSyncResult(link_id=link.id, item_id=link.item_id, quantity=quantity)
    except Exception as exc:
        link.last_error_code = str(exc)[:64] if isinstance(exc, MeliStockError) else "meli_stock_sync_failed"
        await db.commit()
        raise
