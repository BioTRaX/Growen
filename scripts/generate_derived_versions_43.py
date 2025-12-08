# NG-HEADER: Nombre de archivo: generate_derived_versions_43.py
# NG-HEADER: Ubicación: scripts/generate_derived_versions_43.py
# NG-HEADER: Descripción: Genera versiones derivadas (thumb, card, full) para imágenes del producto 43
# NG-HEADER: Lineamientos: Ver AGENTS.md
"""Script para generar versiones derivadas WebP para imágenes del producto 43."""

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
from services.media.processor import to_square_webp_set
from sqlalchemy import select, delete

async def generate():
    async with SessionLocal() as db:
        p = await db.get(Product, 43)
        if not p:
            print("❌ Producto 43 no encontrado")
            return
        
        print(f"=== Generando versiones derivadas para Producto 43: {p.title} ===")
        print()
        
        result = await db.execute(select(Image).where(Image.product_id == 43))
        imgs = result.scalars().all()
        
        if not imgs:
            print("❌ No hay imágenes para el producto 43")
            return
        
        media_root = get_media_root()
        
        for img in imgs:
            print(f"--- Procesando Imagen ID {img.id} ---")
            
            if not img.path:
                print(f"  ⚠ No hay path registrado, saltando...")
                continue
            
            # Ruta del archivo original
            orig_path = media_root / img.path
            if not orig_path.exists():
                print(f"  ⚠ Archivo original no existe: {orig_path}")
                continue
            
            print(f"  Archivo original: {orig_path}")
            print(f"  Tamaño: {orig_path.stat().st_size} bytes")
            print(f"  MIME: {img.mime}")
            print()
            
            # Eliminar versiones derivadas existentes en DB (las regeneraremos)
            existing_versions = await db.execute(
                select(ImageVersion).where(
                    ImageVersion.image_id == img.id,
                    ImageVersion.kind.in_(["thumb", "card", "full"])
                )
            )
            versions_to_delete = existing_versions.scalars().all()
            if versions_to_delete:
                print(f"  Eliminando {len(versions_to_delete)} versiones derivadas existentes en DB...")
                for v in versions_to_delete:
                    await db.delete(v)
                await db.flush()
            
            # Generar versiones derivadas
            out_dir = media_root / "Productos" / str(p.id) / "derived"
            base = (
                "-".join([p for p in [p.slug or None, p.sku_root or None] if p])
                or f"prod-{p.id}"
            )
            
            print(f"  Generando versiones derivadas...")
            print(f"    Directorio: {out_dir}")
            print(f"    Base: {base}")
            
            try:
                proc = to_square_webp_set(orig_path, out_dir, base)
                print(f"  ✓ Versiones generadas:")
                print(f"    - thumb: {proc.thumb}")
                print(f"    - card: {proc.card}")
                print(f"    - full: {proc.full}")
                
                # Crear registros ImageVersion
                root = get_media_root()
                for kind, pth, px in (
                    ("thumb", proc.thumb, 256),
                    ("card", proc.card, 800),
                    ("full", proc.full, 1600),
                ):
                    relv = str(pth.relative_to(root))
                    relv_normalized = relv.replace('\\', '/')
                    
                    # Verificar que el archivo existe
                    if not pth.exists():
                        print(f"    ⚠ Archivo {kind} no existe: {pth}")
                        continue
                    
                    size_bytes = pth.stat().st_size
                    
                    # Crear o actualizar ImageVersion
                    existing = await db.scalar(
                        select(ImageVersion).where(
                            ImageVersion.image_id == img.id,
                            ImageVersion.kind == kind
                        )
                    )
                    
                    if existing:
                        existing.path = relv_normalized
                        existing.width = px
                        existing.height = px
                        existing.mime = "image/webp"
                        existing.size_bytes = size_bytes
                        print(f"    ✓ Actualizado {kind} en DB")
                    else:
                        db.add(ImageVersion(
                            image_id=img.id,
                            kind=kind,
                            path=relv_normalized,
                            width=px,
                            height=px,
                            mime="image/webp",
                            size_bytes=size_bytes,
                        ))
                        print(f"    ✓ Creado {kind} en DB")
                
                await db.commit()
                print(f"  ✓ Versiones derivadas generadas y guardadas en DB")
                
            except Exception as e:
                print(f"  ❌ Error al generar versiones derivadas: {e}")
                import traceback
                traceback.print_exc()
                await db.rollback()
            
            print()

if __name__ == "__main__":
    asyncio.run(generate())

