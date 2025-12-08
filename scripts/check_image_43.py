# NG-HEADER: Nombre de archivo: check_image_43.py
# NG-HEADER: Ubicación: scripts/check_image_43.py
# NG-HEADER: Descripción: Script para verificar información de la imagen ID 43
# NG-HEADER: Lineamientos: Ver AGENTS.md
"""Script para verificar información de la imagen ID 43."""

import asyncio
import sys
from pathlib import Path

if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

project_root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(project_root))

from db.session import SessionLocal
from db.models import Image, Product
from services.media import get_media_root

async def check():
    async with SessionLocal() as db:
        img = await db.get(Image, 43)
        if not img:
            print("❌ Imagen ID 43 no encontrada en la base de datos")
            return
        
        product = await db.get(Product, img.product_id)
        media_root = get_media_root()
        
        print("=== Imagen ID 43 ===")
        print(f"Product ID: {img.product_id}")
        print(f"Producto: {product.title if product else 'N/A'} (SKU: {product.canonical_sku if product else 'N/A'})")
        print(f"URL: {img.url}")
        print(f"Path: {img.path}")
        print(f"Checksum: {img.checksum_sha256}")
        print(f"MIME: {img.mime}")
        print(f"Bytes: {img.bytes}")
        print(f"Width: {img.width}")
        print(f"Height: {img.height}")
        print(f"Is Primary: {img.is_primary}")
        print(f"Active: {img.active}")
        print()
        print(f"MEDIA_ROOT: {media_root}")
        
        if img.path:
            full_path = media_root / img.path
            exists = full_path.exists()
            print(f"Archivo físico existe: {exists}")
            if exists:
                print(f"Tamaño del archivo: {full_path.stat().st_size} bytes")
            else:
                # Intentar con path normalizado
                if '\\' in str(img.path):
                    alt_path = media_root / img.path.replace('\\', '/')
                    print(f"Path alternativo (normalizado): {alt_path}")
                    print(f"  Existe: {alt_path.exists()}")
        else:
            print("❌ No hay path registrado en la base de datos")

if __name__ == "__main__":
    asyncio.run(check())

