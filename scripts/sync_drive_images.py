#!/usr/bin/env python
# NG-HEADER: Nombre de archivo: sync_drive_images.py
# NG-HEADER: Ubicación: scripts/sync_drive_images.py
# NG-HEADER: Descripción: Script para sincronizar imágenes desde Google Drive.
# NG-HEADER: Lineamientos: Ver AGENTS.md
"""Script para sincronizar imágenes de productos desde Google Drive.

El script:
1. Lista archivos de imagen en una carpeta Drive
2. Extrae SKU del nombre de archivo (formato: "SKU #")
3. Busca el producto por canonical_sku
4. Descarga y procesa la imagen
5. Mueve el archivo a "Procesados" o "Errores_SKU"
"""

from __future__ import annotations

import asyncio
import logging
import os
import re
import sys
import tempfile
from pathlib import Path
from typing import Optional

# FIX: Windows ProactorEventLoop no soporta psycopg async
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from db.models import Product, Image, ImageVersion, ImageReview
from db.session import SessionLocal
from services.integrations.drive import GoogleDriveSync, GoogleDriveError
from services.media import get_media_root, sha256_of_file
from services.media.processor import to_square_webp_set

# Configurar logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# Patrón regex para extraer SKU del nombre de archivo: "SKU #" o "SKU#"
SKU_PATTERN = re.compile(r"^(.+?)\s+(\d+)(?:\.[^.]+)?$", re.IGNORECASE)


def extract_sku_from_filename(filename: str) -> Optional[str]:
    """Extrae el SKU del nombre de archivo.

    Formato esperado: "SKU #" (ej: "ABC123 1.jpg" -> "ABC123")

    Args:
        filename: Nombre del archivo.

    Returns:
        SKU extraído o None si no coincide con el patrón.
    """
    # Remover extensión
    name_without_ext = Path(filename).stem
    match = SKU_PATTERN.match(name_without_ext)
    if match:
        sku = match.group(1).strip()
        logger.debug(f"SKU extraído de '{filename}': '{sku}'")
        return sku
    logger.warning(f"No se pudo extraer SKU de '{filename}' (no coincide con patrón)")
    return None


def detect_mime_type(content: bytes, filename: str) -> str:
    """Detecta el MIME type del contenido.

    Args:
        content: Contenido del archivo.
        filename: Nombre del archivo (para inferir por extensión).

    Returns:
        MIME type detectado.
    """
    # Verificar magic bytes
    if content.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if content.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if content.startswith(b"RIFF") and b"WEBP" in content[:12]:
        return "image/webp"
    if content.startswith(b"GIF87a") or content.startswith(b"GIF89a"):
        return "image/gif"

    # Fallback por extensión
    ext = Path(filename).suffix.lower()
    mime_map = {
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".png": "image/png",
        ".webp": "image/webp",
        ".gif": "image/gif",
    }
    return mime_map.get(ext, "application/octet-stream")


async def process_image_from_drive(
    drive_sync: GoogleDriveSync,
    file_info: dict,
    db: AsyncSession,
    processed_folder_id: str,
    errors_folder_id: str,
) -> None:
    """Procesa una imagen desde Drive.

    Args:
        drive_sync: Cliente de Google Drive.
        file_info: Metadata del archivo (id, name, mimeType).
        db: Sesión de base de datos.
        processed_folder_id: ID de carpeta "Procesados".
        errors_folder_id: ID de carpeta "Errores_SKU".
    """
    file_id = file_info["id"]
    filename = file_info["name"]
    logger.info(f"Procesando archivo: {filename} (ID: {file_id})")

    # Extraer SKU
    sku = extract_sku_from_filename(filename)
    if not sku:
        logger.warning(f"No se pudo extraer SKU de '{filename}', moviendo a errores")
        try:
            await drive_sync.move_file(file_id, errors_folder_id)
        except GoogleDriveError as e:
            logger.error(f"Error al mover archivo a errores: {e}")
        return

    # Buscar producto
    product = await db.scalar(select(Product).where(Product.canonical_sku == sku))
    if not product:
        logger.warning(f"Producto no encontrado para SKU '{sku}', moviendo a errores")
        try:
            await drive_sync.move_file(file_id, errors_folder_id)
        except GoogleDriveError as e:
            logger.error(f"Error al mover archivo a errores: {e}")
        return

    logger.info(f"Producto encontrado: ID={product.id}, SKU={sku}, Título={product.title}")

    # Descargar archivo
    try:
        content = await drive_sync.download_file(file_id)
    except GoogleDriveError as e:
        logger.error(f"Error al descargar archivo {filename}: {e}")
        return  # No mover archivo si falla la descarga

    # Guardar temporalmente
    mime_type = detect_mime_type(content, filename)
    temp_file: Optional[Path] = None
    try:
        with tempfile.NamedTemporaryFile(
            delete=False, suffix=Path(filename).suffix
        ) as tmp:
            tmp.write(content)
            temp_file = Path(tmp.name)

        # Calcular checksum
        checksum = sha256_of_file(temp_file)

        # Verificar duplicados
        exists_same = await db.scalar(
            select(Image.id).where(
                Image.product_id == product.id, Image.checksum_sha256 == checksum
            )
        )
        if exists_same:
            logger.info(
                f"Imagen duplicada (checksum {checksum[:8]}...), saltando. "
                f"Image ID existente: {exists_same}"
            )
            # Mover a procesados aunque sea duplicado (ya fue procesado)
            try:
                await drive_sync.move_file(file_id, processed_folder_id)
            except GoogleDriveError as e:
                logger.error(f"Error al mover archivo duplicado: {e}")
            return

        # Guardar imagen original
        root = get_media_root()
        raw_dir = root / "Productos" / str(product.id) / "raw"
        raw_dir.mkdir(parents=True, exist_ok=True)

        # Nombre seguro para el archivo
        safe_name = filename.replace("\\", "/").split("/")[-1]
        target = raw_dir / safe_name
        i = 1
        while target.exists():
            stem = "".join(safe_name.split(".")[:-1]) or safe_name
            ext = ("." + safe_name.split(".")[-1]) if "." in safe_name else ""
            target = raw_dir / f"{stem}-{i}{ext}"
            i += 1

        # Copiar desde temp a destino final
        import shutil

        shutil.copy2(temp_file, target)

        # Crear registro Image
        rel_path = str(target.relative_to(root))
        img = Image(
            product_id=product.id,
            url=f"/media/{rel_path}",
            path=rel_path,
            mime=mime_type,
            bytes=len(content),
            checksum_sha256=checksum,
        )
        db.add(img)
        await db.flush()

        # Crear ImageVersion original
        db.add(
            ImageVersion(
                image_id=img.id,
                kind="original",
                path=rel_path,
                size_bytes=len(content),
                mime=mime_type,
                source_url=f"drive://{file_id}",
            )
        )

        # Generar derivados (thumb, card, full)
        out_dir = root / "Productos" / str(product.id) / "derived"
        base = (
            "-".join([p for p in [product.slug or None, product.sku_root or None] if p])
            or f"prod-{product.id}"
        )
        proc = to_square_webp_set(target, out_dir, base)

        for kind, pth, px in (
            ("thumb", proc.thumb, 256),
            ("card", proc.card, 800),
            ("full", proc.full, 1600),
        ):
            relv = str(pth.relative_to(root))
            db.add(
                ImageVersion(
                    image_id=img.id,
                    kind=kind,
                    path=relv,
                    width=px,
                    height=px,
                    mime="image/webp",
                )
            )

        # Crear ImageReview
        db.add(ImageReview(image_id=img.id, status="pending"))

        await db.commit()
        logger.info(
            f"Imagen procesada exitosamente: Image ID={img.id}, Product ID={product.id}, SKU={sku}"
        )

        # Mover archivo a "Procesados"
        try:
            await drive_sync.move_file(file_id, processed_folder_id)
            logger.info(f"Archivo {filename} movido a carpeta Procesados")
        except GoogleDriveError as e:
            logger.error(f"Error al mover archivo a Procesados: {e}")
            # No hacer rollback, la imagen ya está guardada

    except Exception as e:
        logger.error(f"Error al procesar imagen {filename}: {e}", exc_info=True)
        await db.rollback()
        # No mover archivo si falla el procesamiento
    finally:
        # Limpiar archivo temporal
        if temp_file and temp_file.exists():
            try:
                temp_file.unlink()
            except Exception:
                pass


async def main() -> None:
    """Función principal del script."""
    # Leer configuración desde variables de entorno
    credentials_path = os.getenv("GOOGLE_APPLICATION_CREDENTIALS")
    if not credentials_path:
        logger.error("GOOGLE_APPLICATION_CREDENTIALS no está definido")
        sys.exit(1)

    source_folder_id = os.getenv("DRIVE_SOURCE_FOLDER_ID")
    if not source_folder_id:
        logger.error("DRIVE_SOURCE_FOLDER_ID no está definido")
        sys.exit(1)

    processed_folder_name = os.getenv("DRIVE_PROCESSED_FOLDER_NAME", "Procesados")
    errors_folder_name = os.getenv("DRIVE_ERRORS_FOLDER_NAME", "Errores_SKU")

    logger.info("Iniciando sincronización de imágenes desde Google Drive")
    logger.info(f"Carpeta origen: {source_folder_id}")
    logger.info(f"Carpeta procesados: {processed_folder_name}")
    logger.info(f"Carpeta errores: {errors_folder_name}")

    # Inicializar cliente Drive
    drive_sync = GoogleDriveSync(credentials_path, source_folder_id)

    try:
        # Autenticar
        await drive_sync.authenticate()

        # Crear/buscar carpetas destino
        processed_folder_id = await drive_sync.find_or_create_folder(
            source_folder_id, processed_folder_name
        )
        errors_folder_id = await drive_sync.find_or_create_folder(
            source_folder_id, errors_folder_name
        )

        # Listar archivos
        files = await drive_sync.list_images_in_folder()
        logger.info(f"Total de archivos a procesar: {len(files)}")

        if not files:
            logger.info("No hay archivos para procesar")
            return

        # Procesar cada archivo
        async with SessionLocal() as db:
            processed_count = 0
            error_count = 0

            for file_info in files:
                try:
                    await process_image_from_drive(
                        drive_sync, file_info, db, processed_folder_id, errors_folder_id
                    )
                    processed_count += 1
                except Exception as e:
                    logger.error(
                        f"Error inesperado al procesar {file_info.get('name', 'unknown')}: {e}",
                        exc_info=True,
                    )
                    error_count += 1

            logger.info(
                f"Sincronización completada: {processed_count} procesados, {error_count} errores"
            )

    except GoogleDriveError as e:
        logger.error(f"Error de Google Drive: {e}")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Error inesperado: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())

