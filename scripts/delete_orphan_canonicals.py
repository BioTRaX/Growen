"""Script para eliminar productos canónicos huérfanos (sin equivalencia)."""
import asyncio
import os
import sys

project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)
os.chdir(project_root)

from dotenv import load_dotenv
load_dotenv()

from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import text

async def main():
    db_host = os.getenv("DB_HOST", "127.0.0.1")
    db_port = os.getenv("DB_PORT", "5433")
    db_user = os.getenv("DB_USER", "growen")
    db_pass = os.getenv("DB_PASS") or os.getenv("POSTGRES_PASSWORD", "")
    db_name = os.getenv("DB_NAME", "growen")
    
    db_url = f"postgresql+asyncpg://{db_user}:{db_pass}@{db_host}:{db_port}/{db_name}"
    engine = create_async_engine(db_url, echo=False)
    
    async with engine.begin() as conn:
        # Primero listar
        sql_list = text("""
            SELECT cp.id, cp.sku_custom, cp.name
            FROM canonical_products cp
            LEFT JOIN product_equivalences pe ON pe.canonical_product_id = cp.id
            WHERE pe.id IS NULL
            ORDER BY cp.id
        """)
        result = await conn.execute(sql_list)
        rows = result.fetchall()
        
        if not rows:
            print("✅ No hay huérfanos para eliminar.")
            return
        
        print(f"\n⚠️  Se eliminarán {len(rows)} productos canónicos huérfanos:\n")
        for r in rows:
            print(f"  {r[0]}: {r[1]} - {r[2][:40]}")
        
        confirm = input(f"\n¿Confirmar DELETE de {len(rows)} registros? (s/N): ")
        if confirm.lower() != 's':
            print("❌ Cancelado.")
            return
        
        # Eliminar
        ids = [r[0] for r in rows]
        ids_str = ",".join(str(i) for i in ids)
        sql_delete = text(f"DELETE FROM canonical_products WHERE id IN ({ids_str})")
        await conn.execute(sql_delete)
        
        print(f"\n✅ Eliminados {len(rows)} productos canónicos huérfanos.")
    
    await engine.dispose()

if __name__ == "__main__":
    asyncio.run(main())
