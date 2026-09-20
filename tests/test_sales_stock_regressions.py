#!/usr/bin/env python
# NG-HEADER: Nombre de archivo: test_sales_stock_regressions.py
# NG-HEADER: Ubicación: tests/test_sales_stock_regressions.py
# NG-HEADER: Descripción: Regresiones de stock, devoluciones y anulaciones de ventas.
# NG-HEADER: Lineamientos: Ver AGENTS.md
from __future__ import annotations

from decimal import Decimal
from uuid import uuid4

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from db.models import Product, StockLedger


async def _create_product(client: AsyncClient, *, stock: str) -> int:
    suffix = uuid4().hex[:10]
    response = await client.post(
        "/catalog/products",
        json={
            "title": f"Regresión venta {suffix}",
            "initial_stock": float(stock),
            "sku": f"SALE-REG-{suffix}",
            "purchase_price": 4.25,
            "sale_price": 10.50,
            "category_name": "general",
            "subcategory_name": "general",
            "generate_canonical": False,
        },
    )
    assert response.status_code == 200, response.text
    body = response.json()
    return int(body.get("product_id") or body["id"])


async def _create_sale(client: AsyncClient, product_id: int, quantities: list[str]) -> int:
    response = await client.post(
        "/sales",
        json={
            "customer": {"name": f"Cliente regresión {uuid4().hex[:8]}"},
            "items": [
                {"product_id": product_id, "qty": float(qty), "unit_price": 10.50}
                for qty in quantities
            ],
        },
    )
    assert response.status_code == 200, response.text
    return int(response.json()["sale_id"])


@pytest.mark.asyncio
async def test_confirm_rejects_aggregate_quantity_for_repeated_product(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    product_id = await _create_product(client, stock="10.00")
    sale_id = await _create_sale(client, product_id, ["6.00", "6.00"])

    response = await client.post(f"/sales/{sale_id}/confirm")

    assert response.status_code == 409, response.text
    db_session.expire_all()
    product = await db_session.get(Product, product_id)
    assert product is not None
    assert Decimal(str(product.stock)) == Decimal("10.00")
    ledgers = (
        await db_session.execute(
            select(StockLedger).where(
                StockLedger.source_type == "sale",
                StockLedger.source_id == sale_id,
            )
        )
    ).scalars().all()
    assert ledgers == []


@pytest.mark.asyncio
async def test_partial_return_then_annul_restores_exact_original_stock(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    product_id = await _create_product(client, stock="20.00")
    sale_id = await _create_sale(client, product_id, ["5.00"])

    confirmed = await client.post(f"/sales/{sale_id}/confirm")
    assert confirmed.status_code == 200, confirmed.text
    detail = await client.get(f"/sales/{sale_id}")
    assert detail.status_code == 200, detail.text
    line_id = int(detail.json()["lines"][0]["id"])

    returned = await client.post(
        f"/sales/{sale_id}/returns",
        json={"reason": "Regresión parcial", "items": [{"sale_line_id": line_id, "qty": 2.0}]},
    )
    assert returned.status_code == 200, returned.text
    annulled = await client.post(
        f"/sales/{sale_id}/annul",
        params={"reason": "Regresión luego de devolución"},
    )
    assert annulled.status_code == 200, annulled.text

    db_session.expire_all()
    product = await db_session.get(Product, product_id)
    assert product is not None
    assert Decimal(str(product.stock)) == Decimal("20.00")
    ledgers = (
        await db_session.execute(
            select(StockLedger)
            .where(StockLedger.product_id == product_id)
            .order_by(StockLedger.id)
        )
    ).scalars().all()
    movements = [
        (row.source_type, Decimal(str(row.delta)), Decimal(str(row.balance_after)))
        for row in ledgers
        if row.source_type in {"sale", "return", "annul"}
    ]
    assert movements == [
        ("sale", Decimal("-5.00"), Decimal("15.00")),
        ("return", Decimal("2.00"), Decimal("17.00")),
        ("annul", Decimal("3.00"), Decimal("20.00")),
    ]
