import pandas as pd
import pytest
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from db.base import Base
from db.models import Inventory, Variant
from services.ingest import upsert


@pytest.mark.asyncio
async def test_upsert_crea_variant_e_inventory():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    Session = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    df = pd.DataFrame({"sku": ["SKU1"], "title": ["Prod"], "price": [10]})
    async with Session() as session:
        await upsert.upsert_rows(df.to_dict("records"), session, "Test", dry_run=False)
    async with Session() as session:
        count = await session.scalar(select(func.count(Variant.id)))
        inv = await session.scalar(select(Inventory.stock_qty))
    assert count == 1
    assert inv == 0
