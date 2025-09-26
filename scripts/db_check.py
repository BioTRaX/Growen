# NG-HEADER: Nombre de archivo: db_check.py
# NG-HEADER: Ubicación: scripts/db_check.py
# NG-HEADER: Descripción: Chequeos básicos de conexión y latencia de la base.
# NG-HEADER: Lineamientos: Ver AGENTS.md
import os
from agent_core.config import settings
from sqlalchemy import create_engine, text, inspect

url = settings.db_url
print("DB_URL:", url)
engine = create_engine(url, future=True)
with engine.connect() as conn:
    # Basic schema info
    sp = conn.exec_driver_sql("show search_path").scalar()
    cs = conn.exec_driver_sql("select current_schema()").scalar()
    print("search_path:", sp)
    print("current_schema:", cs)

    # Which schemas have a 'users' table?
    rows = conn.execute(text(
        """
        SELECT table_schema, table_name
          FROM information_schema.tables
         WHERE table_name = 'users'
         ORDER BY table_schema
        """
    )).all()
    print("users tables:", rows)

    insp = inspect(conn)
    cols = [c['name'] for c in insp.get_columns('users')]
    print('users columns:', cols)

    # Alembic revision
    try:
        rev = conn.execute(text("select version_num from alembic_version"))
        print("alembic_version:", [r[0] for r in rev])
    except Exception as e:
        print("alembic_version read failed:", e)

    try:
        res = conn.execute(text("SELECT id, identifier, email, name, role FROM users ORDER BY id LIMIT 5")).mappings().all()
        print('sample users:', res)
    except Exception as e:
        print('query failed:', e)
