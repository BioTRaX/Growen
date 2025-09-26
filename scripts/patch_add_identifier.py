# NG-HEADER: Nombre de archivo: patch_add_identifier.py
# NG-HEADER: Ubicación: scripts/patch_add_identifier.py
# NG-HEADER: Descripción: Parche que agrega identificadores faltantes en usuarios.
# NG-HEADER: Lineamientos: Ver AGENTS.md
from agent_core.config import settings
from sqlalchemy import create_engine, text

url = settings.db_url
print("Patching DB at:", url)
engine = create_engine(url, future=True)
with engine.begin() as conn:
    # 1) add column if missing
    conn.execute(text(
        """
        DO $$
        BEGIN
          IF NOT EXISTS (
            SELECT 1 FROM information_schema.columns
            WHERE table_name = 'users' AND column_name = 'identifier'
              AND table_schema = current_schema()
          ) THEN
            ALTER TABLE users ADD COLUMN identifier VARCHAR(64);
          END IF;
        END $$;
        """
    ))
    # 2) backfill identifier
    conn.execute(text(
        """
        UPDATE users
           SET identifier = COALESCE(identifier, NULLIF(split_part(email, '@', 1), ''), 'user_' || id::text)
         WHERE identifier IS NULL;
        """
    ))
    # 3) add unique constraint if missing
    conn.execute(text(
        """
        DO $$
        BEGIN
          IF NOT EXISTS (
            SELECT 1 FROM pg_constraint WHERE conname = 'uq_users_identifier'
          ) THEN
            BEGIN
              ALTER TABLE users ADD CONSTRAINT uq_users_identifier UNIQUE (identifier);
            EXCEPTION WHEN duplicate_object THEN
              NULL;
            END;
          END IF;
        END $$;
        """
    ))
    # 4) try set not null
    try:
        conn.execute(text("ALTER TABLE users ALTER COLUMN identifier SET NOT NULL"))
    except Exception:
        pass
print("DB patched.")
