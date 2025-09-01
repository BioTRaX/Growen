# NG-HEADER: Nombre de archivo: test_ingest_dryrun.py
# NG-HEADER: Ubicación: tests/test_ingest_dryrun.py
# NG-HEADER: Descripción: Pendiente de descripción
# NG-HEADER: Lineamientos: Ver AGENTS.md
import pandas as pd
import pytest
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from db.base import Base
from db.models import Variant
from services.ingest import report, upsert


@pytest.mark.asyncio
async def test_dryrun_no_persist(tmp_path):
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    Session = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    df = pd.DataFrame({"sku": ["SKU2"], "title": ["Prod"], "price": [10]})
    async with Session() as session:
        res = await upsert.upsert_rows(df.to_dict("records"), session, "Test", dry_run=True)
        report.write_reports("job1", [], [], dest=tmp_path)
    async with Session() as session:
        count = await session.scalar(select(func.count(Variant.id)))
    assert count == 0
    assert (tmp_path / "import_job1_summary.json").exists()
