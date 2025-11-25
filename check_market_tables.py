#!/usr/bin/env python
"""Script temporal para verificar tablas de mercado."""
from sqlalchemy import create_engine, text
from urllib.parse import quote_plus

pw = quote_plus('GrowenBot=01')
engine = create_engine(f'postgresql+psycopg://growen:{pw}@127.0.0.1:5433/growen')

print("\n=== VERIFICACIÓN DE TABLAS DE MERCADO ===\n")

with engine.connect() as conn:
    # Listar tablas market_*
    result = conn.execute(text(
        "SELECT table_name FROM information_schema.tables "
        "WHERE table_schema = 'public' AND table_name LIKE 'market%' "
        "ORDER BY table_name"
    ))
    tables = [row[0] for row in result]
    
    if tables:
        print(f"✅ Tablas encontradas: {', '.join(tables)}\n")
        
        # Contar registros en cada tabla
        for table in tables:
            count_result = conn.execute(text(f"SELECT COUNT(*) FROM {table}"))
            count = count_result.scalar()
            print(f"   {table}: {count:,} registros")
    else:
        print("❌ NO SE ENCONTRARON TABLAS DE MERCADO")
        print("\nVerificando si existieron antes (buscando en migraciones)...")

print("\n" + "="*50)
