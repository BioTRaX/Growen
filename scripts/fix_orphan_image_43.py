#!/usr/bin/env python
# NG-HEADER: Nombre de archivo: fix_orphan_image_43.py
# NG-HEADER: Ubicación: scripts/fix_orphan_image_43.py
# NG-HEADER: Descripción: Limpia registro huérfano de imagen del producto 43
# NG-HEADER: Lineamientos: Ver AGENTS.md
"""Script para limpiar registro huérfano de imagen del producto 43."""

import asyncio
import sys
from pathlib import Path

if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

project_root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(project_root))

from db.session import SessionLocal
from db.models import Image, ImageVersion, ImageReview
from sqlalchemy import select

async def fix():
    async with SessionLocal() as db:
        product_id = 43
        image_id = 8
        
        # Verificar imagen
        img = await db.get(Image, image_id)
        if not img:
            print(f"Imagen ID {image_id} no encontrada")
            return
        
        if img.product_id != product_id:
            print(f"La imagen ID {image_id} pertenece al producto {img.product_id}, no al {product_id}")
            return
        
        print(f"=== Imagen ID {image_id} (Producto {product_id}) ===")
        print(f"URL: {img.url}")
        print(f"Path: {img.path}")
        print(f"MIME: {img.mime}")
        print()
        
        # Verificar versiones
        vers = await db.scalars(
            select(ImageVersion).where(ImageVersion.image_id == image_id)
        )
        versions = list(vers)
        print(f"Versiones derivadas: {len(versions)}")
        for v in versions:
            print(f"  - {v.kind}: path={v.path}")
        
        # Verificar reviews
        reviews = await db.scalars(
            select(ImageReview).where(ImageReview.image_id == image_id)
        )
        reviews_list = list(reviews)
        print(f"Reviews: {len(reviews_list)}")
        print()
        
        # Confirmar eliminación
        print("⚠️  ADVERTENCIA: Esto eliminará:")
        print(f"  - Imagen ID {image_id}")
        print(f"  - {len(versions)} versiones derivadas")
        print(f"  - {len(reviews_list)} reviews")
        print()
        
        respuesta = input("¿Deseas continuar? (escribe 'SI' para confirmar): ")
        if respuesta != "SI":
            print("Operación cancelada")
            return
        
        # Eliminar versiones
        for v in versions:
            await db.delete(v)
        print(f"✓ Eliminadas {len(versions)} versiones derivadas")
        
        # Eliminar reviews
        for r in reviews_list:
            await db.delete(r)
        print(f"✓ Eliminadas {len(reviews_list)} reviews")
        
        # Eliminar imagen
        await db.delete(img)
        print(f"✓ Eliminada imagen ID {image_id}")
        
        # Commit
        await db.commit()
        print()
        print("✅ Registro huérfano eliminado correctamente")
        print()
        print("Próximos pasos:")
        print("1. Verificar que el producto 43 tenga el SKU correcto (PES_0009_QUI)")
        print("2. Reprocesar desde Drive")

if __name__ == "__main__":
    asyncio.run(fix())

