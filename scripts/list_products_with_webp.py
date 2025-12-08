# NG-HEADER: Nombre de archivo: list_products_with_webp.py
# NG-HEADER: Ubicación: scripts/list_products_with_webp.py
# NG-HEADER: Descripción: Lista productos que tienen versiones WebP disponibles
# NG-HEADER: Lineamientos: Ver AGENTS.md
"""Script para listar productos que tienen versiones WebP disponibles."""

import asyncio
import sys
from pathlib import Path

if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

project_root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(project_root))

from db.session import SessionLocal
from db.models import Image, ImageVersion, Product
from sqlalchemy import select, func

async def list_webp_products():
    async with SessionLocal() as db:
        # Buscar todas las versiones WebP
        webp_versions = (
            await db.execute(
                select(ImageVersion)
                .where(ImageVersion.mime == "image/webp")
                .where(ImageVersion.kind.in_(["full", "card", "thumb"]))
            )
        ).scalars().all()
        
        # Agrupar por producto
        products_by_id = {}
        for version in webp_versions:
            # Obtener la imagen padre
            img = await db.get(Image, version.image_id)
            if not img or not img.product_id:
                continue
            
            product_id = img.product_id
            if product_id not in products_by_id:
                products_by_id[product_id] = {
                    "product_id": product_id,
                    "product": None,
                    "images": [],
                    "webp_versions": []
                }
            
            if img.id not in [i["id"] for i in products_by_id[product_id]["images"]]:
                products_by_id[product_id]["images"].append({
                    "id": img.id,
                    "url": img.url,
                    "path": img.path,
                    "mime": img.mime
                })
            
            products_by_id[product_id]["webp_versions"].append({
                "kind": version.kind,
                "path": version.path,
                "size": version.size_bytes
            })
        
        # Obtener información de productos
        product_ids = list(products_by_id.keys())
        if product_ids:
            products = (
                await db.execute(
                    select(Product)
                    .where(Product.id.in_(product_ids))
                )
            ).scalars().all()
            
            for product in products:
                if product.id in products_by_id:
                    products_by_id[product.id]["product"] = {
                        "id": product.id,
                        "title": product.title,
                        "canonical_sku": product.canonical_sku
                    }
        
        # Mostrar resultados
        print(f"=== Productos con versiones WebP disponibles ===\n")
        print(f"Total productos: {len(products_by_id)}\n")
        
        for product_id in sorted(products_by_id.keys()):
            info = products_by_id[product_id]
            product = info["product"]
            
            if product:
                print(f"--- Producto ID {product_id}: {product['title']} ---")
                print(f"  SKU: {product.get('canonical_sku', 'N/A')}")
                print(f"  Imágenes: {len(info['images'])}")
                print(f"  Versiones WebP: {len(info['webp_versions'])}")
                
                # Mostrar versiones disponibles
                versions_by_kind = {}
                for v in info["webp_versions"]:
                    if v["kind"] not in versions_by_kind:
                        versions_by_kind[v["kind"]] = []
                    versions_by_kind[v["kind"]].append(v)
                
                for kind in ["full", "card", "thumb"]:
                    if kind in versions_by_kind:
                        v = versions_by_kind[kind][0]
                        size_kb = v["size"] / 1024 if v["size"] else 0
                        print(f"    - {kind}: {v['path']} ({size_kb:.1f} KB)")
                
                print()

if __name__ == "__main__":
    asyncio.run(list_webp_products())

