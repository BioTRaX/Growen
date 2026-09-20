#!/usr/bin/env python
# NG-HEADER: Nombre de archivo: test_meli_scopes_migration.py
# NG-HEADER: Ubicación: tests/test_meli_scopes_migration.py
# NG-HEADER: Descripción: Regresión PostgreSQL para scopes extensos y rollback sin pérdida.
# NG-HEADER: Lineamientos: Ver AGENTS.md
import importlib
import os

import pytest
import sqlalchemy as sa
from alembic.migration import MigrationContext
from alembic.operations import Operations

from db.models import MeliAccount


def test_scopes_model_has_no_length_limit():
    assert isinstance(MeliAccount.__table__.c.scopes.type, sa.Text)


@pytest.mark.postgres
def test_scopes_upgrade_preserves_data_and_downgrade_refuses_truncation():
    url = os.getenv("MIGRATION_TEST_POSTGRES_URL")
    if not url:
        pytest.skip("Requiere PostgreSQL para probar límites reales")
    migration = importlib.import_module("db.migrations.versions.20260905_meli_scopes_text")
    engine = sa.create_engine(url, hide_parameters=True)
    try:
        with engine.connect() as connection, connection.begin():
            connection.execute(sa.text("CREATE TEMP TABLE meli_accounts (scopes VARCHAR(500)) ON COMMIT DROP"))
            connection.execute(sa.text("INSERT INTO meli_accounts VALUES ('read'), (NULL)"))
            with Operations.context(MigrationContext.configure(connection)):
                migration.upgrade()
                long_scopes = "urn:ml:mktp:publish-sync:/read-write " * 50
                connection.execute(sa.text("INSERT INTO meli_accounts VALUES (:scopes)"), {"scopes": long_scopes})
                assert connection.execute(sa.text("SELECT scopes FROM meli_accounts WHERE length(scopes)>500")).scalar_one() == long_scopes
                with pytest.raises(RuntimeError, match="meli_scopes_downgrade_would_truncate"):
                    migration.downgrade()
                connection.execute(sa.text("DELETE FROM meli_accounts WHERE length(scopes)>500"))
                migration.downgrade()
                assert connection.execute(sa.text("SELECT scopes FROM meli_accounts WHERE scopes IS NOT NULL")).scalar_one() == "read"
                assert connection.execute(sa.text("SELECT count(*) FROM meli_accounts WHERE scopes IS NULL")).scalar_one() == 1
    finally:
        engine.dispose()
