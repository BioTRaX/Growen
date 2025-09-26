# NG-HEADER: Nombre de archivo: test_santaplanta_dryrun.py
# NG-HEADER: Ubicación: tests/test_santaplanta_dryrun.py
# NG-HEADER: Descripción: Pruebas del modo dry-run de Santaplanta.
# NG-HEADER: Lineamientos: Ver AGENTS.md
import pandas as pd
import pytest
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from db.base import Base
from db.models import SupplierProduct, Variant
from services.ingest import upsert


@pytest.mark.asyncio
async def test_dryrun_no_persist(tmp_path):
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    Session = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    df = pd.DataFrame({
        "supplier_product_id": ["1"],
        "title": ["P"],
        "purchase_price": [10],
        "sale_price": [20],
    })
    async with Session() as session:
        await upsert.upsert_supplier_rows(df.to_dict("records"), session, "santa-planta", dry_run=True)
    async with Session() as session:
        count_sp = await session.scalar(select(func.count(SupplierProduct.id)))
        count_var = await session.scalar(select(func.count(Variant.id)))
    assert count_sp == 0
    assert count_var == 0
