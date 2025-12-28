# NG-HEADER: Nombre de archivo: catalog_jobs.py
# NG-HEADER: Ubicación: services/jobs/catalog_jobs.py
# NG-HEADER: Descripción: Jobs de Dramatiq para procesamiento batch de catálogos.
# NG-HEADER: Lineamientos: Ver AGENTS.md
"""Jobs para procesamiento asíncrono de catálogos (productos canónicos, etc.)."""
from __future__ import annotations

import logging
import sys
import asyncio
from typing import TypedDict

# FIX: Windows ProactorEventLoop no soporta psycopg async
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

# IMPORTANTE: Importar el paquete services.jobs primero para inicializar el broker Redis
try:
    import services.jobs  # noqa: F401 - Inicializa el broker
except ImportError:
    pass

try:  # Hacer opcional dramatiq para permitir levantar la API sin la dependencia
    import dramatiq  # type: ignore
    _dramatiq_available = True
except Exception:  # pragma: no cover - entorno sin dramatiq
    _dramatiq_available = False
    def _noop_decorator(*dargs, **dkwargs):
        def _wrap(func):
            return func
        return _wrap
    class _StubModule:  # type: ignore
        actor = staticmethod(_noop_decorator)
    dramatiq = _StubModule()  # type: ignore

from db.session import SessionLocal
from db.models import CanonicalProduct, Category, AuditLog, SupplierProduct, ProductEquivalence

logger = logging.getLogger(__name__)


# ============================================================================
# TIPOS
# ============================================================================

class CanonicalProductBatchItem(TypedDict):
    """Item para creación batch de producto canónico."""
    name: str
    brand: str | None
    category_id: int | None
    subcategory_id: int | None
    sku_custom: str | None
    source_product_id: int | None  # ID del producto de mercado origen (para vincular)


class BatchResultItem(TypedDict):
    """Resultado de procesamiento de un item del batch."""
    index: int
    source_product_id: int | None
    success: bool
    canonical_id: int | None
    ng_sku: str | None
    sku_custom: str | None
    error: str | None


# ============================================================================
# HELPERS
# ============================================================================

def _slugify3(name: str | None, fallback: str) -> str:
    """Toma hasta 3 letras del nombre, removiendo acentos/diacríticos."""
    if not name:
        return fallback
    import unicodedata
    x = unicodedata.normalize('NFD', name)
    x = ''.join(ch for ch in x if unicodedata.category(ch) != 'Mn')
    x = ''.join(ch for ch in x if ('A' <= ch <= 'Z') or ('a' <= ch <= 'z'))
    x = (x[:3].upper() or fallback)
    return x.ljust(3, 'X')


def build_canonical_sku(cat_name: str | None, sub_name: str | None, next_seq: int) -> str:
    """Construye un SKU canónico en formato XXX_####_YYY."""
    XXX = _slugify3(cat_name, 'SIN')
    YYY = _slugify3(sub_name, 'GEN')
    num = str(int(next_seq)).rjust(4, '0')
    return f"{XXX}_{num}_{YYY}"


# ============================================================================
# ACTOR DE DRAMATIQ
# ============================================================================

@dramatiq.actor(queue_name="catalog", max_retries=1, time_limit=300000)  # 5 min timeout
def process_canonical_batch(job_id: str, items: list[dict]) -> None:
    """
    Procesa un batch de productos canónicos para creación.
    
    Estrategia de errores: Intentar procesar todos, reportar errores parciales.
    No se hace rollback general si falla uno.
    
    Args:
        job_id: Identificador único del job
        items: Lista de diccionarios con datos de cada producto
    """
    import asyncio
    asyncio.run(_process_canonical_batch_async(job_id, items))


async def _process_canonical_batch_async(job_id: str, items: list[dict]) -> None:
    """Implementación async del procesamiento batch."""
    import re as _re
    from sqlalchemy import select
    
    results: list[BatchResultItem] = []
    generated_skus: set[str] = set()  # SKUs generados en este batch para evitar duplicados
    # Diccionario para trackear el máximo secuencial por prefijo de categoría en este batch
    # Esto asegura que cada categoría tenga números únicos incluso con diferentes subcategorías
    category_max_seq: dict[str, int] = {}
    
    async with SessionLocal() as db:
        for idx, item_dict in enumerate(items):
            # LOG de diagnóstico para ver qué datos llegan
            logger.info(f"[Batch {job_id}] Item {idx}: source_product_id={item_dict.get('source_product_id')}, name={item_dict.get('name', 'N/A')[:30]}, category_id={item_dict.get('category_id')}, subcategory_id={item_dict.get('subcategory_id')}")
            
            item = CanonicalProductBatchItem(**item_dict)
            result: BatchResultItem = {
                "index": idx,
                "source_product_id": item.get("source_product_id"),
                "success": False,
                "canonical_id": None,
                "ng_sku": None,
                "sku_custom": None,
                "error": None,
            }
            
            try:
                # Validar nombre
                name = (item.get("name") or "").strip()
                if not name:
                    result["error"] = "Nombre requerido"
                    results.append(result)
                    continue
                
                # Obtener o generar SKU
                sku_custom = (item.get("sku_custom") or "").strip().upper() or None
                
                if not sku_custom:
                    # Autogenerar SKU
                    category_id = item.get("category_id")
                    subcategory_id = item.get("subcategory_id")
                    
                    # Obtener nombres de categoría
                    cat_name = None
                    sub_name = None
                    if category_id:
                        cat = await db.get(Category, category_id)
                        cat_name = cat.name if cat else None
                    if subcategory_id:
                        sub = await db.get(Category, subcategory_id)
                        sub_name = sub.name if sub else None
                    
                    # Buscar secuencia más alta para esta categoría
                    if category_id is not None:
                        sku_stmt = select(CanonicalProduct.sku_custom).where(
                            CanonicalProduct.category_id == category_id,
                            CanonicalProduct.sku_custom.isnot(None)
                        )
                    else:
                        sku_stmt = select(CanonicalProduct.sku_custom).where(
                            CanonicalProduct.category_id.is_(None),
                            CanonicalProduct.sku_custom.isnot(None)
                        )
                    sku_result = await db.execute(sku_stmt)
                    existing_skus = {row[0].upper() for row in sku_result.all() if row[0]}
                    
                    # Combinar con SKUs ya generados en este batch
                    all_used_skus = existing_skus | generated_skus
                    
                    # Obtener prefijo de categoría para filtrar
                    cat_prefix = _slugify3(cat_name, 'SIN')
                    
                    # Si no tenemos max_seq para esta categoría en el batch, calcularlo de la BD + generated_skus
                    if cat_prefix not in category_max_seq:
                        sku_pattern = _re.compile(rf'^{cat_prefix}_(\d{{4}})_[A-Z]{{3}}$')
                        max_seq = 0
                        for sku in all_used_skus:
                            match = sku_pattern.match(sku)
                            if match:
                                seq_num = int(match.group(1))
                                if seq_num > max_seq:
                                    max_seq = seq_num
                        category_max_seq[cat_prefix] = max_seq
                    
                    # Incrementar y guardar el siguiente número para esta categoría
                    category_max_seq[cat_prefix] += 1
                    next_seq = category_max_seq[cat_prefix]
                    
                    # Generar SKU con el número garantizado único para esta categoría
                    sku_custom = build_canonical_sku(cat_name, sub_name, next_seq)
                    
                    # DEBUG: Log para diagnosticar duplicación de SKU
                    logger.info(f"[Batch {job_id}] SKU DEBUG: cat_prefix={cat_prefix}, next_seq={next_seq}, category_max_seq={category_max_seq}")
                    
                    # Registrar SKU como usado
                    generated_skus.add(sku_custom.upper())
                
                # Verificar unicidad final en DB
                exists = await db.scalar(
                    select(CanonicalProduct).where(CanonicalProduct.sku_custom == sku_custom)
                )
                if exists:
                    result["error"] = f"SKU '{sku_custom}' ya existe en la base de datos"
                    results.append(result)
                    continue
                
                # Crear producto
                cp = CanonicalProduct(
                    name=name,
                    brand=item.get("brand"),
                    sku_custom=sku_custom,
                    category_id=item.get("category_id"),
                    subcategory_id=item.get("subcategory_id"),
                    specs_json={
                        "batch_job_id": job_id,
                        "source_product_id": item.get("source_product_id"),
                    },
                )
                db.add(cp)
                await db.flush()
                
                # Generar ng_sku
                cp.ng_sku = f"NG-{cp.id:06d}"
                
                # Crear equivalencia si hay producto de proveedor origen
                source_product_id = item.get("source_product_id")
                if source_product_id:
                    # Obtener el supplier_id del SupplierProduct
                    sp = await db.get(SupplierProduct, source_product_id)
                    if sp and sp.supplier_id:
                        # Verificar si ya existe una equivalencia para este supplier_product
                        from sqlalchemy import select as sql_select
                        existing_eq = await db.scalar(
                            sql_select(ProductEquivalence).where(
                                ProductEquivalence.supplier_product_id == source_product_id
                            )
                        )
                        if not existing_eq:
                            equiv = ProductEquivalence(
                                supplier_id=sp.supplier_id,
                                supplier_product_id=source_product_id,
                                canonical_product_id=cp.id,
                                confidence=1.0,  # Alta confianza porque es creación manual
                                source="batch_cannon",
                            )
                            db.add(equiv)
                            logger.info(f"[Batch {job_id}] Creada equivalencia: SP#{source_product_id} -> Canon#{cp.id}")
                
                await db.commit()
                await db.refresh(cp)
                
                # Resultado exitoso
                result["success"] = True
                result["canonical_id"] = cp.id
                result["ng_sku"] = cp.ng_sku
                result["sku_custom"] = cp.sku_custom
                
                logger.info(f"[Batch {job_id}] Creado canónico {cp.id}: {cp.sku_custom}")
                
            except Exception as e:
                result["error"] = str(e)
                logger.error(f"[Batch {job_id}] Error en item {idx}: {e}")
                # Rollback parcial
                await db.rollback()
            
            results.append(result)
        
        # Guardar registro de auditoría del batch
        try:
            success_count = sum(1 for r in results if r["success"])
            error_count = sum(1 for r in results if not r["success"])
            
            audit = AuditLog(
                action="batch_create",
                table="canonical_products",
                entity_id=None,
                meta={
                    "job_id": job_id,
                    "total": len(items),
                    "success": success_count,
                    "errors": error_count,
                    "results": results,
                },
                user_id=None,
                ip=None,
            )
            db.add(audit)
            await db.commit()
            logger.info(f"[Batch {job_id}] Completado: {success_count}/{len(items)} exitosos")
        except Exception as e:
            logger.warning(f"[Batch {job_id}] Error guardando auditoría: {e}")
