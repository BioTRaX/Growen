# NG-HEADER: Nombre de archivo: conftest.py
# NG-HEADER: Ubicación: tests/conftest.py
# NG-HEADER: Descripción: Fixtures y configuración compartida de Pytest.
# NG-HEADER: Lineamientos: Ver AGENTS.md
import os
import sys
import asyncio
from pathlib import Path
import importlib
import pytest_asyncio

from sqlalchemy.ext.asyncio import create_async_engine

# Asegurar path del proyecto antes de importar cualquier módulo interno
project_root = Path(__file__).resolve().parents[1]
if str(project_root) not in sys.path:
    sys.path.append(str(project_root))

# Forzar URL de base de datos en memoria ANTES de importar db.session
os.environ["DB_URL"] = "sqlite+aiosqlite:///:memory:"

# Recargar módulo de sesión para que lea la DB_URL recién establecida
import db.session as _session  # type: ignore
import db.base as _base  # noqa: E402
import db.models  # noqa: F401,E402  (asegura registro de todas las tablas)
from sqlalchemy import text as _text  # noqa: E402

# Reconstruir engine y SessionLocal apuntando a SQLite compartido en memoria
from sqlalchemy.pool import StaticPool
from sqlalchemy.ext.asyncio import create_async_engine as _create_engine
from sqlalchemy.ext.asyncio import async_sessionmaker

if str(_session.engine.url).startswith("postgres"):
    # Solo si quedó creado previamente hacia Postgres, reemplazamos.
    mem_url = "sqlite+aiosqlite:///file:memdb1?mode=memory&cache=shared"
    engine = _create_engine(mem_url, connect_args={"uri": True}, poolclass=StaticPool)
    _session.engine = engine  # type: ignore
    _session.SessionLocal = async_sessionmaker(engine, expire_on_commit=False, class_=_session.AsyncSession)  # type: ignore
else:
    engine = _session.engine

Base = _base.Base

@pytest_asyncio.fixture(scope="function", autouse=True)
async def db_session():
    """
    Fixture que crea una base de datos en memoria para cada test,
    garantizando aislamiento total.
    """
    # Usar el engine global preparado (memoria compartida) para rapidez.
    engine = _session.engine
    async with engine.begin() as conn:
        # Crear todas las tablas
        await conn.run_sync(Base.metadata.create_all)
        # Asegurar tablas o columnas que no están en el modelo base pero son necesarias
        try:
            await conn.execute(_text("CREATE TABLE IF NOT EXISTS sku_sequences (category_code VARCHAR(3) PRIMARY KEY, next_seq INTEGER NOT NULL)"))
        except Exception:
            pass
    
    # La fixture no necesita devolver nada, solo configurar el entorno.
    # El test usará su propia sesión que apunta a esta DB en memoria.
    yield
    
    # Limpieza (aunque en memoria, es buena práctica)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()
