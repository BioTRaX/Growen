"""Sesión asíncrona para SQLAlchemy."""
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from agent_core.config import settings

engine = create_async_engine(settings.db_url, echo=False)
SessionLocal = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)

async def get_session() -> AsyncSession:
    async with SessionLocal() as session:
        yield session
