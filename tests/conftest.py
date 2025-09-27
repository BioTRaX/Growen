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
import db.models  # noqa: F401,E402  (asegura registro de todas las tablas)
from sqlalchemy import text as _text  # noqa: E402

_engine = create_async_engine(os.environ['DB_URL'])

async def _init_db():
	async with _engine.begin() as conn:
		# Crear todas las tablas (simplificación respecto a migraciones Alembic para tests rápidos)
		await conn.run_sync(Base.metadata.create_all)
		# Asegurar tabla sku_sequences (si tests requieren generación canónica)
		try:
			await conn.execute(_text("CREATE TABLE IF NOT EXISTS sku_sequences (category_code VARCHAR(3) PRIMARY KEY, next_seq INTEGER NOT NULL)"))
		except Exception:
			pass

	# Asegurar columna canonical_sku si falta (Legacy DB sqlite ya creada antes de cambio de modelo)
	try:
		res = await _engine.execute(_text("PRAGMA table_info(products)"))  # type: ignore[attr-defined]
		cols = [r[1] for r in res.fetchall()]
		if 'canonical_sku' not in cols:
			async with _engine.begin() as conn2:
				try:
					await conn2.execute(_text("ALTER TABLE products ADD COLUMN canonical_sku VARCHAR(32)"))
				except Exception:
					pass
	except Exception:
		pass

# Ejecutar inicialización una vez al importar conftest
asyncio.get_event_loop().run_until_complete(_init_db())

