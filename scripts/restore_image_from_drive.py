# NG-HEADER: Nombre de archivo: restore_image_from_drive.py
# NG-HEADER: Ubicación: scripts/restore_image_from_drive.py
# NG-HEADER: Descripción: Script para restaurar imagen desde Google Drive usando checksum o nombre
# NG-HEADER: Lineamientos: Ver AGENTS.md
"""Script para restaurar una imagen desde Google Drive a MEDIA_ROOT."""

import asyncio
import sys
from pathlib import Path

if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

project_root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(project_root))

from db.session import SessionLocal
from db.models import Image, Product
from services.integrations.drive import GoogleDriveSync, GoogleDriveError
from services.media import get_media_root, sha256_of_file
from sqlalchemy import select
import hashlib
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def find_file_by_checksum(drive_sync: GoogleDriveSync, checksum: str, folder_id: str) -> dict | None:
    """Busca un archivo en Google Drive por checksum (comparando SHA256)."""
    try:
        # Usar list_images_in_folder que lista todos los archivos de imagen
        files = await drive_sync.list_images_in_folder()
        logger.info(f"Buscando archivo con checksum {checksum[:16]}... en {len(files)} archivos")
        
        for file_info in files:
            try:
                content = await drive_sync.download_file(file_info["id"])
                file_checksum = hashlib.sha256(content).hexdigest()
                if file_checksum == checksum:
                    logger.info(f"✓ Archivo encontrado: {file_info['name']} (ID: {file_info['id']})")
                    return file_info
            except Exception as e:
                logger.debug(f"Error al verificar checksum de {file_info.get('name')}: {e}")
                continue
        return None
    except Exception as e:
        logger.error(f"Error buscando archivo por checksum: {e}")
        return None


async def restore_image(image_id: int, source_folder_id: str | None = None) -> bool:
    """Restaura una imagen desde Google Drive a MEDIA_ROOT.
    
    Args:
        image_id: ID de la imagen en la base de datos.
        source_folder_id: ID de carpeta en Google Drive donde buscar (opcional).
    
    Returns:
        True si se restauró exitosamente, False en caso contrario.
    """
    async with SessionLocal() as db:
        # Obtener imagen de la DB
        img = await db.get(Image, image_id)
        if not img:
            logger.error(f"Imagen ID {image_id} no encontrada en la base de datos")
            return False
        
        logger.info(f"=== Restaurando Imagen ID {image_id} ===")
        logger.info(f"  Product ID: {img.product_id}")
        logger.info(f"  URL: {img.url}")
        logger.info(f"  Path: {img.path}")
        logger.info(f"  Checksum: {img.checksum_sha256}")
        logger.info(f"  MIME: {img.mime}")
        logger.info(f"  Bytes: {img.bytes}")
        
        # Obtener producto
        product = await db.get(Product, img.product_id)
        if not product:
            logger.error(f"Producto ID {img.product_id} no encontrado")
            return False
        
        logger.info(f"  Producto: {product.title} (SKU: {product.canonical_sku})")
        
        # Determinar carpeta de origen
        if not source_folder_id:
            source_folder_id = os.getenv("DRIVE_SOURCE_FOLDER_ID")
            if not source_folder_id:
                logger.error("No se especificó source_folder_id y DRIVE_SOURCE_FOLDER_ID no está configurado")
                return False
        
        # Obtener ruta de credenciales
        credentials_path = os.getenv("GOOGLE_APPLICATION_CREDENTIALS")
        if not credentials_path:
            logger.error("GOOGLE_APPLICATION_CREDENTIALS no está configurado")
            return False
        
        # Inicializar Google Drive
        try:
            drive_sync = GoogleDriveSync(credentials_path, source_folder_id)
            await drive_sync.authenticate()
        except Exception as e:
            logger.error(f"Error inicializando Google Drive: {e}")
            return False
        
        logger.info(f"Buscando en carpeta Drive: {source_folder_id}")
        
        # Buscar también en carpetas "Procesados" y "Errores_SKU"
        processed_folder_name = os.getenv("DRIVE_PROCESSED_FOLDER_NAME", "Procesados")
        errors_folder_name = os.getenv("DRIVE_ERRORS_FOLDER_NAME", "Errores_SKU")
        
        # Crear/buscar carpetas destino
        processed_folder_id = await drive_sync.find_or_create_folder(source_folder_id, processed_folder_name)
        errors_folder_id = await drive_sync.find_or_create_folder(source_folder_id, errors_folder_name)
        
        folders_to_search = [
            (source_folder_id, "Origen"),
            (processed_folder_id, "Procesados"),
            (errors_folder_id, "Errores_SKU"),
        ]
        
        # Buscar archivo por checksum en todas las carpetas
        file_info = None
        if img.checksum_sha256:
            logger.info("Buscando archivo por checksum en todas las carpetas...")
            for folder_id, folder_name in folders_to_search:
                logger.info(f"  Buscando en carpeta '{folder_name}' ({folder_id})...")
                # Crear un drive_sync temporal con esta carpeta como origen
                temp_drive = GoogleDriveSync(drive_sync.credentials_path, folder_id)
                await temp_drive.authenticate()
                file_info = await find_file_by_checksum(temp_drive, img.checksum_sha256, folder_id)
                if file_info:
                    logger.info(f"✓ Archivo encontrado en carpeta '{folder_name}'")
                    drive_sync = temp_drive  # Usar este drive_sync para descargar
                    break
        
        # Si no se encontró por checksum, buscar por nombre (usando SKU del producto)
        if not file_info and product.canonical_sku:
            logger.info(f"Buscando archivo por nombre (SKU: {product.canonical_sku}) en todas las carpetas...")
            for folder_id, folder_name in folders_to_search:
                logger.info(f"  Buscando en carpeta '{folder_name}' ({folder_id})...")
                try:
                    temp_drive = GoogleDriveSync(drive_sync.credentials_path, folder_id)
                    await temp_drive.authenticate()
                    files = await temp_drive.list_images_in_folder()
                    for f in files:
                        if product.canonical_sku.lower() in f["name"].lower():
                            logger.info(f"Archivo potencial encontrado: {f['name']} (ID: {f['id']})")
                            # Verificar checksum si está disponible
                            if img.checksum_sha256:
                                try:
                                    content = await temp_drive.download_file(f["id"])
                                    file_checksum = hashlib.sha256(content).hexdigest()
                                    if file_checksum == img.checksum_sha256:
                                        file_info = f
                                        drive_sync = temp_drive
                                        logger.info("✓ Checksum coincide")
                                        break
                                except Exception:
                                    pass
                            else:
                                # Si no hay checksum, usar el primer archivo que coincida
                                file_info = f
                                drive_sync = temp_drive
                                break
                    if file_info:
                        break
                except Exception as e:
                    logger.debug(f"Error buscando en carpeta '{folder_name}': {e}")
                    continue
        
        if not file_info:
            logger.error("No se encontró el archivo en Google Drive")
            return False
        
        # Descargar archivo
        logger.info(f"Descargando archivo: {file_info['name']}...")
        try:
            content = await drive_sync.download_file(file_info["id"])
        except GoogleDriveError as e:
            logger.error(f"Error al descargar archivo: {e}")
            return False
        
        # Verificar checksum si está disponible
        if img.checksum_sha256:
            file_checksum = hashlib.sha256(content).hexdigest()
            if file_checksum != img.checksum_sha256:
                logger.warning(f"⚠ Checksum no coincide: esperado {img.checksum_sha256[:16]}..., obtenido {file_checksum[:16]}...")
                logger.warning("Continuando de todas formas...")
        
        # Guardar archivo en MEDIA_ROOT
        root = get_media_root()
        raw_dir = root / "Productos" / str(product.id) / "raw"
        raw_dir.mkdir(parents=True, exist_ok=True)
        
        # Determinar nombre del archivo
        filename = file_info["name"]
        if img.path:
            # Usar el nombre original del path si está disponible
            original_name = Path(img.path).name
            if original_name:
                filename = original_name
        
        target = raw_dir / filename
        
        # Si el archivo ya existe, agregar sufijo
        i = 1
        while target.exists():
            stem = Path(filename).stem
            ext = Path(filename).suffix
            target = raw_dir / f"{stem}-{i}{ext}"
            i += 1
        
        logger.info(f"Guardando archivo en: {target}")
        target.write_bytes(content)
        
        # Actualizar path en la DB si es diferente
        rel_path = str(target.relative_to(root))
        if img.path != rel_path:
            logger.info(f"Actualizando path en DB: {img.path} -> {rel_path}")
            img.path = rel_path
            # Normalizar separadores para URL
            rel_path_normalized = rel_path.replace('\\', '/')
            img.url = f"/media/{rel_path_normalized}"
            await db.commit()
            logger.info("✓ Path actualizado en la base de datos")
        
        logger.info(f"✓ Imagen restaurada exitosamente: {target}")
        return True


if __name__ == "__main__":
    import os
    import argparse
    
    parser = argparse.ArgumentParser(description="Restaurar imagen desde Google Drive")
    parser.add_argument("image_id", type=int, help="ID de la imagen a restaurar")
    parser.add_argument("--source-folder-id", type=str, help="ID de carpeta en Google Drive (opcional)")
    
    args = parser.parse_args()
    
    result = asyncio.run(restore_image(args.image_id, args.source_folder_id))
    sys.exit(0 if result else 1)

