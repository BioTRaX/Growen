#!/usr/bin/env python
# NG-HEADER: Nombre de archivo: cleanup_product_93_orphans.py
# NG-HEADER: Ubicación: scripts/cleanup_product_93_orphans.py
# NG-HEADER: Descripción: Limpia referencias huérfanas del producto 93 (testing)
# NG-HEADER: Lineamientos: Ver AGENTS.md
"""
Script para limpiar referencias huérfanas del producto 93.

Este producto tiene SupplierProduct que referencian un Product que no existe,
causando que aparezca en Market pero no se pueda eliminar normalmente.
"""

import asyncio
import sys
from pathlib import Path

# FIX: Windows ProactorEventLoop
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

project_root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(project_root))

from db.session import SessionLocal
from db.models import Product, CanonicalProduct, SupplierProduct, ProductEquivalence
from sqlalchemy import select

async def cleanup_product_93(confirm: bool = False):
    """Limpia referencias huérfanas del producto 93."""
    async with SessionLocal() as session:
        print("[*] Buscando referencias huerfanas del producto 93...")
        
        # Buscar SupplierProduct que referencian el producto 93
        orphan_sp = await session.execute(
            select(SupplierProduct).where(SupplierProduct.internal_product_id == 93)
        )
        orphan_sp_list = orphan_sp.scalars().all()
        
        if not orphan_sp_list:
            print("[OK] No se encontraron SupplierProduct con internal_product_id=93")
        else:
            print(f"[!] Encontrados {len(orphan_sp_list)} SupplierProduct huerfanos:")
            for sp in orphan_sp_list:
                print(f"   - ID: {sp.id}, supplier_id: {sp.supplier_id}, supplier_product_id: {sp.supplier_product_id}")
            
            # Buscar equivalencias relacionadas
            sp_ids = [sp.id for sp in orphan_sp_list]
            equivalences = await session.execute(
                select(ProductEquivalence).where(ProductEquivalence.supplier_product_id.in_(sp_ids))
            )
            eq_list = equivalences.scalars().all()
            
            if eq_list:
                print(f"[!] Encontradas {len(eq_list)} ProductEquivalence relacionadas:")
                for eq in eq_list:
                    print(f"   - ID: {eq.id}, canonical_product_id: {eq.canonical_product_id}")
            
            if not confirm:
                try:
                    response = input("\n¿Deseas eliminar estas referencias huerfanas? (s/N): ")
                    if response.lower() != 's':
                        print("[X] Cancelado")
                        return
                except (EOFError, KeyboardInterrupt):
                    print("\n[X] Cancelado (no se puede leer input)")
                    return
            
            # Eliminar equivalencias primero
            for eq in eq_list:
                await session.delete(eq)
                print(f"   [OK] Eliminada ProductEquivalence ID {eq.id}")
            
            # Eliminar SupplierProduct
            for sp in orphan_sp_list:
                await session.delete(sp)
                print(f"   [OK] Eliminado SupplierProduct ID {sp.id}")
            
            await session.commit()
            print("\n[OK] Limpieza completada")
        
        # Verificar si existe como CanonicalProduct
        canonical = await session.get(CanonicalProduct, 93)
        if canonical:
            print(f"\n[!] Tambien existe CanonicalProduct ID 93: {canonical.name}")
            print(f"   SKU: {canonical.sku_custom or canonical.ng_sku}")
            if confirm:
                should_delete = True
            else:
                try:
                    response = input("¿Deseas eliminar este CanonicalProduct tambien? (s/N): ")
                    should_delete = response.lower() == 's'
                except (EOFError, KeyboardInterrupt):
                    print("\n[X] Cancelado (no se puede leer input)")
                    should_delete = False
            if should_delete:
                await session.delete(canonical)
                await session.commit()
                print("[OK] CanonicalProduct 93 eliminado")
        else:
            print("\n[OK] No existe CanonicalProduct con ID 93")

if __name__ == "__main__":
    import sys
    # Permitir ejecutar con --yes para confirmar automáticamente
    confirm = "--yes" in sys.argv or "-y" in sys.argv
    asyncio.run(cleanup_product_93(confirm=confirm))

