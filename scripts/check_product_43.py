#!/usr/bin/env python
# NG-HEADER: Nombre de archivo: check_product_43.py
# NG-HEADER: Ubicación: scripts/check_product_43.py
# NG-HEADER: Descripción: Verifica el producto 43 y sus imágenes.
# NG-HEADER: Lineamientos: Ver AGENTS.md

import asyncio
import sys
from pathlib import Path

# FIX: Windows ProactorEventLoop
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

project_root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(project_root))

from db.session import SessionLocal
from db.models import Product, Image
from sqlalchemy import select

async def check():
    async with SessionLocal() as db:
        # Verificar producto 43
        p = await db.get(Product, 43)
        if not p:
            print("Producto 43: NO ENCONTRADO")
            return
        
        print(f"=== Producto ID 43 ===")
        print(f"Título: {p.title}")
        print(f"canonical_sku: {repr(p.canonical_sku)}")
        print(f"sku_root: {repr(p.sku_root)}")
        print()
        
        # Buscar imágenes
        imgs = await db.execute(
            select(Image).where(Image.product_id == 43, Image.active == True)
        )
        images = imgs.scalars().all()
        
        print(f"=== Imágenes activas: {len(images)} ===")
        for img in images:
            print(f"\n  Imagen ID {img.id}:")
            print(f"    URL: {img.url}")
            print(f"    Path: {img.path}")
            print(f"    MIME: {img.mime}")
            print(f"    Tamaño: {img.bytes} bytes")
            print(f"    Checksum: {img.checksum_sha256[:16]}...")
        
        if not images:
            print("  ❌ No hay imágenes activas registradas en la BD.")
        
        # Verificar archivo físico
        from services.media import get_media_root
        media_root = get_media_root()
        print(f"\n=== MEDIA_ROOT: {media_root} ===")
        print(f"¿Existe? {media_root.exists()}")
        
        if images and images[0].path:
            full_path = media_root / images[0].path
            print(f"\n=== Archivo físico esperado ===")
            print(f"Ruta completa: {full_path}")
            print(f"¿Existe? {full_path.exists()}")
            if full_path.exists():
                print(f"Tamaño: {full_path.stat().st_size} bytes")

if __name__ == "__main__":
    asyncio.run(check())

