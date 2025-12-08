#!/usr/bin/env python
# NG-HEADER: Nombre de archivo: fix_image_path_43.py
# NG-HEADER: Ubicación: scripts/fix_image_path_43.py
# NG-HEADER: Descripción: Normaliza el path de la imagen 49 (producto 43) a forward slashes
# NG-HEADER: Lineamientos: Ver AGENTS.md
"""Normaliza paths de imágenes: convierte backslashes a forward slashes."""

import asyncio
import sys
from pathlib import Path

if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

project_root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(project_root))

from db.session import SessionLocal
from db.models import Image, ImageVersion
from sqlalchemy import select, update

async def fix_path_43():
    """Normaliza el path de la imagen 49 (producto 43) a forward slashes."""
    async with SessionLocal() as db:
        img = await db.get(Image, 49)
        if not img:
            print("❌ Imagen 49 no encontrada")
            return
        
        print(f"=== Normalizando path de imagen 49 (Producto {img.product_id}) ===")
        print(f"Path actual: {img.path}")
        
        if img.path and '\\' in img.path:
            # Normalizar a forward slashes
            normalized_path = img.path.replace('\\', '/')
            img.path = normalized_path
            img.url = f"/media/{normalized_path}"
            print(f"Path normalizado: {normalized_path}")
            
            # También normalizar versiones derivadas
            versions_result = await db.execute(
                select(ImageVersion).where(ImageVersion.image_id == 49)
            )
            versions = versions_result.scalars().all()
            
            for v in versions:
                if v.path and '\\' in v.path:
                    v.path = v.path.replace('\\', '/')
                    print(f"  Versión {v.kind} normalizada: {v.path}")
            
            await db.commit()
            print("✅ Path normalizado correctamente")
        else:
            print("✅ Path ya está normalizado")

if __name__ == "__main__":
    asyncio.run(fix_path_43())

