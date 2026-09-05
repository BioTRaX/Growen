#!/usr/bin/env python
# NG-HEADER: Nombre de archivo: 20260905_meli_scopes_text.py
# NG-HEADER: Ubicación: db/migrations/versions/20260905_meli_scopes_text.py
# NG-HEADER: Descripción: Conserva permisos funcionales extensos de Mercado Libre sin truncarlos.
# NG-HEADER: Lineamientos: Ver AGENTS.md
from alembic import op
import sqlalchemy as sa

revision = "20260905_meli_scopes_text"
down_revision = "20260831_meli_sync_v1"
branch_labels = None
depends_on = None


def upgrade():
    op.alter_column("meli_accounts", "scopes", existing_type=sa.String(500), type_=sa.Text(), existing_nullable=True)


def downgrade():
    connection = op.get_bind()
    # El lock impide que una escritura concurrente invalide la comprobación.
    if connection.dialect.name == "postgresql":
        connection.execute(sa.text("LOCK TABLE meli_accounts IN ACCESS EXCLUSIVE MODE"))
    if connection.execute(sa.text("SELECT count(*) FROM meli_accounts WHERE length(scopes)>500")).scalar_one():
        raise RuntimeError("meli_scopes_downgrade_would_truncate")
    op.alter_column("meli_accounts", "scopes", existing_type=sa.Text(), type_=sa.String(500), existing_nullable=True)
