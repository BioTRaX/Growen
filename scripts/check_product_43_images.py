# NG-HEADER: Nombre de archivo: check_product_43_images.py
# NG-HEADER: Ubicación: scripts/check_product_43_images.py
# NG-HEADER: Descripción: Script para verificar imágenes del producto 43
# NG-HEADER: Lineamientos: Ver AGENTS.md
"""Script para verificar imágenes del producto 43."""

import asyncio
import sys
from pathlib import Path

if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

project_root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(project_root))

from db.session import SessionLocal
from db.models import Product, Image
from services.media import get_media_root
from sqlalchemy import select

async def check():
    async with SessionLocal() as db:
        p = await db.get(Product, 43)
        if not p:
            print("❌ Producto 43 no encontrado")
            return
        
        print(f"=== Producto 43: {p.title} ===")
        print(f"SKU: {p.canonical_sku}")
        print()
        
        result = await db.execute(select(Image).where(Image.product_id == 43))
        imgs = result.scalars().all()
        print(f"Imágenes en DB: {len(imgs)}")
        
        media_root = get_media_root()
        print(f"MEDIA_ROOT: {media_root}")
        print()
        
        for img in imgs:
            print(f"--- Imagen ID {img.id} ---")
            print(f"  URL: {img.url}")
            print(f"  Path: {img.path}")
            print(f"  Checksum: {img.checksum_sha256}")
            print(f"  MIME: {img.mime}")
            print(f"  Bytes: {img.bytes}")
            if img.path:
                full_path = media_root / img.path
                exists = full_path.exists()
                print(f"  Archivo físico existe: {exists}")
                if not exists and '\\' in str(img.path):
                    alt_path = media_root / img.path.replace('\\', '/')
                    print(f"    Alternativa (normalizado): {alt_path.exists()}")
            print()

if __name__ == "__main__":
    asyncio.run(check())
