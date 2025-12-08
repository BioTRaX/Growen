#!/usr/bin/env python
# NG-HEADER: Nombre de archivo: diagnose_images.py
# NG-HEADER: Ubicación: scripts/diagnose_images.py
# NG-HEADER: Descripción: Diagnostica problemas con imágenes guardadas desde Drive.
# NG-HEADER: Lineamientos: Ver AGENTS.md

"""Script para diagnosticar problemas con imágenes procesadas desde Google Drive."""

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


def check_file_integrity(file_path: Path) -> tuple[bool, Optional[str]]:
    """Verifica si un archivo existe y es una imagen válida."""
    if not file_path.exists():
        return False, "Archivo no existe"
    
    if not file_path.is_file():
        return False, "No es un archivo"
    
    size = file_path.stat().st_size
    if size == 0:
        return False, "Archivo vacío (0 bytes)"
    
    # Intentar leer los primeros bytes para verificar formato
    try:
        with open(file_path, 'rb') as f:
            header = f.read(20)
        
        # Verificar magic bytes
        if header.startswith(b'\xff\xd8\xff'):
            return True, "JPEG válido"
        elif header.startswith(b'\x89PNG\r\n\x1a\n'):
            return True, "PNG válido"
        elif header.startswith(b'RIFF') and b'WEBP' in header[:12]:
            return True, "WebP válido"
        elif header.startswith(b'GIF87a') or header.startswith(b'GIF89a'):
            return True, "GIF válido"
        elif header.startswith(b'ftyp') and (b'heic' in header[:20] or b'heif' in header[:20] or b'mif1' in header[:20]):
            return True, "HEIF/HEIC (puede no ser visible en Windows)"
        else:
            return False, f"Formato desconocido (header: {header[:10].hex()})"
    except Exception as e:
        return False, f"Error al leer archivo: {e}"


async def diagnose_images(product_ids: Optional[list[int]] = None):
    """Diagnostica imágenes guardadas para los productos especificados."""
    media_root = get_media_root()
    print(f"MEDIA_ROOT configurado: {media_root}")
    print(f"¿Existe el directorio? {media_root.exists()}")
    print()
    
    async with SessionLocal() as db:
        if product_ids:
            products = []
            for pid in product_ids:
                p = await db.get(Product, pid)
                if p:
                    products.append(p)
        else:
            # Buscar todos los productos con imágenes recientes
            result = await db.execute(
                select(Product).join(Image).where(Image.active == True).limit(10)
            )
            products = result.scalars().unique().all()
        
        print(f"Diagnosticando {len(products)} productos...\n")
        
        for product in products:
            print(f"{'='*60}")
            print(f"Producto ID {product.id}: {product.title}")
            print(f"{'='*60}")
            
            imgs = await db.execute(
                select(Image).where(Image.product_id == product.id, Image.active == True)
            )
            images = imgs.scalars().all()
            
            if not images:
                print("  ⚠ No hay imágenes activas registradas")
                # Verificar si hay archivos físicos sin registro
                raw_dir = media_root / "Productos" / str(product.id) / "raw"
                if raw_dir.exists():
                    files = list(raw_dir.glob("*"))
                    if files:
                        print(f"  ⚠ Pero hay {len(files)} archivos físicos en {raw_dir}")
                        for f in files[:5]:  # Mostrar solo los primeros 5
                            is_valid, msg = check_file_integrity(f)
                            status = "✅" if is_valid else "❌"
                            print(f"    {status} {f.name} - {msg}")
            else:
                print(f"  📸 {len(images)} imagen(es) registrada(s):\n")
                for img in images:
                    print(f"    Imagen ID {img.id}:")
                    print(f"      URL: {img.url}")
                    print(f"      Path: {img.path}")
                    print(f"      MIME: {img.mime}")
                    print(f"      Tamaño: {img.bytes} bytes" if img.bytes else "      Tamaño: desconocido")
                    
                    # Verificar archivo físico
                    if img.path:
                        # Normalizar path (puede tener backslashes)
                        path_normalized = img.path.replace('\\', '/')
                        full_path = media_root / path_normalized
                        
                        # También intentar con path original
                        full_path_original = media_root / img.path
                        
                        found = False
                        checked_path = None
                        
                        if full_path.exists():
                            checked_path = full_path
                            found = True
                        elif full_path_original.exists():
                            checked_path = full_path_original
                            found = True
                        else:
                            # Buscar archivos en el directorio raw
                            raw_dir = media_root / "Productos" / str(product.id) / "raw"
                            if raw_dir.exists():
                                # Buscar por nombre de archivo
                                path_parts = Path(img.path).parts
                                filename = path_parts[-1] if path_parts else None
                                if filename:
                                    potential_file = raw_dir / filename
                                    if potential_file.exists():
                                        checked_path = potential_file
                                        found = True
                        
                        if found and checked_path:
                            is_valid, msg = check_file_integrity(checked_path)
                            status = "✅" if is_valid else "❌"
                            actual_size = checked_path.stat().st_size
                            size_match = "✓" if img.bytes and actual_size == img.bytes else f"⚠ (DB: {img.bytes}, disco: {actual_size})"
                            print(f"      Archivo físico: {status} {checked_path}")
                            print(f"      Integridad: {msg}")
                            print(f"      Tamaño: {size_match}")
                        else:
                            print(f"      ❌ Archivo físico NO encontrado")
                            print(f"         Buscado en: {full_path}")
                            if full_path != full_path_original:
                                print(f"         También: {full_path_original}")
                            # Listar qué archivos SÍ existen
                            raw_dir = media_root / "Productos" / str(product.id) / "raw"
                            if raw_dir.exists():
                                existing_files = list(raw_dir.glob("*"))
                                if existing_files:
                                    print(f"         Archivos existentes en raw/:")
                                    for f in existing_files[:5]:
                                        print(f"           - {f.name}")
                    print()
            print()


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Diagnostica problemas con imágenes procesadas")
    parser.add_argument("--product-ids", type=int, nargs="+", help="IDs de productos a diagnosticar (opcional)")
    args = parser.parse_args()
    
    asyncio.run(diagnose_images(args.product_ids))

