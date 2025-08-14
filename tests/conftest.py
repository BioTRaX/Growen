import os
import sys
from pathlib import Path

# Usa una base SQLite en memoria para los tests sin afectar PostgreSQL.
os.environ.setdefault("DB_URL", "sqlite:///:memory:")

# Añade el directorio raíz del proyecto al path para importar los módulos sin instalar
sys.path.append(str(Path(__file__).resolve().parents[1]))

import pytest

from agent_core.db import Base, engine, SessionLocal


@pytest.fixture
def session():
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
        Base.metadata.drop_all(bind=engine)
