"""Tabla para tokens de reseteo de contraseña."""

from alembic import op
import sqlalchemy as sa
from sqlalchemy import text

revision = "20250220_password_reset_tokens"
down_revision = "20250114_supplier_price_history_idx"
branch_labels = None
depends_on = None


def _insp():
    return sa.inspect(op.get_bind())


def _table_exists(name: str) -> bool:
    return _insp().has_table(name)


def _cols(table: str) -> set[str]:
    return {c["name"] for c in _insp().get_columns(table)}


def _idx_exists(table: str, name: str) -> bool:
    return any(ix["name"] == name for ix in _insp().get_indexes(table))


def upgrade() -> None:
    bind = op.get_bind()
    if not _table_exists("password_reset_tokens"):
        op.create_table(
            "password_reset_tokens",
            sa.Column("token", sa.String(64), primary_key=True),
            sa.Column(
                "user_fk",
                sa.Integer,
                sa.ForeignKey("users.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column("expires_at", sa.TIMESTAMP(timezone=False), nullable=False),
            sa.Column(
                "used", sa.Boolean, nullable=False, server_default=sa.text("false")
            ),
        )
        op.create_index(
            "ix_prt_user_fk", "password_reset_tokens", ["user_fk"]
        )
    else:
        cols = _cols("password_reset_tokens")
        if "token" not in cols:
            op.add_column(
                "password_reset_tokens", sa.Column("token", sa.String(64))
            )
        if "user_fk" not in cols:
            op.add_column(
                "password_reset_tokens", sa.Column("user_fk", sa.Integer)
            )
            bind.execute(
                text(
                    """
                DO $$
                BEGIN
                  IF NOT EXISTS (
                    SELECT 1 FROM pg_constraint WHERE conname = 'fk_prt_user'
                  ) THEN
                    ALTER TABLE password_reset_tokens
                    ADD CONSTRAINT fk_prt_user
                    FOREIGN KEY (user_fk) REFERENCES users (id) ON DELETE CASCADE;
                  END IF;
                END $$;
                """
                )
            )
        if "expires_at" not in cols:
            op.add_column(
                "password_reset_tokens",
                sa.Column("expires_at", sa.TIMESTAMP(timezone=False), nullable=False),
            )
        if "used" not in cols:
            op.add_column(
                "password_reset_tokens",
                sa.Column(
                    "used", sa.Boolean, nullable=False, server_default=sa.text("false")
                ),
            )
        if not _idx_exists("password_reset_tokens", "ix_prt_user_fk"):
            op.create_index(
                "ix_prt_user_fk", "password_reset_tokens", ["user_fk"]
            )


def downgrade() -> None:
    if _table_exists("password_reset_tokens"):
        try:
            op.drop_index(
                "ix_prt_user_fk", table_name="password_reset_tokens"
            )
        except Exception:
            pass
        try:
            op.drop_table("password_reset_tokens")
        except Exception:
            pass

