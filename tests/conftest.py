# NG-HEADER: Nombre de archivo: conftest.py
# NG-HEADER: Ubicación: tests/conftest.py
# NG-HEADER: Descripción: Fixtures y configuración compartida de Pytest.
# NG-HEADER: Lineamientos: Ver AGENTS.md
import os
import sys
import asyncio
from pathlib import Path
import tempfile

from sqlalchemy.ext.asyncio import create_async_engine

sys.path.append(str(Path(__file__).resolve().parents[1]))

# Crear archivo SQLite temporal para permitir múltiples conexiones async y conservar schema.
_tmp_dir = Path(tempfile.gettempdir()) / "growen_pytest"
_tmp_dir.mkdir(exist_ok=True)
_db_path = _tmp_dir / "test_db.sqlite"
os.environ.setdefault("DB_URL", f"sqlite+aiosqlite:///{_db_path}")

from db.base import Base  # noqa: E402
from sqlalchemy import text as _text  # noqa: E402

_engine = create_async_engine(os.environ['DB_URL'])

async def _init_db():
	async with _engine.begin() as conn:
		# Crear todas las tablas (simplificación respecto a migraciones Alembic para tests rápidos)
		await conn.run_sync(Base.metadata.create_all)

# Ejecutar inicialización una vez al importar conftest
asyncio.get_event_loop().run_until_complete(_init_db())

