# NG-HEADER: Nombre de archivo: check_image_versions_43.py
# NG-HEADER: Ubicación: scripts/check_image_versions_43.py
# NG-HEADER: Descripción: Verifica versiones derivadas de imágenes del producto 43
# NG-HEADER: Lineamientos: Ver AGENTS.md
"""Script para verificar versiones derivadas de imágenes del producto 43."""

import asyncio
import sys
from pathlib import Path

if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

project_root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(project_root))

from db.session import SessionLocal
from db.models import Image, ImageVersion, Product
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
        
        media_root = get_media_root()
        print(f"MEDIA_ROOT: {media_root}")
        print()
        
        for img in imgs:
            print(f"--- Imagen ID {img.id} ---")
            print(f"  URL: {img.url}")
            print(f"  Path: {img.path}")
            print(f"  MIME: {img.mime}")
            print(f"  Checksum: {img.checksum_sha256[:16] if img.checksum_sha256 else None}...")
            print()
            
            # Verificar versiones derivadas
            versions_result = await db.execute(
                select(ImageVersion).where(ImageVersion.image_id == img.id)
            )
            versions = versions_result.scalars().all()
            
            print(f"  Versiones derivadas en DB: {len(versions)}")
            for v in versions:
                print(f"    - {v.kind}: path={v.path}, mime={v.mime}, size={v.size_bytes}")
                if v.path:
                    v_path = media_root / v.path
                    print(f"      Existe físicamente: {v_path.exists()}")
            print()
            
            # Verificar archivo original
            if img.path:
                orig_path = media_root / img.path
                print(f"  Archivo original existe: {orig_path.exists()}")
                if orig_path.exists():
                    print(f"    Tamaño: {orig_path.stat().st_size} bytes")
            print()

if __name__ == "__main__":
    asyncio.run(check())

