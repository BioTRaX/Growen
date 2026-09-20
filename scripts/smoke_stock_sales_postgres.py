#!/usr/bin/env python
# NG-HEADER: Nombre de archivo: smoke_stock_sales_postgres.py
# NG-HEADER: Ubicación: scripts/smoke_stock_sales_postgres.py
# NG-HEADER: Descripción: Smoke autenticado de Stock y Ventas contra PostgreSQL real.
# NG-HEADER: Lineamientos: Ver AGENTS.md
from __future__ import annotations

import argparse
import asyncio
import os
import selectors
import sys
from decimal import Decimal
from pathlib import Path
from uuid import uuid4

import httpx
from sqlalchemy import delete, func, select

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from db.models import Customer, Product, Sale, Session, StockLedger, StockShortage, Supplier, User
from db.session import SessionLocal, engine
from services.auth import hash_pw


USER_PREFIX = "codex_smoke_"
SUPPLIER_SLUG = "codex-smoke-provider"


def _password() -> str:
    value = os.getenv("GROWEN_SMOKE_PASSWORD", "")
    if len(value) < 12:
        raise RuntimeError("Defina GROWEN_SMOKE_PASSWORD con al menos 12 caracteres")
    return value


async def _prepare_users(password: str) -> dict[str, str]:
    async with SessionLocal() as db:
        supplier = await db.scalar(select(Supplier).where(Supplier.slug == SUPPLIER_SLUG))
        if supplier is None:
            supplier = Supplier(slug=SUPPLIER_SLUG, name="Proveedor temporal smoke Codex")
            db.add(supplier)
            await db.flush()
        identifiers: dict[str, str] = {}
        for role in ("cliente", "proveedor", "colaborador", "admin"):
            identifier = f"{USER_PREFIX}{role}"
            identifiers[role] = identifier
            user = await db.scalar(select(User).where(User.identifier == identifier))
            if user is None:
                user = User(identifier=identifier, name=f"Smoke {role}", password_hash=hash_pw(password), role=role)
                db.add(user)
            else:
                user.password_hash = hash_pw(password)
                user.role = role
            user.supplier_id = supplier.id if role == "proveedor" else None
        await db.commit()
        return identifiers


async def _login(identifier: str, password: str, base_url: str) -> httpx.AsyncClient:
    client = httpx.AsyncClient(base_url=base_url, timeout=30)
    response = await client.post("/auth/login", json={"identifier": identifier, "password": password})
    if response.status_code != 200:
        await client.aclose()
        raise AssertionError(f"login {identifier}: {response.status_code} {response.text}")
    csrf = client.cookies.get("csrf_token")
    if not csrf:
        await client.aclose()
        raise AssertionError(f"login {identifier}: falta cookie CSRF")
    client.headers["X-CSRF-Token"] = csrf
    return client


async def _assert_status(client: httpx.AsyncClient, method: str, path: str, expected: int, **kwargs) -> httpx.Response:
    response = await client.request(method, path, **kwargs)
    if response.status_code != expected:
        raise AssertionError(f"{method} {path}: esperado {expected}, recibido {response.status_code}: {response.text[:500]}")
    return response


async def _create_product(stock: Decimal, suffix: str) -> int:
    async with SessionLocal() as db:
        product = Product(
            sku_root=f"CODEX-SMOKE-{suffix}",
            title=f"Producto smoke concurrente {suffix}",
            slug=f"codex-smoke-{suffix}",
            status="active",
            stock=stock,
        )
        db.add(product)
        await db.commit()
        return product.id


async def _verify_roles(clients: dict[str, httpx.AsyncClient], product_id: int) -> None:
    for role, client in clients.items():
        await _assert_status(client, "GET", "/auth/me", 200)
        await _assert_status(client, "GET", "/products", 200, params={"page": 1, "page_size": 5, "type": "all"})
        export = await _assert_status(client, "GET", "/stock/export.csv", 200)
        if not export.content.startswith(b"\xef\xbb\xbf"):
            raise AssertionError(f"CSV sin BOM UTF-8 para rol {role}")
        shortage_status = 200 if role in {"colaborador", "admin"} else 403
        catalog_status = 200 if role in {"colaborador", "admin"} else 403
        await _assert_status(client, "GET", "/stock/shortages", shortage_status)
        await _assert_status(client, "GET", "/catalogs", catalog_status)
        if role in {"cliente", "proveedor"}:
            await _assert_status(
                client,
                "PATCH",
                f"/products/{product_id}/stock",
                403,
                json={"stock": 999, "expected_stock": 10.25},
            )


async def _verify_concurrent_shortages(
    clients: dict[str, httpx.AsyncClient],
    product_id: int,
) -> None:
    responses = await asyncio.gather(
        clients["colaborador"].post(
            "/stock/shortages",
            json={"product_id": product_id, "quantity": 1.25, "reason": "UNKNOWN", "observation": "smoke A"},
        ),
        clients["admin"].post(
            "/stock/shortages",
            json={"product_id": product_id, "quantity": 2.50, "reason": "GIFT", "observation": "smoke B"},
        ),
    )
    if [response.status_code for response in responses] != [200, 200]:
        raise AssertionError(f"faltantes concurrentes: {[(r.status_code, r.text) for r in responses]}")
    async with SessionLocal() as db:
        product = await db.get(Product, product_id)
        assert product is not None
        if Decimal(str(product.stock)) != Decimal("6.50"):
            raise AssertionError(f"stock concurrente esperado 6.50, recibido {product.stock}")
        ledgers = (
            await db.execute(
                select(StockLedger)
                .where(StockLedger.product_id == product_id, StockLedger.source_type == "shortage")
                .order_by(StockLedger.id)
            )
        ).scalars().all()
        if len(ledgers) != 2 or sum((Decimal(str(row.delta)) for row in ledgers), Decimal("0")) != Decimal("-3.75"):
            raise AssertionError("los faltantes concurrentes no generaron dos movimientos independientes")
        if Decimal(str(ledgers[-1].balance_after)) != Decimal("6.50"):
            raise AssertionError("el último ledger de faltante no coincide con el saldo persistido")


async def _verify_concurrent_sale_confirmation(
    clients: dict[str, httpx.AsyncClient],
    product_id: int,
) -> int:
    created = await _assert_status(
        clients["colaborador"],
        "POST",
        "/sales",
        200,
        json={
            "customer": {"name": f"Cliente smoke {uuid4().hex[:8]}"},
            "items": [{"product_id": product_id, "qty": 3.25, "unit_price": 10.50}],
        },
    )
    sale_id = int(created.json()["sale_id"])
    responses = await asyncio.gather(
        clients["colaborador"].post(f"/sales/{sale_id}/confirm"),
        clients["admin"].post(f"/sales/{sale_id}/confirm"),
    )
    if [response.status_code for response in responses] != [200, 200]:
        raise AssertionError(f"confirmación concurrente: {[(r.status_code, r.text) for r in responses]}")
    if sum(1 for response in responses if response.json().get("already") is True) != 1:
        raise AssertionError("la confirmación concurrente no fue idempotente")
    async with SessionLocal() as db:
        product = await db.get(Product, product_id)
        assert product is not None
        if Decimal(str(product.stock)) != Decimal("6.75"):
            raise AssertionError(f"stock de venta esperado 6.75, recibido {product.stock}")
        count = await db.scalar(
            select(func.count()).select_from(StockLedger).where(
                StockLedger.product_id == product_id,
                StockLedger.source_type == "sale",
                StockLedger.source_id == sale_id,
            )
        )
        if count != 1:
            raise AssertionError(f"confirmación concurrente generó {count} movimientos de venta")
    return sale_id


async def _cleanup_domain(product_ids: list[int], sale_ids: list[int]) -> None:
    async with SessionLocal() as db:
        customer_ids = (
            await db.execute(select(Sale.customer_id).where(Sale.id.in_(sale_ids), Sale.customer_id.is_not(None)))
        ).scalars().all()
        if sale_ids:
            await db.execute(delete(Sale).where(Sale.id.in_(sale_ids)))
        if product_ids:
            await db.execute(delete(Product).where(Product.id.in_(product_ids)))
        if customer_ids:
            await db.execute(delete(Customer).where(Customer.id.in_(customer_ids)))
        await db.commit()


async def cleanup_users() -> None:
    async with SessionLocal() as db:
        user_ids = (await db.execute(select(User.id).where(User.identifier.like(f"{USER_PREFIX}%")))).scalars().all()
        if user_ids:
            await db.execute(delete(Session).where(Session.user_id.in_(user_ids)))
            await db.execute(delete(User).where(User.id.in_(user_ids)))
        supplier = await db.scalar(select(Supplier).where(Supplier.slug == SUPPLIER_SLUG))
        if supplier is not None:
            await db.delete(supplier)
        await db.commit()
    print("[OK] Usuarios temporales de smoke eliminados")


async def run(base_url: str) -> None:
    if engine.dialect.name != "postgresql":
        raise RuntimeError(f"El smoke requiere PostgreSQL real; conexión actual: {engine.dialect.name}")
    password = _password()
    identifiers = await _prepare_users(password)
    clients = {role: await _login(identifier, password, base_url) for role, identifier in identifiers.items()}
    shortage_product = await _create_product(Decimal("10.25"), uuid4().hex[:10])
    sale_product = await _create_product(Decimal("10.00"), uuid4().hex[:10])
    sale_ids: list[int] = []
    try:
        await _verify_roles(clients, shortage_product)
        await _verify_concurrent_shortages(clients, shortage_product)
        sale_ids.append(await _verify_concurrent_sale_confirmation(clients, sale_product))
        print("[OK] Roles cliente/proveedor/colaborador/admin autenticados y autorizados")
        print("[OK] Dos faltantes concurrentes: stock 10.25 -> 6.50, dos ledgers")
        print("[OK] Confirmación concurrente de venta: stock 10.00 -> 6.75, un ledger")
        print("[INFO] Usuarios temporales conservados para smoke visual; ejecute --cleanup-users al finalizar")
    finally:
        for client in clients.values():
            await client.aclose()
        await _cleanup_domain([shortage_product, sale_product], sale_ids)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    parser.add_argument("--cleanup-users", action="store_true")
    args = parser.parse_args()
    coroutine = cleanup_users() if args.cleanup_users else run(args.base_url.rstrip("/"))
    if os.name == "nt":
        asyncio.run(coroutine, loop_factory=lambda: asyncio.SelectorEventLoop(selectors.SelectSelector()))
    else:
        asyncio.run(coroutine)


if __name__ == "__main__":
    main()
