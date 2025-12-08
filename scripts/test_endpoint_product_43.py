# NG-HEADER: Nombre de archivo: test_endpoint_product_43.py
# NG-HEADER: Ubicación: scripts/test_endpoint_product_43.py
# NG-HEADER: Descripción: Prueba el endpoint GET /products/43 para ver qué URL de imagen devuelve
# NG-HEADER: Lineamientos: Ver AGENTS.md
"""Script para probar qué URL de imagen devuelve el endpoint GET /products/43."""

import asyncio
import sys
from pathlib import Path

if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

project_root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(project_root))

from db.session import SessionLocal
from db.models import Image, ImageVersion, Product
from services.routers.catalog import _get_image_url_for_browser
from sqlalchemy import select

async def test():
    async with SessionLocal() as db:
        p = await db.get(Product, 43)
        if not p:
            print("❌ Producto 43 no encontrado")
            return
        
        print(f"=== Producto 43: {p.title} ===")
        print()
        
        # Obtener imágenes (igual que en el endpoint)
        imgs = (
            await db.execute(
                select(Image)
                .where(Image.product_id == 43, Image.active == True)
                .order_by(Image.sort_order.asc().nulls_last(), Image.id.asc())
            )
        ).scalars().all()
        
        if not imgs:
            print("❌ No hay imágenes activas para el producto 43")
            return
        
        # Obtener versiones derivadas (igual que en el endpoint)
        img_ids = [im.id for im in imgs]
        versions = {}
        if img_ids:
            version_rows = (
                await db.execute(
                    select(ImageVersion)
                    .where(
                        ImageVersion.image_id.in_(img_ids),
                        ImageVersion.kind.in_(["full", "card", "thumb"])
                    )
                )
            ).scalars().all()
            for v in version_rows:
                if v.image_id not in versions:
                    versions[v.image_id] = {}
                versions[v.image_id][v.kind] = v
        
        print(f"Imágenes encontradas: {len(imgs)}")
        print(f"Versiones derivadas cargadas: {len(versions)}")
        print()
        
        for img in imgs:
            print(f"--- Imagen ID {img.id} ---")
            print(f"  URL original: {img.url}")
            print(f"  Path: {img.path}")
            print(f"  MIME: {img.mime}")
            print()
            
            # Versiones derivadas disponibles
            img_versions = versions.get(img.id, {})
            print(f"  Versiones derivadas disponibles: {list(img_versions.keys())}")
            for kind in ["full", "card", "thumb"]:
                if kind in img_versions:
                    v = img_versions[kind]
                    print(f"    - {kind}: {v.path}")
            print()
            
            # URL que devolvería la función
            browser_url = _get_image_url_for_browser(img, img_versions)
            print(f"  ✓ URL para navegador: {browser_url}")
            print()

if __name__ == "__main__":
    asyncio.run(test())

