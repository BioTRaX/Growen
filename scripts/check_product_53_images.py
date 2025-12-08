# NG-HEADER: Nombre de archivo: check_product_53_images.py
# NG-HEADER: Ubicación: scripts/check_product_53_images.py
# NG-HEADER: Descripción: Verifica imágenes del producto 53 y sus versiones WebP
# NG-HEADER: Lineamientos: Ver AGENTS.md
"""Script para verificar imágenes del producto 53."""

import asyncio
import sys
from pathlib import Path

if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

project_root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(project_root))

from db.session import SessionLocal
from db.models import Product, Image, ImageVersion
from services.media import get_media_root
from sqlalchemy import select

async def check():
    async with SessionLocal() as db:
        p = await db.get(Product, 53)
        if not p:
            print("❌ Producto 53 no encontrado")
            return
        
        print(f"=== Producto 53: {p.title} ===")
        print(f"SKU: {p.canonical_sku or p.sku_root}")
        print()
        
        imgs = (await db.execute(
            select(Image).where(Image.product_id == 53)
        )).scalars().all()
        
        print(f"Imágenes en BD: {len(imgs)}")
        media_root = get_media_root()
        print(f"MEDIA_ROOT: {media_root}")
        print()
        
        for img in imgs:
            print(f"--- Imagen ID {img.id} ---")
            print(f"  URL: {img.url}")
            print(f"  Path: {img.path}")
            print(f"  MIME: {img.mime}")
            print(f"  Bytes: {img.bytes}")
            print(f"  Primary: {img.is_primary}")
            
            if img.path:
                full_path = media_root / img.path
                exists = full_path.exists()
                print(f"  Archivo físico existe: {exists}")
                if exists:
                    print(f"    Tamaño: {full_path.stat().st_size:,} bytes")
            else:
                print(f"  ❌ No hay ruta de archivo registrada")
            
            # Verificar versiones derivadas
            versions = (await db.execute(
                select(ImageVersion).where(ImageVersion.image_id == img.id)
            )).scalars().all()
            
            print(f"  Versiones derivadas en BD: {len(versions)}")
            for v in versions:
                v_path = media_root / v.path
                exists = v_path.exists()
                print(f"    - {v.kind}: path={v.path}, mime={v.mime}, size={v.size_bytes}")
                print(f"      Existe físicamente: {exists}")
                if not exists:
                    print(f"      ⚠️ FALTA ARCHIVO FÍSICO")
            
            print()

if __name__ == "__main__":
    asyncio.run(check())

