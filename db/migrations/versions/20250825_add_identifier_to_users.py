"""add identifier to users if missing (idempotent)"""

from alembic import op
import sqlalchemy as sa

# Reemplaza por un ID único si tu convención lo requiere
revision = "20250825_add_identifier_to_users"
down_revision = "20241105_auth_roles_sessions"
branch_labels = None
depends_on = None

def _col_exists(conn, table, column):
    q = sa.text("""
        SELECT 1
        FROM information_schema.columns
        WHERE table_name = :t AND column_name = :c
          AND table_schema = current_schema()
        LIMIT 1
    """)
    return conn.execute(q, {"t": table, "c": column}).scalar() is not None

def upgrade():
    conn = op.get_bind()

    # Agregar columna si no existe
    if not _col_exists(conn, "users", "identifier"):
        op.add_column(
            "users",
            sa.Column("identifier", sa.String(length=64), nullable=True)
        )
        # Poblar a partir del email (parte antes de @) si hay email
        conn.execute(sa.text("""
            UPDATE users
            SET identifier = COALESCE(identifier,
                                      NULLIF(split_part(email, '@', 1), ''))
            WHERE identifier IS NULL
        """))
        # Índice único si no existe
        idx_name = "uq_users_identifier"
        op.create_unique_constraint(idx_name, "users", ["identifier"])

def downgrade():
    # Downgrade seguro: solo elimina si existe
    conn = op.get_bind()
    if _col_exists(conn, "users", "identifier"):
        # Quitar constraint si existe
        try:
            op.drop_constraint("uq_users_identifier", "users", type_="unique")
        except Exception:
            pass
        op.drop_column("users", "identifier")
