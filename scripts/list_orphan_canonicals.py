"""Script para listar productos canónicos huérfanos (sin equivalencia)."""
import asyncio
import os
import sys

# Asegurar que el directorio del proyecto esté en el path
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)
os.chdir(project_root)

from dotenv import load_dotenv
load_dotenv()

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy import text

async def main():
    # Construir URL de base de datos
    db_host = os.getenv("DB_HOST", "127.0.0.1")
    db_port = os.getenv("DB_PORT", "5433")
    db_user = os.getenv("DB_USER", "growen")
    db_pass = os.getenv("DB_PASS") or os.getenv("POSTGRES_PASSWORD", "")
    db_name = os.getenv("DB_NAME", "growen")
    
    db_url = f"postgresql+asyncpg://{db_user}:{db_pass}@{db_host}:{db_port}/{db_name}"
    
    engine = create_async_engine(db_url, echo=False)
    
    async with engine.connect() as conn:
        # Query para encontrar productos canónicos sin equivalencia
        sql = text("""
            SELECT cp.id, cp.sku_custom, cp.name, cp.created_at
            FROM canonical_products cp
            LEFT JOIN product_equivalences pe ON pe.canonical_product_id = cp.id
            WHERE pe.id IS NULL
            ORDER BY cp.id
        """)
        result = await conn.execute(sql)
        rows = result.fetchall()
        
        print(f"\n{'='*70}")
        print(f"PRODUCTOS CANÓNICOS HUÉRFANOS (sin equivalencia)")
        print(f"{'='*70}")
        print(f"Total encontrados: {len(rows)}\n")
        
        if rows:
            print(f"{'ID':<6} {'SKU':<22} {'Nombre':<35}")
            print("-" * 70)
            for row in rows:
                pid, sku, name, created = row
                name_short = (name[:32] + "...") if len(name) > 35 else name
                sku_str = sku or "N/A"
                print(f"{pid:<6} {sku_str:<22} {name_short:<35}")
            
            print("\n" + "="*70)
            print("Para ELIMINAR estos huérfanos, ejecuta:")
            ids = ",".join(str(r[0]) for r in rows)
            print(f"DELETE FROM canonical_products WHERE id IN ({ids});")
            print("="*70)
        else:
            print("✅ No hay productos canónicos huérfanos.")
    
    await engine.dispose()

if __name__ == "__main__":
    asyncio.run(main())
