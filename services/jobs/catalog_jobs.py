# NG-HEADER: Nombre de archivo: catalog_jobs.py
# NG-HEADER: Ubicación: services/jobs/catalog_jobs.py
# NG-HEADER: Descripción: Worker persistente para altas masivas de productos canónicos.
# NG-HEADER: Lineamientos: Ver AGENTS.md
"""Procesamiento asíncrono y parcial de lotes de productos canónicos."""
from __future__ import annotations

import asyncio
import json
import logging
import sys
import time
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

try:
    import services.jobs  # noqa: F401
except ImportError:
    pass

try:
    import dramatiq  # type: ignore
except Exception:  # pragma: no cover
    def _noop_decorator(*_args, **_kwargs):
        def _wrap(func):
            return func
        return _wrap

    class _StubModule:
        actor = staticmethod(_noop_decorator)

    dramatiq = _StubModule()  # type: ignore

from db.models import (
    AuditLog,
    CanonicalBatchJob,
    CanonicalBatchJobItem,
    CanonicalProduct,
    Category,
    ProductEquivalence,
    ProductTag,
    SupplierProduct,
)
from db.session import SessionLocal
from db.sku_generator import CanonicalSkuGenerationError, generate_canonical_sku
from db.sku_utils import CANONICAL_SKU_REGEX

logger = logging.getLogger(__name__)


def _log_catalog_event(event: str, *, level: str = "INFO", **fields) -> None:
    """Emite un evento NDJSON mínimo a stdout para que Docker lo capture."""
    payload = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "service": "catalog_worker",
        "event": event,
        "level": level,
        **fields,
    }
    print(json.dumps(payload, ensure_ascii=False, default=str), flush=True)


class BatchItemError(Exception):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code
        self.message = message


async def _taxonomy(db, category_id: int | None, subcategory_id: int | None) -> tuple[Category, Category]:
    if not category_id:
        raise BatchItemError("invalid_category", "La categoría es obligatoria")
    if not subcategory_id:
        raise BatchItemError("invalid_subcategory", "La subcategoría es obligatoria")
    category = await db.get(Category, category_id)
    subcategory = await db.get(Category, subcategory_id)
    if not category or category.kind != "category":
        raise BatchItemError("invalid_category", "La categoría debe existir y ser de tipo category")
    if not subcategory or subcategory.kind != "subcategory":
        raise BatchItemError("invalid_subcategory", "La subcategoría debe existir y ser de tipo subcategory")
    return category, subcategory


async def _register_legacy_job(job_id: str, items: list[dict]) -> None:
    """Compatibilidad para invocaciones internas antiguas del helper."""
    async with SessionLocal() as db:
        if await db.get(CanonicalBatchJob, job_id):
            return
        db.add(CanonicalBatchJob(
            id=job_id,
            client_request_id=f"legacy-{job_id}",
            total_items=len(items),
        ))
        for position, item in enumerate(items):
            db.add(CanonicalBatchJobItem(
                job_id=job_id,
                position=position,
                source_product_id=item.get("source_product_id"),
                name=(item.get("name") or "").strip(),
                brand=(item.get("brand") or "").strip() or None,
                category_id=item.get("category_id"),
                subcategory_id=item.get("subcategory_id"),
                tag_names=item.get("tag_names") or [],
                requested_sku=(item.get("sku_custom") or "").strip().upper() or None,
            ))
        await db.commit()


async def _claim_job(job_id: str) -> list[int]:
    async with SessionLocal() as db:
        job = await db.scalar(
            select(CanonicalBatchJob).where(CanonicalBatchJob.id == job_id).with_for_update()
        )
        if not job or job.status != "QUEUED":
            return []
        job.status = "RUNNING"
        job.started_at = datetime.utcnow()
        item_ids = list((await db.execute(
            select(CanonicalBatchJobItem.id)
            .where(CanonicalBatchJobItem.job_id == job_id)
            .order_by(CanonicalBatchJobItem.position)
        )).scalars())
        await db.commit()
        _log_catalog_event("job_claimed", job_id=job_id, item_count=len(item_ids))
        return item_ids


async def _mark_failed(job_id: str, item_id: int, code: str, message: str) -> None:
    async with SessionLocal() as db:
        item = await db.get(CanonicalBatchJobItem, item_id)
        job = await db.get(CanonicalBatchJob, job_id)
        if not item or not job or item.status in {"SUCCEEDED", "FAILED"}:
            return
        item.status = "FAILED"
        item.error_code = code
        item.error_message = message[:500]
        job.processed_items += 1
        job.error_count += 1
        await db.commit()
        _log_catalog_event(
            "item_failed",
            level="ERROR",
            job_id=job_id,
            item_id=item_id,
            error_code=code,
            error_message=message[:500],
        )


async def _process_item(job_id: str, item_id: int) -> None:
    async with SessionLocal() as db:
        item = await db.get(CanonicalBatchJobItem, item_id)
        job = await db.get(CanonicalBatchJob, job_id)
        if not item or not job or item.status != "PENDING":
            return
        item.status = "RUNNING"
        await db.commit()
        _log_catalog_event("item_started", job_id=job_id, item_id=item_id)
        try:
            name = item.name.strip()
            if not name:
                raise BatchItemError("invalid_name", "El nombre es obligatorio")
            category, subcategory = await _taxonomy(db, item.category_id, item.subcategory_id)
            if not item.source_product_id:
                raise BatchItemError("source_product_not_found", "Falta el producto de proveedor origen")
            supplier_product = await db.get(SupplierProduct, item.source_product_id)
            if not supplier_product:
                raise BatchItemError("source_product_not_found", "El producto de proveedor ya no existe")
            equivalence = await db.scalar(select(ProductEquivalence.id).where(
                ProductEquivalence.supplier_product_id == supplier_product.id
            ))
            if equivalence:
                raise BatchItemError("already_canonicalized", "El producto de proveedor ya tiene un canónico")

            sku = (item.requested_sku or "").strip().upper() or None
            if sku and not CANONICAL_SKU_REGEX.fullmatch(sku):
                raise BatchItemError("invalid_sku", "El SKU debe cumplir XXX_0000_YYY")
            if not sku:
                try:
                    sku = await generate_canonical_sku(db, category.name, subcategory.name)
                except CanonicalSkuGenerationError as exc:
                    raise BatchItemError("sku_sequence_exhausted", str(exc)) from exc
            if await db.scalar(select(CanonicalProduct.id).where(CanonicalProduct.sku_custom == sku)):
                raise BatchItemError("duplicate_sku", f"El SKU {sku} ya existe")

            canonical = CanonicalProduct(
                name=name,
                brand=(item.brand or "").strip() or None,
                sku_custom=sku,
                category_id=category.id,
                subcategory_id=subcategory.id,
                specs_json={"batch_job_id": job_id, "source_product_id": supplier_product.id},
            )
            db.add(canonical)
            await db.flush()
            canonical.ng_sku = f"NG-{canonical.id:06d}"
            db.add(ProductEquivalence(
                supplier_id=supplier_product.supplier_id,
                supplier_product_id=supplier_product.id,
                canonical_product_id=canonical.id,
                confidence=1.0,
                source="batch_canonical",
            ))
            if item.tag_names and supplier_product.internal_product_id:
                from services.routers.tags import get_or_create_tags
                for tag in await get_or_create_tags(db, item.tag_names):
                    relation = await db.get(ProductTag, (supplier_product.internal_product_id, tag.id))
                    if not relation:
                        db.add(ProductTag(product_id=supplier_product.internal_product_id, tag_id=tag.id))
            await db.flush()

            item.status = "SUCCEEDED"
            item.canonical_product_id = canonical.id
            item.sku_custom = sku
            item.error_code = None
            item.error_message = None
            job.processed_items += 1
            job.success_count += 1
            await db.commit()
            _log_catalog_event(
                "item_succeeded",
                job_id=job_id,
                item_id=item_id,
                canonical_product_id=canonical.id,
                sku_custom=sku,
            )
        except BatchItemError as exc:
            await db.rollback()
            await _mark_failed(job_id, item_id, exc.code, exc.message)
        except IntegrityError:
            await db.rollback()
            await _mark_failed(job_id, item_id, "duplicate_sku", "Conflicto de unicidad al crear el canónico")
        except Exception as exc:  # pragma: no cover - barrera del worker
            await db.rollback()
            logger.exception("Error procesando item %s del lote %s", item_id, job_id)
            await _mark_failed(job_id, item_id, "internal_error", str(exc))


async def _finish_job(job_id: str) -> None:
    async with SessionLocal() as db:
        job = await db.get(CanonicalBatchJob, job_id)
        if not job:
            return
        if job.success_count == job.total_items:
            job.status = "COMPLETED"
        elif job.success_count:
            job.status = "PARTIAL"
        else:
            job.status = "FAILED"
        job.completed_at = datetime.utcnow()
        db.add(AuditLog(
            action="batch_create",
            table="canonical_products",
            entity_id=None,
            meta={
                "job_id": job.id,
                "total": job.total_items,
                "success": job.success_count,
                "errors": job.error_count,
            },
            user_id=job.created_by_user_id,
            ip=None,
        ))
        await db.commit()
        _log_catalog_event(
            "job_finished",
            job_id=job.id,
            status=job.status,
            total_items=job.total_items,
            processed_items=job.processed_items,
            success_count=job.success_count,
            error_count=job.error_count,
        )
        logger.info(
            "Lote canónico %s finalizado: %s exitosos, %s errores",
            job.id,
            job.success_count,
            job.error_count,
        )


@dramatiq.actor(queue_name="catalog", max_retries=1, time_limit=300000)
def process_canonical_batch(job_id: str) -> None:
    started = time.perf_counter()
    _log_catalog_event("actor_received", job_id=job_id)
    try:
        asyncio.run(_process_canonical_batch_async(job_id))
    except Exception as exc:
        _log_catalog_event(
            "actor_failed",
            level="ERROR",
            job_id=job_id,
            duration_ms=round((time.perf_counter() - started) * 1000, 2),
            error_type=type(exc).__name__,
            error_message=str(exc)[:500],
        )
        raise
    _log_catalog_event(
        "actor_completed",
        job_id=job_id,
        duration_ms=round((time.perf_counter() - started) * 1000, 2),
    )


async def _process_canonical_batch_async(job_id: str, items: list[dict] | None = None) -> None:
    if items is not None:
        await _register_legacy_job(job_id, items)
    item_ids = await _claim_job(job_id)
    if not item_ids:
        return
    for item_id in item_ids:
        await _process_item(job_id, item_id)
    await _finish_job(job_id)
