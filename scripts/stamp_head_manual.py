# NG-HEADER: Nombre de archivo: stamp_head_manual.py
# NG-HEADER: Ubicación: scripts/stamp_head_manual.py
# NG-HEADER: Descripción: Forzar manualmente la versión alembic_version a un HEAD específico (uso excepcional)
# NG-HEADER: Lineamientos: Ver AGENTS.md
import os
from sqlalchemy import create_engine, text
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), '..', '.env'))
url = os.getenv('DB_URL')
assert url, 'DB_URL not set'
default_head = '20250825_fix_identifier_users_force'
HEAD = os.getenv('TARGET_HEAD', default_head)
print('Stamping alembic_version to', HEAD)
engine = create_engine(url, future=True)
with engine.begin() as conn:
    revs = conn.execute(text('SELECT version_num FROM alembic_version')).scalars().all()
    if len(revs) > 1:
        print('Encontradas múltiples filas en alembic_version, se normalizarán a una sola.')
        conn.execute(text('DELETE FROM alembic_version'))
        conn.execute(text('INSERT INTO alembic_version (version_num) VALUES (:v)'), {'v': HEAD})
    elif len(revs) == 1:
        conn.execute(text('UPDATE alembic_version SET version_num=:v'), {'v': HEAD})
    else:
        conn.execute(text('INSERT INTO alembic_version (version_num) VALUES (:v)'), {'v': HEAD})
print('Done. (Uso con precaución: preferir alembic merge + upgrade)')
