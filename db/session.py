# NG-HEADER: Nombre de archivo: session.py
# NG-HEADER: Ubicación: db/session.py
# NG-HEADER: Descripción: Creación del engine y sesiones de SQLAlchemy.
# NG-HEADER: Lineamientos: Ver AGENTS.md
"""Sesión asíncrona para SQLAlchemy."""
import asyncio
import os
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from typing import AsyncGenerator
from sqlalchemy.pool import StaticPool
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

# Soporte especial para SQLite en memoria durante tests: un solo pool/conn compartido
# Priorizar variable de entorno DB_URL si está definida (p. ej., tests la setean a :memory:)
db_url = os.getenv("DB_URL") or settings.db_url
kwargs: dict = {"echo": ECHO, "pool_pre_ping": True, "future": True}
if db_url.startswith("sqlite+") and ":memory:" in db_url:
    # Usar una DB en memoria compartida y con nombre para múltiples conexiones
    # Referencia: https://www.sqlite.org/inmemorydb.html (URI mode)
    db_url = "sqlite+aiosqlite:///file:memdb1?mode=memory&cache=shared"
    kwargs.update({"connect_args": {"uri": True}, "poolclass": StaticPool})

engine = create_async_engine(db_url, **kwargs)
SessionLocal = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)

_schema_initialized = False

async def _ensure_schema_if_memory() -> None:
    global _schema_initialized
    if _schema_initialized:
        return
    try:
        url = str(engine.url)
        if url.startswith("sqlite+") and (":memory:" in url or "mode=memory" in url):
            # Import models so metadata is populated
            import db.models  # noqa: F401
            from db.base import Base  # local import to avoid cycles
            async with engine.begin() as conn:
                # Crear el esquema si no existe; no borrar datos ya cargados por tests
                await conn.run_sync(Base.metadata.create_all)
        _schema_initialized = True
    except Exception:
        _schema_initialized = True

async def get_session() -> AsyncGenerator[AsyncSession, None]:
    await _ensure_schema_if_memory()
    async with SessionLocal() as session:
        yield session


# Compatibilidad: algunos módulos esperan ``get_db`` como alias.
get_db = get_session
