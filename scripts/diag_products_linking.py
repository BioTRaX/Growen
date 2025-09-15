#!/usr/bin/env python
# NG-HEADER: Nombre de archivo: diag_products_linking.py
# NG-HEADER: Ubicación: scripts/diag_products_linking.py
# NG-HEADER: Descripción: Diagnóstico de integridad producto <-> supplier_product y stock.
# NG-HEADER: Lineamientos: Ver AGENTS.md
"""Script de diagnóstico para:
1. Contar productos totales.
2. Contar supplier_products totales.
3. Listar productos sin supplier_product asociado.
4. Listar supplier_products sin internal_product_id.
5. Mostrar últimos audit_logs de creación de productos.
"""
from __future__ import annotations
import os, asyncio, json, textwrap, sys
from sqlalchemy import select, func
from db.session import get_session

# En Windows forzar policy compatible con psycopg async (evita Proactor loop).
if sys.platform.startswith("win"):
    try:
        from asyncio import WindowsSelectorEventLoopPolicy
        asyncio.set_event_loop_policy(WindowsSelectorEventLoopPolicy())
    except Exception:
        pass
from db.models import Product, SupplierProduct, AuditLog

DB_URL = os.getenv("DB_URL")

async def main():
    print(f"DB_URL={DB_URL}")
    # get_session es un async generator; lo usamos manualmente
    agen = get_session()
    session = await agen.__anext__()
    try:
        total_products = await session.scalar(select(func.count()).select_from(Product))
        total_sp = await session.scalar(select(func.count()).select_from(SupplierProduct))
        # Productos con al menos un supplier_product
        q_linked_ids = select(SupplierProduct.internal_product_id).where(SupplierProduct.internal_product_id.isnot(None))
        linked_ids = {row[0] for row in (await session.execute(q_linked_ids)).all() if row[0] is not None}
        # Productos huérfanos
        q_recent_products = select(Product.id, Product.title, Product.stock).order_by(Product.id.desc()).limit(30)
        recent_products = (await session.execute(q_recent_products)).all()
        orphan_products = [ (pid, title, stock) for pid, title, stock in recent_products if pid not in linked_ids ]
        # Supplier products sin internal_product_id
        q_sp_orphans = select(SupplierProduct.id, SupplierProduct.supplier_id, SupplierProduct.supplier_product_id).where(SupplierProduct.internal_product_id.is_(None)).order_by(SupplierProduct.id.desc()).limit(30)
        sp_orphans = (await session.execute(q_sp_orphans)).all()
        # Audit logs product_create
        q_logs = select(AuditLog.id, AuditLog.meta).where(AuditLog.action=="product_create").order_by(AuditLog.id.desc()).limit(10)
        logs = (await session.execute(q_logs)).all()

        print("\n=== RESUMEN ===")
        print(f"Productos totales: {total_products}")
        print(f"SupplierProducts totales: {total_sp}")
        print(f"Productos recientes sin vínculo (entre los últimos 30): {len(orphan_products)}")
        for pid, title, stock in orphan_products[:10]:
            print(f"  - Product {pid} stock={stock} title={title[:60]}")
        print(f"SupplierProducts sin internal_product_id (top 30): {len(sp_orphans)}")
        for spid, sid, ssku in sp_orphans[:10]:
            print(f"  - SupplierProduct {spid} supplier={sid} sku={ssku}")
        print("\n=== LOGS product_create (últimos 10) ===")
        for lid, meta in logs:
            try:
                meta_dict = meta or {}
                forced_zero = meta_dict.get("initial_stock_forced_zero")
                isp = meta_dict.get("initial_stock_final")
                spid = meta_dict.get("supplier_product_id")
                supid = meta_dict.get("supplier_id")
                sku = meta_dict.get("supplier_sku")
                print(f"  - log {lid}: supplier_id={supid} sku={sku} sp_id={spid} forced_zero={forced_zero} initial_stock_final={isp}")
            except Exception:
                print(f"  - log {lid}: (error parseando meta)")
        print("\nSugerencias:")
        if orphan_products:
            print(" - Hay productos sin SupplierProduct: crear vínculo para que aparezcan en /products.")
        if sp_orphans:
            print(" - Hay supplier_products sin internal_product_id: enlazarlos o depurarlos.")
        if not orphan_products and not sp_orphans:
            print(" - No se detectan problemas de enlace básicos en el muestreo.")
    finally:
        try:
            await agen.aclose()
        except Exception:
            pass

if __name__ == "__main__":
    asyncio.run(main())
