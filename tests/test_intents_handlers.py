"""Pruebas de los handlers de intents."""

from __future__ import annotations

import asyncio
from pathlib import Path

import pandas as pd
from sqlalchemy import select

from db.session import engine, SessionLocal
from db.models import Base, Product, Variant, Inventory, Supplier, SupplierProduct
from services.intents import handlers


async def _init_db() -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)


def test_handle_stock_adjust_and_min() -> None:
    async def setup() -> None:
        await _init_db()
        async with SessionLocal() as session:
            prod = Product(sku_root="SKU1", title="Producto")
            session.add(prod)
            await session.flush()
            var = Variant(product_id=prod.id, sku="SKU1")
            session.add(var)
            await session.flush()
            inv = Inventory(variant_id=var.id, stock_qty=5, min_qty=1)
            session.add(inv)
            await session.commit()

    asyncio.run(setup())

    res_adjust = handlers.handle_stock(["adjust"], {"sku": "SKU1", "qty": "10"})
    assert res_adjust["action"] == "adjust"

    async def verify_adjust() -> None:
        async with SessionLocal() as session:
            prod = await session.scalar(select(Product).where(Product.sku_root == "SKU1"))
            inv = await session.scalar(
                select(Inventory).join(Variant).where(Variant.sku == "SKU1")
            )
            assert prod and prod.stock == 10
            assert inv and inv.stock_qty == 10

    asyncio.run(verify_adjust())

    res_min = handlers.handle_stock(["min"], {"sku": "SKU1", "qty": "2"})
    assert res_min["action"] == "min"

    async def verify_min() -> None:
        async with SessionLocal() as session:
            inv = await session.scalar(
                select(Inventory).join(Variant).where(Variant.sku == "SKU1")
            )
            assert inv and inv.min_qty == 2

    asyncio.run(verify_min())


def _create_sample_file(path: Path) -> Path:
    df = pd.DataFrame(
        [
            {
                "ID": "ABC1",
                "Agrupamiento": "Ag",
                "Familia": "Fam",
                "SubFamilia": "Sub",
                "Producto": "Maceta",
                "Compra Minima": 1,
                "Stock": 10,
                "PrecioDeCompra": 5.0,
                "PrecioDeVenta": 7.5,
            }
        ]
    )
    file_path = path / "sample.xlsx"
    df.to_excel(file_path, sheet_name="data", index=False, startrow=1)
    return file_path


def test_handle_import(tmp_path: Path) -> None:
    async def setup() -> None:
        await _init_db()
        async with SessionLocal() as session:
            supplier = Supplier(slug="santa-planta", name="Santa Planta")
            session.add(supplier)
            await session.commit()

    asyncio.run(setup())
    file_path = _create_sample_file(tmp_path)

    res = handlers.handle_import([str(file_path)], {"supplier": "santa-planta"})
    assert res["imported"] == 1

    async def verify() -> None:
        async with SessionLocal() as session:
            prod = await session.scalar(select(Product).where(Product.sku_root == "ABC1"))
            sp = await session.scalar(
                select(SupplierProduct).where(
                    SupplierProduct.supplier_product_id == "ABC1"
                )
            )
            assert prod is not None
            assert sp is not None

    asyncio.run(verify())


def test_handle_search(tmp_path: Path) -> None:
    async def setup() -> None:
        await _init_db()
        async with SessionLocal() as session:
            supplier = Supplier(slug="santa-planta", name="Santa Planta")
            session.add(supplier)
            await session.commit()

    asyncio.run(setup())
    file_path = _create_sample_file(tmp_path)
    handlers.handle_import([str(file_path)], {"supplier": "santa-planta"})

    res = handlers.handle_search(["Maceta"], {})
    assert res["items"]
    assert res["items"][0]["name"] == "Maceta"
