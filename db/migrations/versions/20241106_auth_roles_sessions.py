"""create users and sessions tables with admin seed"""

from alembic import op
import sqlalchemy as sa
from passlib.hash import argon2
from sqlalchemy.sql import text

revision = "20241106_auth_roles_sessions"
down_revision = "20241105_auth_roles_sessions"
branch_labels = None
depends_on = None


def _insp():
    return sa.inspect(op.get_bind())


def _table_exists(name: str) -> bool:
    return _insp().has_table(name)


def upgrade():
    if not _table_exists("users"):
        op.create_table(
            "users",
            sa.Column("id", sa.Integer, primary_key=True),
            sa.Column("identifier", sa.Text, nullable=False, unique=True),
            sa.Column("email", sa.Text, nullable=True, unique=True),
            sa.Column("name", sa.Text, nullable=True),
            sa.Column("password_hash", sa.Text, nullable=False),
            sa.Column("role", sa.Text, nullable=False),
            sa.Column(
                "supplier_id",
                sa.Integer,
                sa.ForeignKey("suppliers.id", ondelete="SET NULL"),
                nullable=True,
            ),
            sa.Column(
                "created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False
            ),
            sa.Column(
                "updated_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False
            ),
            sa.CheckConstraint(
                "role IN ('cliente','proveedor','colaborador','admin')",
                name="ck_users_role",
            ),
        )

    if not _table_exists("sessions"):
        op.create_table(
            "sessions",
            sa.Column("id", sa.String(64), primary_key=True),
            sa.Column(
                "user_id",
                sa.Integer,
                sa.ForeignKey("users.id", ondelete="CASCADE"),
                nullable=True,
            ),
            sa.Column("role", sa.Text, nullable=False),
            sa.Column("csrf_token", sa.Text, nullable=False),
            sa.Column("expires_at", sa.DateTime(), nullable=False),
            sa.Column(
                "created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False
            ),
            sa.Column("ip", sa.Text, nullable=True),
            sa.Column("user_agent", sa.Text, nullable=True),
            sa.CheckConstraint(
                "role IN ('guest','cliente','proveedor','colaborador','admin')",
                name="ck_sessions_role",
            ),
        )

    conn = op.get_bind()
    res = conn.execute(text("SELECT 1 FROM users WHERE role='admin' LIMIT 1")).first()
    if not res:
        pwd = argon2.using(type="ID").hash("123456")
        conn.execute(text("""
            INSERT INTO users (identifier,email,name,password_hash,role)
            VALUES (:i,:e,:n,:h,'admin')
            ON CONFLICT (identifier) DO NOTHING
        """), dict(i="Admin", e="admin@growen.local", n="Admin", h=pwd))


def downgrade():
    if _table_exists("sessions"):
        op.drop_table("sessions")
    if _table_exists("users"):
        op.drop_table("users")
