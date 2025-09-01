# NG-HEADER: Nombre de archivo: patch_summary_json.py
# NG-HEADER: Ubicación: scripts/patch_summary_json.py
# NG-HEADER: Descripción: Pendiente de descripción
# NG-HEADER: Lineamientos: Ver AGENTS.md
import os
from sqlalchemy import create_engine, text
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), '..', '.env'))
url = os.getenv('DB_URL')
assert url, 'DB_URL not set'
print('DB_URL:', url)
engine = create_engine(url, future=True)
with engine.begin() as conn:
    print('Adding column import_jobs.summary_json if missing...')
    conn.execute(text(
        """
        DO $$
        BEGIN
          IF NOT EXISTS (
            SELECT 1 FROM information_schema.columns
            WHERE table_name = 'import_jobs'
              AND column_name = 'summary_json'
              AND table_schema = current_schema()
          ) THEN
            ALTER TABLE import_jobs ADD COLUMN summary_json JSON;
          END IF;
        END $$;
        """
    ))
print('Done.')
