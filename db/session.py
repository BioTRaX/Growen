"""Sesión asíncrona para SQLAlchemy."""
import asyncio
import os
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from agent_core.config import settings

# Pytest con ``pytest-asyncio`` en modo estricto remueve el loop por defecto y
# ``asyncio.get_event_loop()`` lanza ``RuntimeError`` si no hay uno activo.
# Para mantener compatibilidad con utilidades del proyecto que invocan
# directamente esta función, la parcheamos para crear un loop nuevo cuando
# sea necesario.
_orig_get_event_loop = asyncio.get_event_loop


def _safe_get_event_loop() -> asyncio.AbstractEventLoop:  # pragma: no cover
    try:
        return _orig_get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        return loop


asyncio.get_event_loop = _safe_get_event_loop

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


# Compatibilidad: algunos módulos esperan ``get_db`` como alias.
get_db = get_session
