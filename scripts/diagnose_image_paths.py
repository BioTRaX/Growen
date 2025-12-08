#!/usr/bin/env python
# NG-HEADER: Nombre de archivo: diagnose_image_paths.py
# NG-HEADER: Ubicación: scripts/diagnose_image_paths.py
# NG-HEADER: Descripción: Diagnóstico de paths de imágenes en DB vs archivos reales
# NG-HEADER: Lineamientos: Ver AGENTS.md
"""Diagnóstico de paths de imágenes: verifica consistencia entre DB y sistema de archivos."""

import asyncio
import sys
from pathlib import Path

if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

project_root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(project_root))

from db.session import SessionLocal
from db.models import Image, Product, ImageVersion
from services.media import get_media_root
from sqlalchemy import select

async def diagnose_image_paths(product_id: int = None):
    """Diagnostica paths de imágenes para un producto o todos."""
    async with SessionLocal() as db:
        root = get_media_root()
        print(f"=== DIAGNÓSTICO DE PATHS DE IMÁGENES ===\n")
        print(f"MEDIA_ROOT: {root}\n")
        
        # Construir query
        query = select(Image).where(Image.active == True)
        if product_id:
            query = query.where(Image.product_id == product_id)
        query = query.order_by(Image.product_id, Image.id)
        
        result = await db.execute(query)
        images = result.scalars().all()
        
        if not images:
            print(f"❌ No se encontraron imágenes {'para producto ' + str(product_id) if product_id else ''}")
            return
        
        print(f"Total de imágenes encontradas: {len(images)}\n")
        print("=" * 80)
        
        issues = []
        for img in images:
            prod = await db.get(Product, img.product_id)
            prod_name = prod.title if prod else f"Producto {img.product_id}"
            
            print(f"\n📸 Imagen ID {img.id} - Producto {img.product_id}: {prod_name}")
            print(f"   Path en DB: {img.path or '(sin path)'}")
            print(f"   URL en DB: {img.url or '(sin URL)'}")
            print(f"   MIME: {img.mime or '(sin MIME)'}")
            print(f"   Checksum: {img.checksum_sha256[:16] + '...' if img.checksum_sha256 else '(sin checksum)'}")
            
            # Verificar archivo raw
            if img.path:
                full_path = root / img.path
                exists = full_path.exists()
                
                if exists:
                    print(f"   ✅ Archivo raw EXISTE: {full_path}")
                    size = full_path.stat().st_size
                    print(f"      Tamaño: {size:,} bytes")
                else:
                    print(f"   ❌ Archivo raw NO EXISTE: {full_path}")
                    issues.append({
                        'image_id': img.id,
                        'product_id': img.product_id,
                        'expected_path': str(full_path),
                        'db_path': img.path,
                        'type': 'missing_raw'
                    })
                    
                    # Buscar archivos alternativos
                    expected_dir = root / "Productos" / str(img.product_id) / "raw"
                    if expected_dir.exists():
                        files = list(expected_dir.iterdir())
                        if files:
                            print(f"   📁 Archivos encontrados en {expected_dir}:")
                            for f in files:
                                print(f"      - {f.name} ({f.stat().st_size:,} bytes)")
                        else:
                            print(f"   ⚠️  Directorio existe pero está vacío: {expected_dir}")
                    else:
                        print(f"   ⚠️  Directorio no existe: {expected_dir}")
            else:
                print(f"   ⚠️  Imagen sin path registrado en DB")
                issues.append({
                    'image_id': img.id,
                    'product_id': img.product_id,
                    'type': 'no_path'
                })
            
            # Verificar versiones derivadas
            versions_result = await db.execute(
                select(ImageVersion).where(ImageVersion.image_id == img.id)
            )
            versions = versions_result.scalars().all()
            
            if versions:
                print(f"   Versiones derivadas: {len(versions)}")
                for v in versions:
                    v_path = root / v.path if v.path else None
                    if v_path and v_path.exists():
                        print(f"      ✅ {v.kind}: {v.path} ({v_path.stat().st_size:,} bytes)")
                    elif v_path:
                        print(f"      ❌ {v.kind}: {v.path} (NO EXISTE)")
                    else:
                        print(f"      ⚠️  {v.kind}: (sin path)")
            else:
                print(f"   ⚠️  Sin versiones derivadas registradas")
        
        print("\n" + "=" * 80)
        print(f"\n📊 RESUMEN:")
        print(f"   Total imágenes: {len(images)}")
        print(f"   Problemas encontrados: {len(issues)}")
        
        if issues:
            print(f"\n⚠️  PROBLEMAS DETECTADOS:")
            for issue in issues:
                print(f"   - Imagen {issue['image_id']} (Producto {issue['product_id']}): {issue['type']}")
                if 'expected_path' in issue:
                    print(f"     Path esperado: {issue['expected_path']}")
        
        return issues

async def find_misplaced_images(product_id: int = None):
    """Busca imágenes raw que estén fuera de su ubicación esperada."""
    async with SessionLocal() as db:
        root = get_media_root()
        print(f"\n=== BÚSQUEDA DE IMÁGENES DESPLAZADAS ===\n")
        
        # Buscar en directorios comunes
        search_dirs = [
            root / "Productos",
            root,  # Raíz por si están fuera de Productos/
        ]
        
        misplaced = []
        
        query = select(Image).where(Image.active == True)
        if product_id:
            query = query.where(Image.product_id == product_id)
        
        result = await db.execute(query)
        images = result.scalars().all()
        
        for img in images:
            if not img.path or not img.checksum_sha256:
                continue
            
            expected_path = root / img.path
            if expected_path.exists():
                continue  # Ya está en el lugar correcto
            
            # Buscar por checksum en otros lugares
            expected_dir = root / "Productos" / str(img.product_id) / "raw"
            
            # Buscar en el directorio esperado
            if expected_dir.exists():
                for f in expected_dir.iterdir():
                    if f.is_file():
                        # Comparar checksum si es posible
                        try:
                            import hashlib
                            h = hashlib.sha256()
                            with open(f, "rb") as file:
                                for chunk in iter(lambda: file.read(1024 * 1024), b""):
                                    h.update(chunk)
                            if h.hexdigest() == img.checksum_sha256:
                                misplaced.append({
                                    'image_id': img.id,
                                    'product_id': img.product_id,
                                    'found_at': str(f),
                                    'expected_at': str(expected_path),
                                    'current_db_path': img.path
                                })
                                print(f"✅ Encontrada imagen {img.id} (Producto {img.product_id}):")
                                print(f"   Actual: {f}")
                                print(f"   Esperado: {expected_path}")
                                print(f"   Path en DB: {img.path}")
                        except Exception as e:
                            pass  # Continuar buscando
        
        return misplaced

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Diagnostica paths de imágenes")
    parser.add_argument("--product-id", type=int, help="ID del producto a diagnosticar")
    args = parser.parse_args()
    
    issues = asyncio.run(diagnose_image_paths(args.product_id))
    misplaced = asyncio.run(find_misplaced_images(args.product_id))
    
    if misplaced:
        print(f"\n📋 Imágenes encontradas fuera de lugar: {len(misplaced)}")
        print("   Estas imágenes necesitan ser movidas o actualizados sus paths en la DB.")

