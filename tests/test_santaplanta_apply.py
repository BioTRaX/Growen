# NG-HEADER: Nombre de archivo: test_santaplanta_apply.py
# NG-HEADER: Ubicación: tests/test_santaplanta_apply.py
# NG-HEADER: Descripción: Pendiente de descripción
# NG-HEADER: Lineamientos: Ver AGENTS.md
import hashlib
import pandas as pd
import pytest
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from db.base import Base
from db.models import Inventory, SupplierPriceHistory, SupplierProduct, Variant
from services.ingest import upsert


def _sku(spid: str) -> str:
    return "SP-" + hashlib.sha1(spid.encode()).hexdigest()[:8].upper()


@pytest.mark.asyncio
async def test_apply_crea_registros_y_historial():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    Session = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    df1 = pd.DataFrame({
        "supplier_product_id": ["1"],
        "title": ["P"],
        "purchase_price": [10],
        "sale_price": [20],
    })
    df2 = pd.DataFrame({
        "supplier_product_id": ["1"],
        "title": ["P"],
        "purchase_price": [15],
        "sale_price": [25],
    })
    async with Session() as session:
        await upsert.upsert_supplier_rows(df1.to_dict("records"), session, "santa-planta", dry_run=False)
    async with Session() as session:
        await upsert.upsert_supplier_rows(df2.to_dict("records"), session, "santa-planta", dry_run=False)
    async with Session() as session:
        sp = await session.scalar(select(SupplierProduct))
        variant = await session.scalar(select(Variant))
        inventory = await session.scalar(select(Inventory))
        history_count = await session.scalar(select(func.count(SupplierPriceHistory.id)))
        last_history = (
            await session.execute(
                select(SupplierPriceHistory).order_by(SupplierPriceHistory.id.desc())
            )
        ).scalar()
    assert sp.supplier_product_id == "1"
    assert variant.sku == _sku("1")
    assert inventory.stock_qty == 0
    assert history_count == 2
    assert round(last_history.delta_purchase_pct, 2) == 50.0
    assert round(last_history.delta_sale_pct, 2) == 25.0
