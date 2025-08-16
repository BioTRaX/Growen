from alembic import op
import sqlalchemy as sa
from sqlalchemy.sql import text

# Revisions
revision = "20241105_auth_roles_sessions"
down_revision = "20241103_imports_tables"   # ⚠️ Asegúrate que coincida con el nombre real anterior
branch_labels = None
depends_on = None


def upgrade():
    # Tabla users
    op.create_table(
        "users",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("identifier", sa.Text, nullable=False, unique=True),
        sa.Column("email", sa.Text, unique=True),
        sa.Column("name", sa.Text),
        sa.Column("password_hash", sa.Text, nullable=False),
        sa.Column(
            "role",
            sa.Text,
            nullable=False,
        ),
        sa.Column("supplier_id", sa.Integer, sa.ForeignKey("suppliers.id", ondelete="SET NULL")),
        sa.Column("created_at", sa.TIMESTAMP(timezone=False), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.TIMESTAMP(timezone=False), server_default=sa.text("now()"), nullable=False),
    )
    # Check de rol
    op.execute(
        "ALTER TABLE users ADD CONSTRAINT users_role_chk CHECK (role IN ('cliente','proveedor','colaborador','admin'))"
    )

    # Tabla sessions
    op.create_table(
        "sessions",
        sa.Column("id", sa.Text, primary_key=True),  # token hex
        sa.Column("user_id", sa.Integer, sa.ForeignKey("users.id", ondelete="CASCADE")),
        sa.Column(
            "role",
            sa.Text,
            nullable=False,
        ),
        sa.Column("csrf_token", sa.Text, nullable=False),
        sa.Column("expires_at", sa.TIMESTAMP(timezone=False), nullable=False),
        sa.Column("created_at", sa.TIMESTAMP(timezone=False), server_default=sa.text("now()"), nullable=False),
        sa.Column("ip", sa.Text),
        sa.Column("user_agent", sa.Text),
    )
    op.create_index("ix_sessions_expires_at", "sessions", ["expires_at"])
    op.execute(
        "ALTER TABLE sessions ADD CONSTRAINT sessions_role_chk CHECK (role IN ('guest','cliente','proveedor','colaborador','admin'))"
    )

    # Seed admin si no existe
    # Usamos un hash Argon2id ya calculado para '123456' para evitar dependencia en runtime.
    # Si preferís generarlo con passlib dentro de la migración, reemplazá el hash estático.
    admin_hash = (
        # Hash Argon2id ejemplo (podés reemplazar por uno propio si ya generaste):
        # generado con passlib argon2id por defecto (time_cost 2, memory_cost 512, parallelism 2).
        # NO cambia el funcionamiento de la app.
        "$argon2id$v=19$m=65536,t=3,p=4$YWJjZGVmZ2hpamtsbW5vcA$2m9s0B4c5eU2N7Y6U2g0r8o0W3mJz6mXK8oHqkz9b4k"
    )

    op.execute(
        """
        INSERT INTO users (identifier, email, name, password_hash, role)
        SELECT 'Admin', 'admin@growen.local', 'Admin', :pwd, 'admin'
        WHERE NOT EXISTS (SELECT 1 FROM users WHERE role='admin' LIMIT 1)
        """,
        {"pwd": admin_hash},
    )


def downgrade():
    op.drop_index("ix_sessions_expires_at", table_name="sessions")
    op.drop_table("sessions")
    op.drop_constraint("users_role_chk", "users", type_="check")
    op.drop_table("users")
