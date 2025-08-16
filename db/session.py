"""Sesión asíncrona para SQLAlchemy."""
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from agent_core.config import settings
import os

# ``DEBUG_SQL=1`` activa el modo ``echo`` para ver las consultas generadas y
# facilitar la depuración de errores relacionados a la base de datos.
ECHO = os.getenv("DEBUG_SQL", "0") == "1"
engine = create_async_engine(
    settings.db_url, echo=ECHO, pool_pre_ping=True, future=True
)
SessionLocal = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)

async def get_session() -> AsyncSession:
    async with SessionLocal() as session:
        yield session
