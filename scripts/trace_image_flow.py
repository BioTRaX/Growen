#!/usr/bin/env python
# NG-HEADER: Nombre de archivo: trace_image_flow.py
# NG-HEADER: Ubicación: scripts/trace_image_flow.py
# NG-HEADER: Descripción: Traza el flujo completo de guardado de imágenes para diagnóstico.
# NG-HEADER: Lineamientos: Ver AGENTS.md

"""Script para trazar el flujo completo de guardado de imágenes y diagnosticar problemas."""

import asyncio
import sys
from pathlib import Path
from typing import Optional

# FIX: Windows ProactorEventLoop
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

project_root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(project_root))

from db.session import SessionLocal
from db.models import Product, Image
from services.media import get_media_root
from sqlalchemy import select


async def trace_image_flow(product_id: int):
    """Traza el flujo completo de guardado de imágenes para un producto."""
    media_root = get_media_root()
    print(f"{'='*70}")
    print(f"TRAZANDO FLUJO DE IMAGENES - PRODUCTO ID {product_id}")
    print(f"{'='*70}\n")
    
    print(f"1. MEDIA_ROOT configurado: {media_root}")
    print(f"   Existe: {media_root.exists()}")
    print(f"   Ruta absoluta: {media_root.resolve()}\n")
    
    async with SessionLocal() as db:
        product = await db.get(Product, product_id)
        if not product:
            print(f"ERROR: Producto {product_id} no encontrado")
            return
        
        print(f"2. Producto encontrado:")
        print(f"   ID: {product.id}")
        print(f"   Título: {product.title}")
        print(f"   SKU canónico: {product.canonical_sku}")
        print(f"   SKU root: {product.sku_root}\n")
        
        # Verificar imágenes en BD
        imgs = await db.execute(
            select(Image).where(Image.product_id == product_id)
            .order_by(Image.id.desc())
        )
        images = imgs.scalars().all()
        
        print(f"3. Imágenes registradas en BD: {len(images)}\n")
        
        for img in images:
            print(f"   Imagen ID {img.id}:")
            print(f"     URL: {img.url}")
            print(f"     Path: {img.path}")
            print(f"     MIME: {img.mime}")
            print(f"     Tamaño BD: {img.bytes} bytes")
            print(f"     Activa: {img.active}")
            print(f"     Primaria: {img.is_primary}")
            print(f"     Checksum: {img.checksum_sha256[:16] if img.checksum_sha256 else 'N/A'}...")
            
            # Verificar archivo físico
            if img.path:
                # Intentar diferentes rutas
                path_variants = [
                    media_root / img.path,
                    media_root / img.path.replace('\\', '/'),
                    media_root / img.path.replace('/', '\\'),
                ]
                
                found = False
                for variant_path in path_variants:
                    if variant_path.exists():
                        found = True
                        file_size = variant_path.stat().st_size
                        print(f"     Archivo encontrado: {variant_path}")
                        print(f"     Tamaño en disco: {file_size} bytes")
                        
                        # Verificar integridad básica
                        if file_size < 100:
                            print(f"     ADVERTENCIA: Archivo muy pequeño (posiblemente corrupto)")
                        elif file_size != img.bytes:
                            print(f"     ADVERTENCIA: Tamaño no coincide (BD: {img.bytes}, disco: {file_size})")
                        else:
                            print(f"     OK: Tamaño coincide")
                        break
                
                if not found:
                    print(f"     ERROR: Archivo NO encontrado")
                    print(f"     Buscado en:")
                    for variant_path in path_variants:
                        print(f"       - {variant_path}")
            
            print()
        
        # Verificar qué archivos físicos existen
        raw_dir = media_root / "Productos" / str(product_id) / "raw"
        print(f"4. Directorio físico esperado: {raw_dir}")
        print(f"   Existe: {raw_dir.exists()}\n")
        
        if raw_dir.exists():
            physical_files = list(raw_dir.glob("*"))
            print(f"   Archivos físicos encontrados: {len(physical_files)}\n")
            for f in physical_files:
                size = f.stat().st_size
                print(f"     - {f.name} ({size} bytes)")
                
                # Verificar si está registrado en BD
                filename_match = any(
                    img.path and (f.name in img.path or img.path.endswith(f.name))
                    for img in images
                )
                if not filename_match:
                    print(f"       ADVERTENCIA: No está registrado en BD")
                else:
                    print(f"       OK: Registrado en BD")
                print()
        else:
            print(f"   ADVERTENCIA: El directorio no existe\n")
        
        # Verificar directorio derived
        derived_dir = media_root / "Productos" / str(product_id) / "derived"
        print(f"5. Directorio derived esperado: {derived_dir}")
        print(f"   Existe: {derived_dir.exists()}\n")
        
        if derived_dir.exists():
            derived_files = list(derived_dir.glob("*"))
            print(f"   Archivos derived encontrados: {len(derived_files)}\n")
            for f in derived_files[:10]:  # Mostrar solo los primeros 10
                size = f.stat().st_size
                print(f"     - {f.name} ({size} bytes)")
        
        print(f"\n{'='*70}")
        print("RESUMEN:")
        print(f"{'='*70}")
        print(f"  - Imágenes en BD: {len(images)}")
        print(f"  - Archivos físicos en raw/: {len(physical_files) if raw_dir.exists() else 0}")
        print(f"  - Archivos derived: {len(derived_files) if derived_dir.exists() else 0}")
        
        # Verificar inconsistencias
        issues = []
        if raw_dir.exists():
            for f in physical_files:
                if f.stat().st_size < 100:
                    issues.append(f"Archivo muy pequeño: {f.name}")
        if len(images) == 0 and raw_dir.exists() and len(physical_files) > 0:
            issues.append("Hay archivos físicos pero no hay registros en BD")
        if len(images) > 0 and (not raw_dir.exists() or len(physical_files) == 0):
            issues.append("Hay registros en BD pero no hay archivos físicos")
        
        if issues:
            print(f"\n  PROBLEMAS DETECTADOS:")
            for issue in issues:
                print(f"    - {issue}")
        else:
            print(f"\n  Todo parece estar OK")


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Traza el flujo completo de guardado de imágenes")
    parser.add_argument("product_id", type=int, help="ID del producto a diagnosticar")
    args = parser.parse_args()
    
    asyncio.run(trace_image_flow(args.product_id))

