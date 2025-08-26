import os
from sqlalchemy import create_engine, text
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), '..', '.env'))
url = os.getenv('DB_URL')
assert url, 'DB_URL not set'
HEAD = '20250825_fix_identifier_users_force'
print('Stamping alembic_version to', HEAD)
engine = create_engine(url, future=True)
with engine.begin() as conn:
    res = conn.execute(text('UPDATE alembic_version SET version_num=:v'), {'v': HEAD})
    # If table had no rows, insert one
    rowcount = getattr(res, 'rowcount', 0)
    if not rowcount:
        conn.execute(text('INSERT INTO alembic_version (version_num) VALUES (:v)'), {'v': HEAD})
print('Done.')
