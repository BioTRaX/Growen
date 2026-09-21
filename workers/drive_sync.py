# NG-HEADER: Nombre de archivo: drive_sync.py
# NG-HEADER: Ubicación: workers/drive_sync.py
# NG-HEADER: Descripción: Worker para sincronización de imágenes desde Google Drive con WebSocket.
# NG-HEADER: Lineamientos: Ver AGENTS.md
"""Worker para sincronizar imágenes desde Google Drive con reporte de progreso en tiempo real."""

from __future__ import annotations

import asyncio
import logging
import os
import re
import sys
import tempfile
from pathlib import Path
from typing import Optional, Callable, Any, Awaitable, Union

# FIX: Windows ProactorEventLoop no soporta psycopg async
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

from sqlalchemy import select, func, or_
from sqlalchemy.ext.asyncio import AsyncSession

from db.models import Product, Image, ImageVersion, ImageReview, CanonicalProduct, ProductEquivalence, SupplierProduct
from db.session import SessionLocal
from db.sku_utils import is_canonical_sku
from services.integrations.drive import GoogleDriveSync, GoogleDriveError
from services.media import get_media_root, sha256_of_file
from services.media.processor import to_square_webp_set

logger = logging.getLogger(__name__)

# Registrar soporte HEIF/HEIC si pillow-heif está instalado (requerido para imágenes iPhone)
try:
    from pillow_heif import register_heif_opener
    register_heif_opener()
    logger.debug("Opener HEIF/HEIC registrado para PIL")
except ImportError:
    # pillow-heif no está instalado, HEIF/HEIC no se podrán procesar
    logger.debug("pillow-heif no disponible, HEIF/HEIC no soportado")
except Exception:
    # Error al registrar (no crítico, solo afecta validación de HEIF)
    pass

from dataclasses import dataclass

# Patrón regex para SKU canónico con o sin adicionales:
# Formato canónico: 3 letras, 4 dígitos, 3 alfanuméricos (ej: FER_0001_ORG)
# Adicionales admitidos: " - 2", " Dorso", "_2", "-2", " (2)", " frente", etc.
CANONICAL_SKU_REGEX_STRICT = re.compile(r"^[A-Z]{3}_[0-9]{4}_[A-Z0-9]{3}$", re.IGNORECASE)
CANONICAL_SKU_EXTRACT_REGEX = re.compile(
    r"^([A-Z]{3}_[0-9]{4}_[A-Z0-9]{3})(?:[\s_\-]+(.+?))?$",
    re.IGNORECASE
)
SKU_PATTERN_WITH_NUMBER = re.compile(r"^(.+?)\s+(\d+)(?:\.[^.]+)?$", re.IGNORECASE)
SKU_PATTERN_DIRECT = re.compile(r"^([A-Z]{3}_[0-9]{4}_[A-Z0-9]{3})(?:\.[^.]+)?$", re.IGNORECASE)


@dataclass
class SkuParsedInfo:
    """Información analizada de SKU e imagen desde el nombre de archivo."""
    raw_sku: str
    canonical_sku: Optional[str]
    is_canonical: bool
    is_additional: bool
    additional_label: Optional[str] = None
    sort_order: int = 0

    @property
    def sku(self) -> str:
        """Devuelve el SKU canónico si existe, o el raw."""
        return self.canonical_sku or self.raw_sku


def parse_image_filename(filename: str) -> Optional[SkuParsedInfo]:
    """Analiza el nombre del archivo para extraer SKU y determinar si es imagen adicional.

    Soporta:
    - Principal: FER_0001_ORG.jpg, FER_0001_ORG 1.jpg, ABC_1234_XYZ.png
    - Adicionales: FER_0001_ORG - 2.jpg, FER_0001_ORG Dorso.jpg, FER_0001_ORG_2.png, FER_0001_ORG (2).heic
    """
    stem = Path(filename).stem.strip()

    # 1. Intentar patrón canónico con posible adicional
    canonical_search = re.search(r"([A-Za-z]{3}_[0-9]{4}_[A-Za-z0-9]{3})", stem)
    if canonical_search:
        raw_sku_matched = canonical_search.group(1)
        is_can = bool(is_canonical_sku(raw_sku_matched))
        can_sku = raw_sku_matched if is_can else None
        prefix = stem[:canonical_search.start()].strip(" -_()[]{}")
        suffix = stem[canonical_search.end():].strip(" -_()[]{}")

        additional_parts = [p for p in (prefix, suffix) if p]
        additional_text = " ".join(additional_parts).strip() if additional_parts else None

        is_additional = False
        additional_label = None
        sort_order = 0

        if additional_text:
            cleaned = additional_text.lower()
            if cleaned in ("1", "frente", "portada", "principal", "main"):
                is_additional = False
                additional_label = None
                sort_order = 0
            else:
                is_additional = True
                additional_label = additional_text
                # Extraer número si existe para ordenar la galería
                digits = re.search(r"\d+", additional_text)
                if digits:
                    val = int(digits.group(0))
                    sort_order = max(1, val - 1) if val > 1 else 1
                else:
                    sort_order = 1

        logger.debug(
            f"SKU extraído de '{filename}': {raw_sku_matched} (canónico={is_can}, adicional={is_additional}, label='{additional_label}', order={sort_order})"
        )
        return SkuParsedInfo(
            raw_sku=raw_sku_matched,
            canonical_sku=can_sku,
            is_canonical=is_can,
            is_additional=is_additional,
            additional_label=additional_label,
            sort_order=sort_order,
        )

    # 2. Intentar formato legacy con número: "SKU #"
    match_num = SKU_PATTERN_WITH_NUMBER.match(stem)
    if match_num:
        raw = match_num.group(1).strip(" -_")
        num = int(match_num.group(2))
        is_add = (num > 1)
        is_can = bool(is_canonical_sku(raw))
        can_val = raw.upper() if is_can else None
        return SkuParsedInfo(
            raw_sku=raw,
            canonical_sku=can_val,
            is_canonical=is_can,
            is_additional=is_add,
            additional_label=str(num) if is_add else None,
            sort_order=max(0, num - 1),
        )

    # 3. Intentar formato directo
    match_dir = SKU_PATTERN_DIRECT.match(stem)
    if match_dir:
        raw = match_dir.group(1).strip()
        is_can = bool(is_canonical_sku(raw))
        return SkuParsedInfo(
            raw_sku=raw,
            canonical_sku=raw.upper() if is_can else None,
            is_canonical=is_can,
            is_additional=False,
            additional_label=None,
            sort_order=0,
        )

    logger.warning(f"No se pudo extraer SKU de '{filename}' (no coincide con patrones)")
    return None


def extract_sku_from_filename(filename: str) -> Optional[str]:
    """Extrae el SKU del nombre de archivo (mantiene compatibilidad)."""
    parsed = parse_image_filename(filename)
    if parsed:
        return parsed.raw_sku
    return None


def detect_mime_type(content: bytes, filename: str) -> str:
    """Detecta el MIME type del contenido."""
    if content.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if content.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if content.startswith(b"RIFF") and b"WEBP" in content[:12]:
        return "image/webp"
    if content.startswith(b"GIF87a") or content.startswith(b"GIF89a"):
        return "image/gif"
    # HEIF/HEIC: formato usado por iPhone y dispositivos modernos
    # Magic bytes: ftyp (file type box) seguido de heic/heif/mif1
    if content.startswith(b"ftyp") and (b"heic" in content[:20] or b"heif" in content[:20] or b"mif1" in content[:20]):
        return "image/heic"
    if len(content) >= 12 and content[4:8] == b"ftyp" and (b"heic" in content[8:24] or b"heif" in content[8:24] or b"mif1" in content[8:24]):
        return "image/heic"

    ext = Path(filename).suffix.lower()
    mime_map = {
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".png": "image/png",
        ".webp": "image/webp",
        ".gif": "image/gif",
        ".heif": "image/heif",
        ".heic": "image/heic",
    }
    return mime_map.get(ext, "application/octet-stream")


async def sync_drive_images(
    progress_callback: Optional[Callable[[dict[str, Any]], Union[None, Awaitable[None]]]] = None,
    source_folder_id: Optional[str] = None,
    include_filenames: Optional[list[str]] = None,
) -> dict[str, Any]:
    """Sincroniza imágenes desde Google Drive.

    Args:
        progress_callback: Función opcional para reportar progreso en tiempo real.
            Recibe un dict con: status, current, total, sku, message, error
        source_folder_id: ID de carpeta de origen (opcional). Si no se proporciona,
            se usa DRIVE_SOURCE_FOLDER_ID del entorno. Permite procesar desde otras
            carpetas como "Errores_SKU".

    Returns:
        Dict con resumen: processed, errors, no_sku, total
    """
    # Leer configuración
    credentials_path = os.getenv("GOOGLE_APPLICATION_CREDENTIALS")
    if not credentials_path:
        raise ValueError("GOOGLE_APPLICATION_CREDENTIALS no está definido")

    # Obtener carpeta principal (siempre la misma, para crear carpetas destino)
    env_folder_id = (os.getenv("DRIVE_SOURCE_FOLDER_ID") or "").strip()
    if not source_folder_id:
        if not env_folder_id or env_folder_id == "REEMPLAZAR_CON_ID_CARPETA":
            raise ValueError("DRIVE_SOURCE_FOLDER_ID no está configurado en .env")
        source_folder_id = env_folder_id
    main_folder_id = env_folder_id or source_folder_id

    processed_folder_name = os.getenv("DRIVE_PROCESSED_FOLDER_NAME", "Procesados")
    errors_folder_name = os.getenv("DRIVE_ERRORS_FOLDER_NAME", "Errores_SKU")
    no_sku_folder_name = os.getenv("DRIVE_SIN_SKU_FOLDER_NAME", "SIN_SKU")
    debug_mode = os.getenv("DEBUG", "false").lower() in ("true", "1", "yes")

    async def emit_progress(
        status: str, 
        current: int = 0, 
        total: int = 0, 
        sku: str = "", 
        filename: str = "",
        message: str = "", 
        error: str = "",
        processed: int = 0,
        errors: int = 0,
        no_sku: int = 0,
        items: list[dict] | None = None,
    ):
        """Helper para emitir progreso con estadísticas."""
        remaining = total - current if total > 0 else 0
        if progress_callback:
            data = {
                "status": status,
                "current": current,
                "total": total,
                "remaining": remaining,
                "sku": sku,
                "filename": filename,
                "message": message,
                "error": error,
                "stats": {
                    "processed": processed,
                    "errors": errors,
                    "no_sku": no_sku,
                },
                "items": items,
            }
            # Si el callback es async, usar await
            if asyncio.iscoroutinefunction(progress_callback):
                await progress_callback(data)
            else:
                progress_callback(data)

    await emit_progress("initializing", message="Inicializando sincronización...")

    # Resolver ruta relativa si es necesario
    creds_path_resolved = Path(credentials_path)
    if not creds_path_resolved.is_absolute():
        # Resolver desde el directorio raíz del proyecto
        project_root = Path(__file__).resolve().parent.parent
        creds_path_resolved = project_root / creds_path_resolved

    # Inicializar cliente Drive
    drive_sync = GoogleDriveSync(str(creds_path_resolved), source_folder_id)
    await drive_sync.authenticate()

    # Crear/buscar carpetas destino
    # IMPORTANTE: Las carpetas destino siempre se crean en la carpeta principal,
    # no en la carpeta de origen (para evitar crear carpetas dentro de Errores_SKU)
    await emit_progress("initializing", message="Buscando/creando carpetas destino...")
    processed_folder_id = await drive_sync.find_or_create_folder(
        main_folder_id, processed_folder_name
    )
    errors_folder_id = await drive_sync.find_or_create_folder(
        main_folder_id, errors_folder_name
    )
    no_sku_folder_id = await drive_sync.find_or_create_folder(
        main_folder_id, no_sku_folder_name
    )

    # Listar archivos (solo en carpeta raíz, excluir subcarpetas)
    await emit_progress("listing", message="Listando archivos en carpeta origen...")
    files = await drive_sync.list_images_in_folder()
    logger.info(f"Total archivos encontrados en Drive: {len(files)}")
    
    # Filtrar archivos que NO están en subcarpetas (solo en source_folder_id)
    # Los archivos listados ya están filtrados por 'source_folder_id' in parents,
    # pero pueden estar en subcarpetas. Necesitamos verificar que solo tengan
    # source_folder_id como padre directo.
    files_in_root = []
    processed_folder_name = os.getenv("DRIVE_PROCESSED_FOLDER_NAME", "Procesados")
    errors_folder_name = os.getenv("DRIVE_ERRORS_FOLDER_NAME", "Errores_SKU")
    no_sku_folder_name = os.getenv("DRIVE_SIN_SKU_FOLDER_NAME", "SIN_SKU")
    
    # Obtener IDs de carpetas destino para excluirlas
    # IMPORTANTE: Usar main_folder_id (carpeta principal) para crear carpetas destino,
    # no source_folder_id (para evitar crear carpetas dentro de Errores_SKU)
    # Nota: find_or_create_folder espera (parent_id, folder_name)
    processed_folder_id = await drive_sync.find_or_create_folder(main_folder_id, processed_folder_name)
    errors_folder_id = await drive_sync.find_or_create_folder(main_folder_id, errors_folder_name)
    no_sku_folder_id = await drive_sync.find_or_create_folder(main_folder_id, no_sku_folder_name)
    # Construir lista de carpetas excluidas
    # Si estamos procesando desde Errores_SKU, no excluir Errores_SKU (es la carpeta de origen)
    excluded_folder_ids = {processed_folder_id, no_sku_folder_id}
    if source_folder_id != errors_folder_id:
        # Solo excluir Errores_SKU si NO es la carpeta de origen
        excluded_folder_ids.add(errors_folder_id)
    
    logger.info(f"Carpetas excluidas: {excluded_folder_ids} (source_folder_id: {source_folder_id}, errors_folder_id: {errors_folder_id})")
    
    for file_info in files:
        # Verificar que el archivo esté directamente en source_folder_id
        # (no en subcarpetas como Procesados, SIN_SKU, o Errores_SKU si no es la carpeta de origen)
        try:
            # Obtener metadata del archivo para verificar padres (ejecutar en thread para no bloquear)
            def get_file_metadata():
                return drive_sync.service.files().get(
                    fileId=file_info["id"], fields="parents"
                ).execute()
            
            file_metadata = await asyncio.to_thread(get_file_metadata)
            parents = file_metadata.get("parents", [])
            logger.debug(f"Archivo {file_info.get('name')}: padres={parents}")
            
            # Solo incluir si tiene source_folder_id como único padre
            # y no está en ninguna carpeta excluida
            if source_folder_id in parents and len(parents) == 1:
                # Verificar que no esté en una carpeta excluida
                if not any(pid in excluded_folder_ids for pid in parents):
                    files_in_root.append(file_info)
                    logger.debug(f"Archivo incluido: {file_info.get('name')}")
                else:
                    logger.debug(f"Archivo excluido (en carpeta destino): {file_info.get('name')}, padres={parents}")
            else:
                logger.debug(f"Archivo excluido (múltiples padres o no en source): {file_info.get('name')}, padres={parents}")
        except Exception as e:
            logger.warning(f"Error al verificar padres de {file_info.get('name')}: {e}", exc_info=True)
            # En caso de error, NO incluir por seguridad (evitar procesar archivos en subcarpetas)

    if include_filenames:
        allowed_names = set(include_filenames)
        files_in_root = [item for item in files_in_root if item.get("name") in allowed_names]

    total_files = len(files_in_root)
    await emit_progress(
        "processing", 
        current=0, 
        total=total_files, 
        message=f"Encontrados {total_files} archivos a procesar",
        processed=0,
        errors=0,
        no_sku=0,
        items=[{"source_file_id": item.get("id"), "filename": item.get("name", "")} for item in files_in_root],
    )

    if total_files == 0:
        await emit_progress(
            "completed", 
            current=0,
            total=0, 
            sku="",
            filename="",
            message="No hay archivos para procesar",
            processed=0,
            errors=0,
            no_sku=0,
        )
        return {
            "processed": 0,
            "errors": 0,
            "no_sku": 0,
            "total": 0,
        }

    # Contadores
    processed_count = 0
    error_count = 0
    no_sku_count = 0

    # Procesar cada archivo
    async with SessionLocal() as db:
        for idx, file_info in enumerate(files_in_root, 1):
            file_id = file_info["id"]
            filename = file_info["name"]

            try:
                # Extraer y analizar SKU (detectando adicionales como - 2, Dorso, etc.)
                logger.debug(f"Extrayendo SKU de archivo: '{filename}'")
                parsed_info = parse_image_filename(filename)
                if not parsed_info or not parsed_info.raw_sku:
                    logger.warning(f"No se pudo extraer SKU de '{filename}'")
                    remaining = total_files - idx
                    await emit_progress(
                        "processing",
                        current=idx,
                        total=total_files,
                        sku="",
                        filename=filename,
                        message=f"Archivo sin formato SKU válido: {filename} ({idx}/{total_files}, faltan {remaining})",
                        processed=processed_count,
                        errors=error_count,
                        no_sku=no_sku_count + 1,
                    )
                    try:
                        await drive_sync.move_file(file_id, no_sku_folder_id)
                    except Exception as e:
                        logger.error(f"Error al mover archivo {filename} a SIN_SKU: {e}")
                    no_sku_count += 1
                    continue

                sku = parsed_info.canonical_sku or parsed_info.raw_sku

                # Validar que sea SKU canónico
                logger.debug(f"Validando si SKU '{sku}' es canónico")
                if not parsed_info.is_canonical and not is_canonical_sku(sku):
                    logger.warning(f"SKU '{sku}' extraído de '{filename}' NO es canónico")
                    remaining = total_files - idx
                    await emit_progress(
                        "processing",
                        current=idx,
                        total=total_files,
                        sku=sku,
                        filename=filename,
                        message=f"SKU no canónico: {sku} ({idx}/{total_files}, faltan {remaining})",
                        processed=processed_count,
                        errors=error_count,
                        no_sku=no_sku_count + 1,
                    )
                    try:
                        await drive_sync.move_file(file_id, no_sku_folder_id)
                    except Exception as e:
                        logger.error(f"Error al mover archivo {filename} a SIN_SKU: {e}")
                    no_sku_count += 1
                    continue

                remaining = total_files - idx
                await emit_progress(
                    "processing",
                    current=idx,
                    total=total_files,
                    sku=sku,
                    filename=filename,
                    message=f"Procesando SKU {sku} ({idx}/{total_files}, faltan {remaining})",
                    processed=processed_count,
                    errors=error_count,
                    no_sku=no_sku_count,
                )

                # Buscar producto: PRIMERO por canonical_sku (formato preferido XXX_####_YYY),
                # luego por sku_root como fallback (solo para sistema/proveedor/deprecado)
                logger.info(f"Buscando producto para SKU canónico: '{sku}' (filename: '{filename}')")
                logger.debug(f"  - Búsqueda 1 (PREFERIDA): Product.canonical_sku == '{sku}'")
                # DIAGNÓSTICO: Verificar que la sesión puede leer productos
                test_count = await db.scalar(select(func.count(Product.id)))
                logger.debug(f"  - DIAGNÓSTICO: Total productos en BD (según worker): {test_count}")
                product = await db.scalar(select(Product).where(Product.canonical_sku == sku))
                if product:
                    logger.info(f"  ✓ Producto encontrado por canonical_sku: ID={product.id}, canonical_sku='{product.canonical_sku}', sku_root='{product.sku_root}'")
                else:
                    logger.debug(f"  ✗ Producto NO encontrado por canonical_sku='{sku}'")
                    # DIAGNÓSTICO: Buscar productos con SKU similar para ver qué hay en la BD
                    similar = await db.scalars(
                        select(Product).where(Product.canonical_sku.like(f"%{sku[:7]}%")).limit(3)
                    )
                    similar_list = list(similar)
                    if similar_list:
                        logger.debug(f"  - DIAGNÓSTICO: Productos con SKU similar encontrados:")
                        for p in similar_list:
                            logger.debug(f"    - ID={p.id}: canonical_sku='{p.canonical_sku}', sku_root='{p.sku_root}'")
                    # Búsqueda 2: Buscar en CanonicalProduct directamente (antes de fallback a sku_root)
                    # Esto es importante porque CanonicalProduct puede tener el SKU correcto aunque Product no
                    logger.debug(f"  - Búsqueda 2: Buscando en CanonicalProduct (sku_custom o ng_sku)...")
                    canonical = await db.scalar(
                        select(CanonicalProduct).where(
                            or_(
                                CanonicalProduct.sku_custom == sku,
                                CanonicalProduct.ng_sku == sku,
                                func.lower(CanonicalProduct.sku_custom) == sku.lower(),
                                func.lower(CanonicalProduct.ng_sku) == sku.lower(),
                            )
                        )
                    )
                    if canonical:
                        logger.info(f"  ✓ CanonicalProduct encontrado: ID={canonical.id}, sku_custom='{canonical.sku_custom}', ng_sku='{canonical.ng_sku}'")
                        # Buscar Product asociado a través de ProductEquivalence -> SupplierProduct
                        supplier_product = await db.scalar(
                            select(SupplierProduct)
                            .join(ProductEquivalence, ProductEquivalence.supplier_product_id == SupplierProduct.id)
                            .where(ProductEquivalence.canonical_product_id == canonical.id)
                            .limit(1)
                        )
                        if supplier_product and supplier_product.internal_product_id:
                            product = await db.get(Product, supplier_product.internal_product_id)
                            if product:
                                logger.info(f"  ✓ Producto encontrado vía CanonicalProduct: ID={product.id}, canonical_sku='{product.canonical_sku}', sku_root='{product.sku_root}'")
                                # Si el Product tiene un canonical_sku diferente, actualizarlo para futuras búsquedas
                                if product.canonical_sku != canonical.sku_custom and canonical.sku_custom:
                                    logger.info(f"  → Actualizando Product.canonical_sku de '{product.canonical_sku}' a '{canonical.sku_custom}'")
                                    product.canonical_sku = canonical.sku_custom
                                    await db.commit()
                            else:
                                logger.warning(f"  ⚠ CanonicalProduct encontrado pero Product.internal_product_id={supplier_product.internal_product_id} no existe")
                        else:
                            logger.warning(f"  ⚠ CanonicalProduct encontrado pero no hay SupplierProduct asociado")
                    else:
                        logger.debug(f"  ✗ CanonicalProduct NO encontrado")
                        # Búsqueda 3 (FALLBACK): Product.sku_root (solo para SKUs de sistema/proveedor/deprecado)
                        logger.debug(f"  - Búsqueda 3 (FALLBACK): Product.sku_root == '{sku}' (solo para SKUs de sistema/proveedor/deprecado)")
                        product = await db.scalar(select(Product).where(Product.sku_root == sku))
                        if product:
                            logger.warning(f"  ⚠ Producto encontrado por sku_root (fallback): ID={product.id}, canonical_sku='{product.canonical_sku}', sku_root='{product.sku_root}'")
                            logger.warning(f"  ⚠ NOTA: El SKU '{sku}' está en sku_root pero no en canonical_sku. Considerar migrar a canonical_sku.")
                        else:
                            logger.warning(f"  ✗ Producto NO encontrado para SKU '{sku}' (buscado en canonical_sku, CanonicalProduct y sku_root)")
                            # Intentar búsqueda case-insensitive como último recurso
                            logger.debug(f"  - Búsqueda 4: Intentando búsqueda case-insensitive...")
                            product_ci = await db.scalar(
                                select(Product).where(
                                    func.lower(Product.canonical_sku) == sku.lower()
                                )
                            )
                            if not product_ci:
                                product_ci = await db.scalar(
                                    select(Product).where(
                                        func.lower(Product.sku_root) == sku.lower()
                                    )
                                )
                            if product_ci:
                                logger.warning(f"  ⚠ Producto encontrado con búsqueda case-insensitive: ID={product_ci.id}, canonical_sku='{product_ci.canonical_sku}', sku_root='{product_ci.sku_root}'")
                                logger.warning(f"  ⚠ El SKU en la DB es diferente al buscado (posible problema de mayúsculas/minúsculas)")
                                product = product_ci
                            else:
                                logger.error(f"  ✗ Producto NO encontrado ni con búsqueda case-insensitive para SKU '{sku}'")
                                # Buscar productos similares para diagnóstico
                                logger.debug(f"  - Diagnóstico: Buscando productos con SKU similar...")
                                similar_products = await db.scalars(
                                    select(Product).where(
                                        or_(
                                            Product.canonical_sku.like(f"%{sku[:7]}%"),  # Buscar por prefijo (ej: "FER_0009")
                                            Product.sku_root.like(f"%{sku[:7]}%")
                                        )
                                    ).limit(5)
                                )
                                similar = list(similar_products)
                                if similar:
                                    logger.warning(f"  ⚠ Productos similares encontrados (primeros 5):")
                                    for p in similar:
                                        logger.warning(f"    - ID={p.id}: canonical_sku='{p.canonical_sku}', sku_root='{p.sku_root}'")
                                else:
                                    logger.debug(f"  - No se encontraron productos similares")
                if not product:
                    remaining = total_files - idx
                    error_msg = f"Producto no encontrado para SKU '{sku}' (buscado en canonical_sku y sku_root)"
                    logger.warning(f"SKU '{sku}': {error_msg}")
                    await emit_progress(
                        "processing",
                        current=idx,
                        total=total_files,
                        sku=sku,
                        filename=filename,
                        message=f"SKU {sku}: {error_msg} ({idx}/{total_files}, faltan {remaining})",
                        error=error_msg,
                        processed=processed_count,
                        errors=error_count + 1,
                        no_sku=no_sku_count,
                    )
                    
                    # Guardar log de error si está en modo debug
                    if debug_mode:
                        try:
                            error_log_path = await _save_error_log(
                                drive_sync, errors_folder_id, filename, sku, error_msg
                            )
                        except Exception as e:
                            logger.warning(f"No se pudo guardar log de error: {e}")
                    
                    try:
                        await drive_sync.move_file(file_id, errors_folder_id)
                    except Exception as e:
                        logger.error(f"Error al mover archivo {filename} a Errores_SKU: {e}")
                    error_count += 1
                    continue

                # Verificar idempotencia: ¿la imagen ya fue descargada anteriormente para este producto?
                safe_name_check = filename.replace("\\", "/").split("/")[-1]
                already_downloaded = await db.scalar(
                    select(Image.id)
                    .join(ImageVersion, ImageVersion.image_id == Image.id)
                    .where(
                        Image.product_id == product.id,
                        Image.active == True,
                        ImageVersion.source_url == f"drive://{file_id}",
                    )
                    .limit(1)
                )
                if not already_downloaded:
                    already_downloaded = await db.scalar(
                        select(Image.id)
                        .where(
                            Image.product_id == product.id,
                            Image.active == True,
                            or_(
                                Image.path.like(f"%/{safe_name_check}"),
                                Image.path.like(f"%\\{safe_name_check}"),
                            )
                        )
                        .limit(1)
                    )

                if already_downloaded:
                    # Verificar si el archivo físico realmente existe en disco
                    existing_image = await db.get(Image, already_downloaded)
                    if existing_image and existing_image.path:
                        root_check = get_media_root()
                        if (root_check / existing_image.path).exists():
                            logger.info(f"Imagen '{filename}' ya fue descargada previamente para producto {product.id} (Image ID {already_downloaded}). Saltando re-descarga.")
                            remaining = total_files - idx
                            await emit_progress(
                                "processing",
                                current=idx,
                                total=total_files,
                                sku=sku,
                                filename=filename,
                                message=f"⏩ SKU {sku}: Imagen ya descargada previamente ({filename}), omitiendo descarga ({idx}/{total_files}, faltan {remaining})",
                                processed=processed_count + 1,
                                errors=error_count,
                                no_sku=no_sku_count,
                            )
                            processed_count += 1
                            try:
                                await drive_sync.move_file(file_id, processed_folder_id)
                            except Exception as e:
                                logger.warning(f"No se pudo mover archivo {filename} a Procesados: {e}")
                            continue

                # Descargar y procesar
                try:
                    content = await drive_sync.download_file(file_id)
                except GoogleDriveError as e:
                    remaining = total_files - idx
                    error_msg = f"Error al descargar archivo: {e}"
                    await emit_progress(
                        "processing",
                        current=idx,
                        total=total_files,
                        sku=sku,
                        filename=filename,
                        message=f"SKU {sku}: {error_msg} ({idx}/{total_files}, faltan {remaining})",
                        error=error_msg,
                        processed=processed_count,
                        errors=error_count + 1,
                        no_sku=no_sku_count,
                    )
                    if debug_mode:
                        try:
                            await _save_error_log(
                                drive_sync, errors_folder_id, filename, sku, error_msg
                            )
                        except Exception:
                            pass
                    error_count += 1
                    continue

                # Procesar imagen
                try:
                    await _process_image(
                        content,
                        filename,
                        product,
                        db,
                        file_id,
                        drive_sync,
                        processed_folder_id,
                        is_additional=parsed_info.is_additional,
                        additional_label=parsed_info.additional_label,
                        sort_order=parsed_info.sort_order,
                    )
                    remaining = total_files - idx
                    img_type_label = f" (adicional: {parsed_info.additional_label})" if parsed_info.is_additional else " (principal)"
                    await emit_progress(
                        "processing",
                        current=idx,
                        total=total_files,
                        sku=sku,
                        filename=filename,
                        message=f"✅ SKU {sku} procesado exitosamente{img_type_label} ({idx}/{total_files}, faltan {remaining})",
                        processed=processed_count + 1,
                        errors=error_count,
                        no_sku=no_sku_count,
                    )
                    processed_count += 1
                except Exception as e:
                    remaining = total_files - idx
                    error_msg = f"Error al procesar imagen: {e}"
                    logger.error(f"Error procesando {filename}: {e}", exc_info=True)
                    await emit_progress(
                        "processing",
                        current=idx,
                        total=total_files,
                        sku=sku,
                        filename=filename,
                        message=f"SKU {sku}: {error_msg} ({idx}/{total_files}, faltan {remaining})",
                        error=error_msg,
                        processed=processed_count,
                        errors=error_count + 1,
                        no_sku=no_sku_count,
                    )
                    if debug_mode:
                        try:
                            await _save_error_log(
                                drive_sync, errors_folder_id, filename, sku, error_msg
                            )
                        except Exception:
                            pass
                    try:
                        await db.rollback()
                    except Exception:
                        pass
                    try:
                        await drive_sync.move_file(file_id, errors_folder_id)
                    except Exception as e:
                        logger.error(f"Error al mover archivo {filename} a Errores_SKU: {e}")
                    error_count += 1

            except Exception as e:
                remaining = total_files - idx if total_files > 0 else 0
                logger.error(f"Error inesperado procesando {filename}: {e}", exc_info=True)
                await emit_progress(
                    "processing",
                    current=idx,
                    total=total_files,
                    sku="",
                    filename=filename,
                    message=f"Error inesperado con {filename}: {str(e)[:100]} ({idx}/{total_files}, faltan {remaining})",
                    error=str(e)[:200],
                    processed=processed_count,
                    errors=error_count + 1,
                    no_sku=no_sku_count,
                )
                # Intentar mover a errores si es posible
                try:
                    await drive_sync.move_file(file_id, errors_folder_id)
                except Exception:
                    pass
                error_count += 1

    await emit_progress(
        "completed",
        current=total_files,
        total=total_files,
        sku="",
        filename="",
        message=f"Sincronización completada: {processed_count} procesados, {error_count} errores, {no_sku_count} sin SKU",
        processed=processed_count,
        errors=error_count,
        no_sku=no_sku_count,
    )

    return {
        "processed": processed_count,
        "errors": error_count,
        "no_sku": no_sku_count,
        "total": total_files,
    }


async def _process_image(
    content: bytes,
    filename: str,
    product: Product,
    db: AsyncSession,
    file_id: str,
    drive_sync: GoogleDriveSync,
    processed_folder_id: str,
    is_additional: bool = False,
    additional_label: Optional[str] = None,
    sort_order: int = 0,
) -> None:
    """Procesa una imagen descargada y la asocia al producto."""
    import shutil

    mime_type = detect_mime_type(content, filename)
    temp_file: Optional[Path] = None

    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=Path(filename).suffix) as tmp:
            tmp.write(content)
            temp_file = Path(tmp.name)

        checksum = sha256_of_file(temp_file)

        # Verificar duplicados (solo si el archivo físico existe)
        exists_same = await db.scalar(
            select(Image.id).where(
                Image.product_id == product.id, Image.checksum_sha256 == checksum
            )
        )
        if exists_same:
            # Verificar que el archivo físico realmente existe
            existing_img = await db.get(Image, exists_same)
            if existing_img and existing_img.path:
                root = get_media_root()
                physical_path = root / existing_img.path
                if physical_path.exists():
                    logger.info(
                        f"Imagen duplicada (checksum {checksum[:8]}...), archivo físico existe. "
                        f"Saltando descarga. (Image ID {exists_same})"
                    )
                    await drive_sync.move_file(file_id, processed_folder_id)
                    return
                else:
                    logger.warning(
                        f"Imagen duplicada en DB pero archivo físico NO existe "
                        f"(Image ID {exists_same}, path: {existing_img.path}). "
                        f"Eliminando registro huérfano y re-descargando desde Drive..."
                    )
                    await db.delete(existing_img)
                    await db.flush()
                    logger.info(
                        f"Registro huérfano eliminado (Image ID {exists_same}). "
                        f"Continuando con descarga para producto {product.id} (SKU: {product.canonical_sku or product.sku_root})..."
                    )
            else:
                logger.warning(
                    f"Imagen duplicada en DB pero sin path registrado (Image ID {exists_same}). "
                    f"Eliminando registro huérfano y re-descargando desde Drive..."
                )
                await db.delete(existing_img)
                await db.flush()
                logger.info(
                    f"Registro huérfano eliminado (Image ID {exists_same}). "
                    f"Continuando con descarga para producto {product.id} (SKU: {product.canonical_sku or product.sku_root})..."
                )

        # Guardar imagen original
        root = get_media_root()
        logger.info(f"Guardando imagen para producto {product.id} en MEDIA_ROOT: {root}")
        raw_dir = root / "Productos" / str(product.id) / "raw"
        raw_dir.mkdir(parents=True, exist_ok=True)
        logger.debug(f"Directorio creado/verificado: {raw_dir}")

        safe_name = filename.replace("\\", "/").split("/")[-1]
        logger.debug(f"Nombre original del archivo: {filename}, nombre seguro: {safe_name}")
        
        # Si el archivo no tiene extensión, intentar agregarla basándose en MIME o magic bytes
        if not Path(safe_name).suffix:
            ext = None
            if mime_type.startswith("image/"):
                ext_map = {
                    "image/jpeg": ".jpg",
                    "image/png": ".png",
                    "image/webp": ".webp",
                    "image/gif": ".gif",
                    "image/heif": ".heic",
                    "image/heic": ".heic",
                }
                ext = ext_map.get(mime_type)
            
            if not ext:
                content_preview = content[:20] if len(content) >= 20 else content
                if content_preview.startswith(b'\xff\xd8\xff'):
                    ext = ".jpg"
                elif content_preview.startswith(b'\x89PNG\r\n\x1a\n'):
                    ext = ".png"
                elif content_preview.startswith(b'RIFF') and b'WEBP' in content_preview[:12]:
                    ext = ".webp"
                elif content_preview.startswith(b'GIF87a') or content_preview.startswith(b'GIF89a'):
                    ext = ".gif"
                elif content_preview.startswith(b'ftyp') or (len(content) >= 12 and content[4:8] == b'ftyp'):
                    ext = ".heic"
            
            if ext:
                safe_name = f"{safe_name}{ext}"
                logger.info(f"Agregada extensión {ext} al archivo sin extensión (MIME: {mime_type})")
            else:
                logger.warning(f"No se pudo determinar extensión para archivo {safe_name} (MIME: {mime_type})")
        
        target = raw_dir / safe_name
        i = 1
        while target.exists():
            stem = Path(safe_name).stem
            ext = Path(safe_name).suffix
            target = raw_dir / f"{stem}-{i}{ext}"
            i += 1

        logger.info(f"Copiando archivo temporal a: {target}")
        shutil.copy2(temp_file, target)
        logger.info(f"Archivo copiado exitosamente. Tamaño: {target.stat().st_size} bytes")

        # Validar que la imagen se pueda abrir (verificar integridad)
        try:
            from PIL import Image as PILImage
            file_size = target.stat().st_size
            if file_size < 100:
                raise ValueError(f"Archivo demasiado pequeño para ser una imagen válida: {file_size} bytes")
            
            with PILImage.open(target) as img_test:
                img_test.load()
                if img_test.size[0] <= 0 or img_test.size[1] <= 0:
                    raise ValueError(f"Imagen con dimensiones inválidas: {img_test.size}")
                img_width, img_height = img_test.size
            logger.debug(f"Imagen validada correctamente: {target} ({img_width}x{img_height}, {file_size} bytes)")
        except ImportError:
            logger.warning("PIL no disponible, saltando validación de imagen")
        except Exception as e:
            logger.error(f"Imagen corrupta o inválida {target}: {e}", exc_info=True)
            try:
                target.unlink()
            except Exception:
                pass
            raise ValueError(f"La imagen descargada está corrupta o es inválida: {e}")

        # Determinar si será primaria y calcular su sort_order
        has_primary = await db.scalar(
            select(Image.id).where(
                Image.product_id == product.id,
                Image.active == True,
                Image.is_primary == True,
            ).limit(1)
        )
        is_primary = False
        if not is_additional and not has_primary:
            is_primary = True

        effective_sort_order = sort_order
        if is_additional and effective_sort_order <= 0:
            max_order = await db.scalar(
                select(func.max(Image.sort_order)).where(
                    Image.product_id == product.id,
                    Image.active == True,
                )
            ) or 0
            effective_sort_order = max_order + 1

        # Crear registro Image
        rel_path = str(target.relative_to(root))
        rel_path_normalized = rel_path.replace('\\', '/')
        img = Image(
            product_id=product.id,
            url=f"/media/{rel_path_normalized}",
            path=rel_path,
            mime=mime_type,
            bytes=len(content),
            checksum_sha256=checksum,
            is_primary=is_primary,
            sort_order=effective_sort_order,
            alt_text=f"{product.title} - {additional_label}" if additional_label else product.title,
            title_text=additional_label,
        )
        db.add(img)
        await db.flush()

        # Crear ImageVersion original
        db.add(
            ImageVersion(
                image_id=img.id,
                kind="original",
                path=rel_path_normalized,
                size_bytes=len(content),
                mime=mime_type,
                source_url=f"drive://{file_id}",
            )
        )

        # Generar derivados WebP (square set)
        out_dir = root / "Productos" / str(product.id) / "derived"
        base = (
            "-".join([p for p in [product.slug or None, product.sku_root or None] if p])
            or f"prod-{product.id}"
        )
        proc = to_square_webp_set(target, out_dir, base)

        card_rel_path: Optional[str] = None
        for kind, pth, px in (
            ("thumb", proc.thumb, 256),
            ("card", proc.card, 800),
            ("full", proc.full, 1600),
        ):
            relv = str(pth.relative_to(root))
            relv_normalized = relv.replace('\\', '/')
            if kind == "card":
                card_rel_path = relv_normalized
            db.add(
                ImageVersion(
                    image_id=img.id,
                    kind=kind,
                    path=relv_normalized,
                    width=px,
                    height=px,
                    mime="image/webp",
                )
            )

        # Si el formato es HEIC/HEIF, actualizar img.url hacia la derivada WebP para que los navegadores puedan mostrarla directamente
        if mime_type in ("image/heic", "image/heif") and card_rel_path:
            img.url = f"/media/{card_rel_path}"

        # Crear ImageReview
        db.add(ImageReview(image_id=img.id, status="pending"))

        await db.commit()

        # Mover archivo a "Procesados"
        await drive_sync.move_file(file_id, processed_folder_id)

    finally:
        if temp_file and temp_file.exists():
            try:
                temp_file.unlink()
            except Exception:
                pass


async def _save_error_log(
    drive_sync: GoogleDriveSync,
    errors_folder_id: str,
    filename: str,
    sku: str,
    error_msg: str,
) -> Optional[str]:
    """Guarda un archivo de log de error en la carpeta de errores (modo debug)."""
    try:
        import io
        from datetime import datetime

        log_content = f"""Error al procesar imagen desde Google Drive
Fecha: {datetime.utcnow().isoformat()}
Archivo: {filename}
SKU: {sku}
Error: {error_msg}
"""
        log_bytes = log_content.encode("utf-8")
        log_file = io.BytesIO(log_bytes)

        # Crear archivo de texto en Drive
        file_metadata = {
            "name": f"{Path(filename).stem}_error.txt",
            "parents": [errors_folder_id],
        }
        media = drive_sync.service.files().create(
            body=file_metadata,
            media_body=io.BytesIO(log_bytes),
            fields="id",
        )
        result = media.execute()
        return result.get("id")
    except Exception as e:
        logger.warning(f"No se pudo guardar log de error en Drive: {e}")
        return None

