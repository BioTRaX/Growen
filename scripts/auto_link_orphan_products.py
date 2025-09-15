#!/usr/bin/env python
# NG-HEADER: Nombre de archivo: auto_link_orphan_products.py
# NG-HEADER: Ubicación: scripts/auto_link_orphan_products.py
# NG-HEADER: Descripción: Crea SupplierProduct para Products huérfanos para que aparezcan en /products.
# NG-HEADER: Lineamientos: Ver AGENTS.md
"""Autovincula productos que no tienen SupplierProduct.
Uso:
  python scripts/auto_link_orphan_products.py --supplier-id 1 --prefix AUTO

Estrategia:
- Busca products sin referencia en supplier_products.internal_product_id.
- Genera supplier_product_id = <prefix><product_id> (si no existe colisión).
- Inserta filas SupplierProduct con título recortado.
- Idempotente: no re-crea vínculos existentes.
"""
from __future__ import annotations
import argparse, asyncio, os, sys
from sqlalchemy import select
from db.session import get_session
from db.models import Product, SupplierProduct, Supplier

if sys.platform.startswith("win"):
    try:
        from asyncio import WindowsSelectorEventLoopPolicy
        import asyncio as _a
        _a.set_event_loop_policy(WindowsSelectorEventLoopPolicy())
    except Exception:
        pass

async def run(supplier_id: int, prefix: str, dry_run: bool):
    agen = get_session(); session = await agen.__anext__()
    try:
        supplier = await session.get(Supplier, supplier_id)
        if not supplier:
            print(f"ERROR: supplier_id {supplier_id} no existe")
            return 1
        # IDs ya vinculados
        linked_ids = set([row[0] for row in (await session.execute(select(SupplierProduct.internal_product_id).where(SupplierProduct.internal_product_id.isnot(None)))).all() if row[0]])
        # Productos candidatos (limit defensivo)
        products = (await session.execute(select(Product.id, Product.title).order_by(Product.id.asc()))).all()
        to_link = [(pid, title) for pid, title in products if pid not in linked_ids]
        if not to_link:
            print("No hay productos huérfanos.")
            return 0
        print(f"Encontrados {len(to_link)} productos huérfanos. Creando vínculos (dry_run={dry_run})...")
        created = 0
        for pid, title in to_link:
            spid = f"{prefix}{pid}"
            # Colisión: existe supplier_product_id igual para ese supplier?
            exists = await session.scalar(select(SupplierProduct).where(SupplierProduct.supplier_id==supplier_id, SupplierProduct.supplier_product_id==spid))
            if exists:
                # Ajustar sufijo incremental
                suffix = 1
                base = spid
                while exists:
                    spid = f"{base}_{suffix}"
                    exists = await session.scalar(select(SupplierProduct).where(SupplierProduct.supplier_id==supplier_id, SupplierProduct.supplier_product_id==spid))
                    suffix += 1
            print(f"  - Link product {pid} -> supplier_product_id={spid}")
            if not dry_run:
                sp = SupplierProduct(supplier_id=supplier_id, supplier_product_id=spid, title=(title or '')[:200], internal_product_id=pid)
                session.add(sp)
                created += 1
        if not dry_run:
            await session.commit()
        print(f"Listo. Creado {created} vínculos nuevos." )
        return 0
    finally:
        try: await agen.aclose()
        except Exception: pass

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--supplier-id', type=int, required=True)
    ap.add_argument('--prefix', default='AUTO')
    ap.add_argument('--dry-run', action='store_true')
    args = ap.parse_args()
    rc = asyncio.run(run(args.supplier_id, args.prefix, args.dry_run))
    raise SystemExit(rc)

if __name__ == '__main__':
    main()
