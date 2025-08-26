import os
from sqlalchemy import create_engine, text
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), '..', '.env'))
url = os.getenv('DB_URL')
print('DB_URL:', url)
engine = create_engine(url, future=True)
with engine.connect() as conn:
    sp = conn.exec_driver_sql("show search_path").scalar()
    cs = conn.exec_driver_sql("select current_schema()").scalar()
    print("search_path:", sp)
    print("current_schema:", cs)

    cols = conn.execute(text(
        """
        SELECT column_name, data_type
        FROM information_schema.columns
        WHERE table_name='import_jobs' AND table_schema=current_schema()
        ORDER BY ordinal_position
        """
    )).all()
    print('import_jobs columns:', cols)

    # Also dump columns for import_job_rows to diagnose missing column errors
    rows_cols = conn.execute(text(
        """
        SELECT column_name, data_type
        FROM information_schema.columns
        WHERE table_name='import_job_rows' AND table_schema=current_schema()
        ORDER BY ordinal_position
        """
    )).all()
    print('import_job_rows columns:', rows_cols)

    # canonical_products columns (including is_nullable) to verify ng_sku nullability
    canon_cols = conn.execute(text(
        """
        SELECT column_name, data_type, is_nullable
        FROM information_schema.columns
        WHERE table_name='canonical_products' AND table_schema=current_schema()
        ORDER BY ordinal_position
        """
    )).all()
    print('canonical_products columns:', canon_cols)

    try:
        rev = conn.execute(text("select version_num from alembic_version")).scalars().all()
        print('alembic_version:', rev)
    except Exception as e:
        print('alembic_version read failed:', e)
