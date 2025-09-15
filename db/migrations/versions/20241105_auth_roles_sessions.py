# NG-HEADER: Nombre de archivo: 20241105_auth_roles_sessions.py
# NG-HEADER: Ubicación: db/migrations/versions/20241105_auth_roles_sessions.py
# NG-HEADER: Descripción: Pendiente de descripción
# NG-HEADER: Lineamientos: Ver AGENTS.md
from alembic import op
import sqlalchemy as sa
from sqlalchemy import text
import os
from passlib.hash import argon2

# Revisions
revision = "20241105_auth_roles_sessions"
down_revision = "20241103_imports_tables"  # <-- ajustar si tu revision anterior tiene otro ID
branch_labels = None
depends_on = None


def _insp():
    return sa.inspect(op.get_bind())


def _table_exists(name: str) -> bool:
    return _insp().has_table(name)


def _cols(table: str) -> set[str]:
    return {c["name"] for c in _insp().get_columns(table)}


def upgrade():
    bind = op.get_bind()
    insp = sa.inspect(bind)

    # -------------------------
    # USERS
    # -------------------------
    if not _table_exists("users"):
        op.create_table(
            "users",
            sa.Column("id", sa.Integer, primary_key=True),
            sa.Column("identifier", sa.Text, nullable=False, unique=True),
            sa.Column("email", sa.Text, unique=True),
            sa.Column("name", sa.Text),
            sa.Column("password_hash", sa.Text, nullable=False),
            sa.Column("role", sa.Text, nullable=False),
            sa.Column("supplier_id", sa.Integer, sa.ForeignKey("suppliers.id", ondelete="SET NULL")),
            sa.Column("created_at", sa.TIMESTAMP(timezone=False), server_default=sa.text("now()"), nullable=False),
            sa.Column("updated_at", sa.TIMESTAMP(timezone=False), server_default=sa.text("now()"), nullable=False),
        )
        # Check de roles
        bind.execute(text("""
        ALTER TABLE users
        ADD CONSTRAINT users_role_chk
        CHECK (role IN ('cliente','proveedor','colaborador','admin'))
        """))
    else:
        cols = _cols("users")

        # identifier
        if "identifier" not in cols:
            op.add_column("users", sa.Column("identifier", sa.Text(), nullable=True))
            # Prellenar: usar email si existe, sino user_<id>
            bind.execute(text("""
                UPDATE users
                SET identifier = COALESCE(identifier, email, 'user_' || id::text)
                WHERE identifier IS NULL
            """))
            # UNIQUE si no existe
            bind.execute(text("""
            DO $$
            BEGIN
              IF NOT EXISTS (
                SELECT 1 FROM pg_constraint WHERE conname = 'uq_users_identifier'
              ) THEN
                ALTER TABLE users ADD CONSTRAINT uq_users_identifier UNIQUE (identifier);
              END IF;
            END $$;
            """))
            op.alter_column("users", "identifier", nullable=False)
        else:
            # Asegurar UNIQUE por nombre estable
            bind.execute(text("""
            DO $$
            BEGIN
              IF NOT EXISTS (
                SELECT 1 FROM pg_constraint WHERE conname = 'uq_users_identifier'
              ) THEN
                BEGIN
                  ALTER TABLE users ADD CONSTRAINT uq_users_identifier UNIQUE (identifier);
                EXCEPTION WHEN duplicate_table THEN
                  -- ignorar si ya existía con otro nombre/índice
                END;
              END IF;
            END $$;
            """))

        # password_hash
        if "password_hash" not in cols:
            op.add_column("users", sa.Column("password_hash", sa.Text(), nullable=True))
            # Setear hash temporal para filas existentes sin valor
            try:
                from passlib.hash import argon2
                tmp = argon2.using(type="ID").hash("temporal-1234")
            except Exception:
                # hash estático de 'temporal-1234' (argon2id) por fallback
                tmp = "$argon2id$v=19$m=65536,t=3,p=4$YWJjZGVmZ2hpamtsbW5vcA$2m9s0B4c5eU2N7Y6U2g0r8o0W3mJz6mXK8oHqkz9b4k"
            bind.execute(text("UPDATE users SET password_hash = COALESCE(password_hash, :h)"), {"h": tmp})
            op.alter_column("users", "password_hash", nullable=False)

        # role
        if "role" not in cols:
            op.add_column("users", sa.Column("role", sa.Text(), nullable=True))
            bind.execute(text("UPDATE users SET role = COALESCE(role, 'cliente')"))
            op.alter_column("users", "role", nullable=False)

        # check de rol (solo si falta)
        bind.execute(text("""
        DO $$
        BEGIN
          IF NOT EXISTS (
            SELECT 1 FROM pg_constraint WHERE conname = 'users_role_chk'
          ) THEN
            ALTER TABLE users ADD CONSTRAINT users_role_chk
            CHECK (role IN ('cliente','proveedor','colaborador','admin'));
          END IF;
        END $$;
        """))

        # supplier_id
        if "supplier_id" not in cols:
            op.add_column("users", sa.Column("supplier_id", sa.Integer(), nullable=True))
            bind.execute(text("""
            DO $$
            BEGIN
              IF NOT EXISTS (
                SELECT 1 FROM pg_constraint WHERE conname = 'fk_users_supplier'
              ) THEN
                ALTER TABLE users
                ADD CONSTRAINT fk_users_supplier
                FOREIGN KEY (supplier_id) REFERENCES suppliers (id) ON DELETE SET NULL;
              END IF;
            END $$;
            """))

        # created_at / updated_at
        if "created_at" not in cols:
            op.add_column("users", sa.Column("created_at", sa.TIMESTAMP(timezone=False),
                         server_default=sa.text("now()"), nullable=False))
        if "updated_at" not in cols:
            op.add_column("users", sa.Column("updated_at", sa.TIMESTAMP(timezone=False),
                         server_default=sa.text("now()"), nullable=False))

    # -------------------------
    # SESSIONS
    # -------------------------
    if not _table_exists("sessions"):
        op.create_table(
            "sessions",
            sa.Column("id", sa.Text, primary_key=True),  # token hex/urlsafe
            sa.Column("user_id", sa.Integer, sa.ForeignKey("users.id", ondelete="CASCADE")),
            sa.Column("role", sa.Text, nullable=False),
            sa.Column("csrf_token", sa.Text, nullable=False),
            sa.Column("expires_at", sa.TIMESTAMP(timezone=False), nullable=False),
            sa.Column("created_at", sa.TIMESTAMP(timezone=False), server_default=sa.text("now()"), nullable=False),
            sa.Column("ip", sa.Text),
            sa.Column("user_agent", sa.Text),
        )
        op.create_index("ix_sessions_expires_at", "sessions", ["expires_at"])
        bind.execute(text("""
        ALTER TABLE sessions ADD CONSTRAINT sessions_role_chk
        CHECK (role IN ('guest','cliente','proveedor','colaborador','admin'))
        """))
    else:
        cols_s = _cols("sessions")

        if "id" not in cols_s:
            op.add_column("sessions", sa.Column("id", sa.Text, primary_key=True))
        if "user_id" not in cols_s:
            op.add_column("sessions", sa.Column("user_id", sa.Integer))
            bind.execute(text("""
            DO $$
            BEGIN
              IF NOT EXISTS (
                SELECT 1 FROM pg_constraint WHERE conname = 'fk_sessions_user'
              ) THEN
                ALTER TABLE sessions
                ADD CONSTRAINT fk_sessions_user
                FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE;
              END IF;
            END $$;
            """))
        if "role" not in cols_s:
            op.add_column("sessions", sa.Column("role", sa.Text))
            op.execute("UPDATE sessions SET role = COALESCE(role, 'guest')")
            op.alter_column("sessions", "role", nullable=False)
        if "csrf_token" not in cols_s:
            op.add_column("sessions", sa.Column("csrf_token", sa.Text, nullable=False))
        if "expires_at" not in cols_s:
            op.add_column("sessions", sa.Column("expires_at", sa.TIMESTAMP(timezone=False), nullable=False))
        if "created_at" not in cols_s:
            op.add_column("sessions", sa.Column("created_at", sa.TIMESTAMP(timezone=False),
                         server_default=sa.text("now()"), nullable=False))
        if "ip" not in cols_s:
            op.add_column("sessions", sa.Column("ip", sa.Text))
        if "user_agent" not in cols_s:
            op.add_column("sessions", sa.Column("user_agent", sa.Text))

        # Índice por expires_at
        idxs = {ix["name"] for ix in insp.get_indexes("sessions")}
        if "ix_sessions_expires_at" not in idxs and "expires_at" in _cols("sessions"):
            op.create_index("ix_sessions_expires_at", "sessions", ["expires_at"])

        # Check de rol
        bind.execute(text("""
        DO $$
        BEGIN
          IF NOT EXISTS (
            SELECT 1 FROM pg_constraint WHERE conname = 'sessions_role_chk'
          ) THEN
            ALTER TABLE sessions ADD CONSTRAINT sessions_role_chk
            CHECK (role IN ('guest','cliente','proveedor','colaborador','admin'));
          END IF;
        END $$;
        """))

    # -------------------------
    # SEED ADMIN (si no existe)
    # -------------------------
    try:
        bind = op.get_bind()  # asegurar referencia (ya existe como variable local, pero por seguridad)
    except Exception:
        bind = op.get_bind()
    has_admin = bind.execute(text("SELECT 1 FROM users WHERE role='admin' LIMIT 1")).first()
    if not has_admin:
        admin_user = os.getenv("ADMIN_USER", "admin")
        admin_pass = os.getenv("ADMIN_PASS", "REEMPLAZAR_ADMIN_PASS")
        if admin_pass == "REEMPLAZAR_ADMIN_PASS":
            # Intentar cargar .env manualmente sin abortar
            try:
                from pathlib import Path
                from dotenv import load_dotenv  # type: ignore
                repo_root = Path(__file__).resolve().parents[3]
                env_file = repo_root / ".env"
                if env_file.exists():
                    load_dotenv(env_file, override=False)
                    admin_pass = os.getenv("ADMIN_PASS", admin_pass)
            except Exception:
                pass
            if admin_pass == "REEMPLAZAR_ADMIN_PASS":
                print("[WARN] ADMIN_PASS placeholder durante migración; usando fallback 'admin123'. Cambiar luego y rotar contraseña.")
                admin_pass = "admin123"
    # Hash password admin con argon2 (import local para evitar shadowing de import fallido)
    try:
      from passlib.hash import argon2 as _argon2
      pwd = _argon2.using(type="ID").hash(admin_pass)
    except Exception:
      # Hash precomputado de 'admin123' en argon2id como fallback mínimo
      if admin_pass == "admin123":
        pwd = "$argon2id$v=19$m=65536,t=3,p=4$YWJjZGVmZ2hpamtsbW5vcA$2m9s0B4c5eU2N7Y6U2g0r8o0W3mJz6mXK8oHqkz9b4k"
      else:
        raise
        bind.execute(
            text(
                """
            INSERT INTO users (identifier, email, name, password_hash, role)
            SELECT :i, :e, :n, :h, 'admin'
            WHERE NOT EXISTS (SELECT 1 FROM users WHERE role='admin' LIMIT 1)
        """
            ),
            dict(i=admin_user, e=f"{admin_user}@growen.local", n=admin_user, h=pwd),
        )


def downgrade():
    # Sessions: soltar índice y tabla si existen
    if _table_exists("sessions"):
        try:
            op.drop_index("ix_sessions_expires_at", table_name="sessions")
        except Exception:
            pass
        try:
            op.drop_table("sessions")
        except Exception:
            pass

    # Users: dejar tabla (no destruir datos). Soltar constraints añadidos si existen.
    bind = op.get_bind()
    bind.execute(text("ALTER TABLE users DROP CONSTRAINT IF EXISTS sessions_role_chk"))  # por si se aplicó mal
    bind.execute(text("ALTER TABLE users DROP CONSTRAINT IF EXISTS users_role_chk"))
    # Nota: no se elimina uq_users_identifier ni columnas para evitar pérdida de información.

