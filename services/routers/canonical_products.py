# NG-HEADER: Nombre de archivo: canonical_products.py
# NG-HEADER: Ubicación: services/routers/canonical_products.py
# NG-HEADER: Descripción: API de productos canónicos y equivalencias.
# NG-HEADER: Lineamientos: Ver AGENTS.md
"""Endpoints para productos canónicos y equivalencias."""
from __future__ import annotations

import os

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession
from decimal import Decimal

from db.models import (
    CanonicalProduct,
    CanonicalBatchJob,
    CanonicalBatchJobItem,
    Category,
    AuditLog,
    ProductEquivalence,
    Supplier,
    SupplierProduct,
)
from db.sku_generator import generate_canonical_sku
from db.sku_utils import CANONICAL_SKU_REGEX, build_canonical_sku as compose_canonical_sku, normalize_code
from db.session import get_session
from db.text_utils import stylize_product_name
from services.auth import require_csrf, require_roles, current_session, SessionData

canonical_router = APIRouter(prefix="/canonical-products", tags=["catalog"])
equivalences_router = APIRouter(prefix="/equivalences", tags=["catalog"])


class CanonicalCreate(BaseModel):
    name: str
    brand: str | None = None
    specs_json: dict | None = None
    sku_custom: str | None = None
    category_id: int | None = None
    subcategory_id: int | None = None


class CanonicalUpdate(BaseModel):
    name: str | None = None
    brand: str | None = None
    specs_json: dict | None = None
    sku_custom: str | None = None
    category_id: int | None = None
    subcategory_id: int | None = None


class CanonicalBatchItem(BaseModel):
    """Item para creación batch de producto canónico."""
    name: str
    brand: str | None = None
    category_id: int | None = None
    subcategory_id: int | None = None
    sku_custom: str | None = None
    source_product_id: int | None = None  # ID del producto de mercado origen
    tag_names: list[str] = Field(default_factory=list)


class CanonicalBatchRequest(BaseModel):
    """Request para creación batch de productos canónicos."""
    client_request_id: str | None = None
    items: list[CanonicalBatchItem]


class CanonicalSkuPreviewItem(BaseModel):
    category_id: int
    subcategory_id: int


class CanonicalSkuPreviewRequest(BaseModel):
    items: list[CanonicalSkuPreviewItem]


async def _validate_taxonomy(
    session: AsyncSession,
    category_id: int | None,
    subcategory_id: int | None,
    *,
    required: bool,
) -> tuple[Category | None, Category | None]:
    if required and not category_id:
        raise HTTPException(status_code=422, detail={"code": "invalid_category", "message": "La categoría es obligatoria"})
    if required and not subcategory_id:
        raise HTTPException(status_code=422, detail={"code": "invalid_subcategory", "message": "La subcategoría es obligatoria"})
    category = await session.get(Category, category_id) if category_id else None
    subcategory = await session.get(Category, subcategory_id) if subcategory_id else None
    if category_id and (not category or category.kind != "category"):
        raise HTTPException(status_code=422, detail={"code": "invalid_category", "message": "La categoría debe existir y ser de tipo category"})
    if subcategory_id and (not subcategory or subcategory.kind != "subcategory"):
        raise HTTPException(status_code=422, detail={"code": "invalid_subcategory", "message": "La subcategoría debe existir y ser de tipo subcategory"})
    return category, subcategory


async def _dispatch_canonical_batch_job(
    job: CanonicalBatchJob,
    session: AsyncSession,
) -> None:
    """Ejecuta o encola un lote ya persistido y registra fallos de despacho."""
    run_inline = os.getenv("RUN_INLINE_JOBS", "0") == "1"
    if run_inline:
        from services.jobs.catalog_jobs import _process_canonical_batch_async

        try:
            await _process_canonical_batch_async(job.id)
        except Exception as exc:
            job.status = "FAILED"
            job.error_message = str(exc)[:500]
            await session.commit()
            raise HTTPException(status_code=500, detail="Error procesando el lote") from exc
        return

    try:
        from services.jobs.catalog_jobs import process_canonical_batch

        process_canonical_batch.send(job.id)
    except Exception as exc:
        job.status = "FAILED"
        job.error_message = str(exc)[:500]
        await session.commit()
        raise HTTPException(status_code=503, detail="No se pudo encolar el lote") from exc


@canonical_router.get("/resolve", dependencies=[Depends(require_roles("cliente", "proveedor", "colaborador", "admin"))])
async def resolve_canonical_by_sku(
    sku: str = Query(..., description="NG-SKU (NG-######) o SKU propio canónico (XXX_####_YYY)"),
    session: AsyncSession = Depends(get_session),
):
    """Resuelve un producto canónico por ``ng_sku`` o ``sku_custom`` (match exacto, case-insensitive).

    Respuesta: { id, ng_sku, sku_custom, name }
    """
    value = (sku or "").strip().upper()
    if not value:
        raise HTTPException(status_code=400, detail="sku requerido")
    stmt = select(CanonicalProduct).where(
        (CanonicalProduct.ng_sku == value) | (CanonicalProduct.sku_custom == value)
    ).limit(1)
    row = await session.scalar(stmt)
    if not row:
        raise HTTPException(status_code=404, detail="SKU canónico no encontrado")
    return {
        "id": row.id,
        "ng_sku": row.ng_sku,
        "sku_custom": row.sku_custom,
        "name": stylize_product_name(row.name),
    }


@canonical_router.post(
    "",
    dependencies=[Depends(require_csrf), Depends(require_roles("admin"))],
)
async def create_canonical_product(
    req: CanonicalCreate,
    request: Request,
    session: AsyncSession = Depends(get_session),
    sess: SessionData = Depends(current_session),
) -> dict:
    """Crea un canónico usando el generador transaccional compartido."""
    name = req.name.strip()
    if not name:
        raise HTTPException(status_code=422, detail={"code": "invalid_name", "message": "El nombre es obligatorio"})
    category, subcategory = await _validate_taxonomy(
        session, req.category_id, req.subcategory_id, required=True
    )
    sku_custom = normalize_sku(req.sku_custom or "") or None
    if sku_custom and not CANONICAL_SKU_REGEX.fullmatch(sku_custom):
        raise HTTPException(status_code=422, detail={"code": "invalid_sku", "message": "El SKU debe cumplir XXX_0000_YYY"})
    if not sku_custom:
        sku_custom = await generate_canonical_sku(
            session,
            category.name if category else "Sin categoría",
            subcategory.name if subcategory else (category.name if category else "General"),
        )
    exists = await session.scalar(select(CanonicalProduct.id).where(CanonicalProduct.sku_custom == sku_custom))
    if exists:
        raise HTTPException(status_code=409, detail={"code": "duplicate_sku", "message": "SKU canónico duplicado"})
    cp = CanonicalProduct(
        name=name,
        brand=(req.brand or "").strip() or None,
        specs_json=req.specs_json,
        sku_custom=sku_custom,
        category_id=req.category_id,
        subcategory_id=req.subcategory_id,
    )
    session.add(cp)
    await session.flush()
    cp.ng_sku = f"NG-{cp.id:06d}"
    await session.commit()
    await session.refresh(cp)
    _cid = request.headers.get("x-correlation-id") or request.headers.get("x-request-id") if request else None
    await _audit(session, action="create", table="canonical_products", entity_id=cp.id, meta={
        "sku_custom": cp.sku_custom,
        "category_id": cp.category_id,
        "subcategory_id": cp.subcategory_id,
        "auto_sku": not (req.sku_custom or '').strip(),
        **({"cid": _cid} if _cid else {}),
    }, sess=sess, request=request)
    return {
        "id": cp.id,
        "ng_sku": cp.ng_sku,
        "name": stylize_product_name(cp.name),
        "brand": cp.brand,
        "specs_json": cp.specs_json,
        "sku_custom": cp.sku_custom,
        "category_id": cp.category_id,
        "subcategory_id": cp.subcategory_id,
    }


@canonical_router.post(
    "/batch-job",
    dependencies=[Depends(require_csrf), Depends(require_roles("colaborador", "admin"))],
    status_code=202,
)
async def create_canonical_batch_job(
    req: CanonicalBatchRequest,
    request: Request,
    session: AsyncSession = Depends(get_session),
    sess: SessionData = Depends(current_session),
) -> dict:
    """Persiste y encola un lote idempotente de productos canónicos."""
    import uuid
    
    if not req.items:
        raise HTTPException(status_code=400, detail="Debe proporcionar al menos un producto")
    
    if len(req.items) > 100:
        raise HTTPException(status_code=400, detail="Máximo 100 productos por request")
    
    client_request_id = (req.client_request_id or uuid.uuid4().hex).strip()
    if not client_request_id or len(client_request_id) > 64:
        raise HTTPException(status_code=422, detail="client_request_id inválido")
    existing = await session.scalar(
        select(CanonicalBatchJob)
        .where(CanonicalBatchJob.client_request_id == client_request_id)
        .with_for_update()
    )
    if existing:
        if sess.role != "admin" and existing.created_by_user_id and (not sess.user or sess.user.id != existing.created_by_user_id):
            raise HTTPException(status_code=403, detail="El identificador idempotente pertenece a otro usuario")
        if existing.status == "FAILED" and existing.processed_items == 0:
            existing.status = "QUEUED"
            existing.error_message = None
            await session.commit()
            await _dispatch_canonical_batch_job(existing, session)
            return {
                "status": "QUEUED",
                "job_id": existing.id,
                "message": "El lote fallido fue reenviado",
                "total_items": existing.total_items,
                "status_url": f"/canonical-products/batch-jobs/{existing.id}",
            }
        return {
            "status": existing.status,
            "job_id": existing.id,
            "message": "El lote ya había sido recibido",
            "total_items": existing.total_items,
            "status_url": f"/canonical-products/batch-jobs/{existing.id}",
        }

    job_id = f"batch-canon-{uuid.uuid4()}"
    job = CanonicalBatchJob(
        id=job_id,
        client_request_id=client_request_id,
        created_by_user_id=sess.user.id if sess.user else None,
        total_items=len(req.items),
    )
    session.add(job)
    for position, item in enumerate(req.items):
        session.add(CanonicalBatchJobItem(
            job_id=job_id,
            position=position,
            source_product_id=item.source_product_id,
            name=item.name.strip(),
            brand=(item.brand or "").strip() or None,
            category_id=item.category_id,
            subcategory_id=item.subcategory_id,
            tag_names=item.tag_names,
            requested_sku=normalize_sku(item.sku_custom or "") or None,
        ))
    await session.commit()
    
    run_inline = os.getenv("RUN_INLINE_JOBS", "0") == "1"
    await _dispatch_canonical_batch_job(job, session)
    
    return {
        "status": "QUEUED",
        "job_id": job_id,
        "message": f"{'Procesando' if run_inline else 'Encolados'} {len(req.items)} productos para creación",
        "total_items": len(req.items),
        "status_url": f"/canonical-products/batch-jobs/{job_id}",
    }


@canonical_router.post(
    "/sku-preview",
    dependencies=[Depends(require_csrf), Depends(require_roles("colaborador", "admin"))],
)
async def preview_canonical_skus(
    req: CanonicalSkuPreviewRequest,
    session: AsyncSession = Depends(get_session),
) -> dict:
    """Devuelve vistas previas no reservantes y únicas dentro de la solicitud."""
    if not req.items or len(req.items) > 100:
        raise HTTPException(status_code=400, detail="Debe proporcionar entre 1 y 100 productos")
    existing = (await session.execute(select(CanonicalProduct.sku_custom))).scalars().all()
    maxima: dict[str, int] = {}
    for value in existing:
        if value and CANONICAL_SKU_REGEX.fullmatch(value):
            prefix, number, _suffix = value.split("_")
            maxima[prefix] = max(maxima.get(prefix, 0), int(number))
    previews = []
    for position, item in enumerate(req.items):
        category, subcategory = await _validate_taxonomy(
            session, item.category_id, item.subcategory_id, required=True
        )
        prefix = normalize_code(category.name if category else None)
        suffix = normalize_code(subcategory.name if subcategory else None)
        maxima[prefix] = maxima.get(prefix, 0) + 1
        if maxima[prefix] > 9999:
            raise HTTPException(status_code=409, detail={"code": "sku_sequence_exhausted", "message": f"Secuencia agotada para {prefix}"})
        previews.append({
            "position": position,
            "sku": compose_canonical_sku(prefix, maxima[prefix], suffix),
            "definitive": False,
        })
    return {"items": previews}


def _serialize_batch_job(job: CanonicalBatchJob) -> dict:
    return {
        "job_id": job.id,
        "status": job.status,
        "total_items": job.total_items,
        "processed_items": job.processed_items,
        "success_count": job.success_count,
        "error_count": job.error_count,
        "error_message": job.error_message,
        "created_at": job.created_at.isoformat() if job.created_at else None,
        "started_at": job.started_at.isoformat() if job.started_at else None,
        "completed_at": job.completed_at.isoformat() if job.completed_at else None,
        "items": [{
            "position": item.position,
            "source_product_id": item.source_product_id,
            "status": item.status,
            "canonical_product_id": item.canonical_product_id,
            "sku_custom": item.sku_custom,
            "error": ({"code": item.error_code, "message": item.error_message} if item.error_code else None),
        } for item in job.items],
    }


@canonical_router.get(
    "/batch-jobs/{job_id}",
    dependencies=[Depends(require_roles("colaborador", "admin"))],
)
async def get_canonical_batch_job(
    job_id: str,
    session: AsyncSession = Depends(get_session),
    sess: SessionData = Depends(current_session),
) -> dict:
    job = await session.scalar(
        select(CanonicalBatchJob)
        .options(selectinload(CanonicalBatchJob.items))
        .where(CanonicalBatchJob.id == job_id)
    )
    if not job:
        raise HTTPException(status_code=404, detail="Lote no encontrado")
    if sess.role != "admin" and job.created_by_user_id and (not sess.user or sess.user.id != job.created_by_user_id):
        raise HTTPException(status_code=403, detail="No autorizado para consultar este lote")
    return _serialize_batch_job(job)


@canonical_router.get("")
async def list_canonical_products(
    q: str | None = Query(default=None),
    page: int = 1,
    page_size: int = 20,
    session: AsyncSession = Depends(get_session),
) -> dict:
    """Lista productos canónicos con búsqueda y paginación."""
    stmt = select(CanonicalProduct)
    if q:
        stmt = stmt.where(CanonicalProduct.name.ilike(f"%{q}%"))
    total = await session.scalar(select(func.count()).select_from(stmt.subquery()))
    result = await session.execute(
        stmt.order_by(CanonicalProduct.id)
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    items = result.scalars().all()
    return {
        "page": page,
        "page_size": page_size,
        "total": total or 0,
        "items": [
            {
                "id": cp.id,
                "ng_sku": cp.ng_sku,
                "name": stylize_product_name(cp.name),
                "brand": cp.brand,
                "specs_json": cp.specs_json,
            }
            for cp in items
        ],
    }


@canonical_router.get("/{canonical_id}")
async def get_canonical_product(
    canonical_id: int, session: AsyncSession = Depends(get_session)
) -> dict:
    """Obtiene un producto canónico por ``id``."""
    cp = await session.get(CanonicalProduct, canonical_id)
    if not cp:
        raise HTTPException(status_code=404, detail="Canonical product not found")
    return {
        "id": cp.id,
        "ng_sku": cp.ng_sku,
        "name": stylize_product_name(cp.name),
        "brand": cp.brand,
        "specs_json": cp.specs_json,
    }


@canonical_router.patch(
    "/{canonical_id}",
    dependencies=[Depends(require_csrf), Depends(require_roles("admin"))],
)
async def update_canonical_product(
    canonical_id: int,
    req: CanonicalUpdate,
    request: Request,
    session: AsyncSession = Depends(get_session),
    sess: SessionData = Depends(current_session),
) -> dict:
    """Actualiza un producto canónico."""
    cp = await session.get(CanonicalProduct, canonical_id)
    if not cp:
        raise HTTPException(status_code=404, detail="Canonical product not found")
    data = req.model_dump(exclude_unset=True)
    if "sku_custom" in data and data["sku_custom"]:
        data["sku_custom"] = normalize_sku(data["sku_custom"])
        exists = await session.scalar(select(CanonicalProduct).where(CanonicalProduct.sku_custom == data["sku_custom"], CanonicalProduct.id != cp.id))
        if exists:
            raise HTTPException(status_code=409, detail="SKU canónico duplicado")
    for k, v in data.items():
        setattr(cp, k, v)
    await session.commit()
    await session.refresh(cp)
    _cid = request.headers.get("x-correlation-id") or request.headers.get("x-request-id") if request else None
    await _audit(session, action="update", table="canonical_products", entity_id=cp.id, meta={"fields": list(data.keys()), **({"cid": _cid} if _cid else {})}, sess=sess, request=request)
    return {
        "id": cp.id,
        "ng_sku": cp.ng_sku,
        "name": stylize_product_name(cp.name),
        "brand": cp.brand,
        "specs_json": cp.specs_json,
        "sku_custom": cp.sku_custom,
        "category_id": cp.category_id,
        "subcategory_id": cp.subcategory_id,
    }


@canonical_router.delete(
    "/{canonical_id}",
    dependencies=[Depends(require_csrf), Depends(require_roles("admin"))],
)
async def delete_canonical_product(
    canonical_id: int,
    request: Request,
    session: AsyncSession = Depends(get_session),
    sess: SessionData = Depends(current_session),
) -> dict:
    """Elimina un producto canónico.
    
    Se eliminan automáticamente (CASCADE):
    - MarketSource relacionadas
    - MarketAlert relacionadas
    - MarketPriceHistory relacionadas
    
    Se eliminan manualmente:
    - ProductEquivalence relacionadas (no tienen CASCADE)
    """
    cp = await session.get(CanonicalProduct, canonical_id)
    if not cp:
        raise HTTPException(status_code=404, detail="Canonical product not found")
    
    # Guardar datos para auditoría antes de eliminar
    cp_name = cp.name
    cp_sku = cp.sku_custom or cp.ng_sku
    
    # Eliminar ProductEquivalence relacionadas (no tienen CASCADE)
    equivalences = await session.execute(
        select(ProductEquivalence).where(ProductEquivalence.canonical_product_id == canonical_id)
    )
    eq_list = equivalences.scalars().all()
    for eq in eq_list:
        await session.delete(eq)
    
    # Eliminar el CanonicalProduct (MarketSource, MarketAlert, MarketPriceHistory se eliminan por CASCADE)
    await session.delete(cp)
    await session.commit()
    
    # Auditoría
    _cid = request.headers.get("x-correlation-id") or request.headers.get("x-request-id") if request else None
    await _audit(
        session,
        action="delete",
        table="canonical_products",
        entity_id=canonical_id,
        meta={
            "name": cp_name,
            "sku": cp_sku,
            "equivalences_deleted": len(eq_list),
            **({"cid": _cid} if _cid else {})
        },
        sess=sess,
        request=request
    )
    
    return {"status": "deleted", "id": canonical_id}


class EquivalenceCreate(BaseModel):
    supplier_id: int
    supplier_product_id: int
    canonical_product_id: int
    source: str = "manual"
    confidence: float | None = None


@equivalences_router.get("")
async def list_equivalences(
    supplier_id: int | None = Query(default=None),
    canonical_product_id: int | None = Query(default=None),
    page: int = 1,
    page_size: int = 20,
    session: AsyncSession = Depends(get_session),
) -> dict:
    """Lista equivalencias con filtros opcionales."""
    stmt = select(ProductEquivalence)
    if supplier_id is not None:
        stmt = stmt.where(ProductEquivalence.supplier_id == supplier_id)
    if canonical_product_id is not None:
        stmt = stmt.where(
            ProductEquivalence.canonical_product_id == canonical_product_id
        )
    total = await session.scalar(select(func.count()).select_from(stmt.subquery()))
    result = await session.execute(
        stmt.order_by(ProductEquivalence.id)
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    items = result.scalars().all()
    return {
        "page": page,
        "page_size": page_size,
        "total": total or 0,
        "items": [
            {
                "id": eq.id,
                "supplier_id": eq.supplier_id,
                "supplier_product_id": eq.supplier_product_id,
                "canonical_product_id": eq.canonical_product_id,
                "source": eq.source,
                "confidence": eq.confidence,
            }
            for eq in items
        ],
    }


@equivalences_router.post(
    "",
    dependencies=[Depends(require_csrf), Depends(require_roles("colaborador", "admin"))],
)
async def upsert_equivalence(
    req: EquivalenceCreate, session: AsyncSession = Depends(get_session)
) -> dict:
    """Crea o actualiza una equivalencia entre oferta y canónico."""
    stmt = select(ProductEquivalence).where(
        ProductEquivalence.supplier_id == req.supplier_id,
        ProductEquivalence.supplier_product_id == req.supplier_product_id,
    )
    existing = await session.scalar(stmt)
    if existing:
        existing.canonical_product_id = req.canonical_product_id
        existing.source = req.source
        existing.confidence = req.confidence
        eq = existing
    else:
        eq = ProductEquivalence(
            supplier_id=req.supplier_id,
            supplier_product_id=req.supplier_product_id,
            canonical_product_id=req.canonical_product_id,
            source=req.source,
            confidence=req.confidence,
        )
        session.add(eq)
    await session.commit()
    await session.refresh(eq)
    return {
        "id": eq.id,
        "supplier_id": eq.supplier_id,
        "supplier_product_id": eq.supplier_product_id,
        "canonical_product_id": eq.canonical_product_id,
        "source": eq.source,
        "confidence": eq.confidence,
    }


@equivalences_router.delete(
    "/{equivalence_id}",
    dependencies=[Depends(require_csrf), Depends(require_roles("colaborador", "admin"))],
)
async def delete_equivalence(
    equivalence_id: int, session: AsyncSession = Depends(get_session)
) -> dict:
    """Elimina una equivalencia."""
    eq = await session.get(ProductEquivalence, equivalence_id)
    if not eq:
        raise HTTPException(status_code=404, detail="Equivalence not found")
    await session.delete(eq)
    await session.commit()
    return {"status": "deleted"}


@canonical_router.get("/{canonical_id}/offers")
async def list_offers(
    canonical_id: int, session: AsyncSession = Depends(get_session)
) -> list[dict]:
    """Devuelve todas las ofertas vinculadas a un canónico."""
    stmt = (
        select(SupplierProduct, Supplier)
        .join(
            ProductEquivalence,
            ProductEquivalence.supplier_product_id == SupplierProduct.id,
        )
        .join(Supplier, Supplier.id == SupplierProduct.supplier_id)
        .where(ProductEquivalence.canonical_product_id == canonical_id)
        .order_by(SupplierProduct.current_sale_price)
    )
    result = await session.execute(stmt)
    rows = result.all()
    best_price: Decimal | None = None
    for sp, _ in rows:
        if sp.current_sale_price is not None:
            best_price = Decimal(sp.current_sale_price)
            break
    offers = []
    for sp, sup in rows:
        sale = (
            Decimal(sp.current_sale_price).quantize(Decimal("0.01"))
            if sp.current_sale_price is not None
            else None
        )
        purchase = (
            Decimal(sp.current_purchase_price).quantize(Decimal("0.01"))
            if sp.current_purchase_price is not None
            else None
        )
        offers.append(
            {
                "supplier": {"id": sup.id, "name": sup.name, "slug": sup.slug},
                "precio_venta": float(sale) if sale is not None else None,
                "precio_compra": float(purchase) if purchase is not None else None,
                "compra_minima": float(sp.min_purchase_qty)
                if sp.min_purchase_qty is not None
                else None,
                "updated_at": sp.last_seen_at.isoformat() if sp.last_seen_at else None,
                "supplier_product_id": sp.id,
                "mejor_precio":
                    bool(sale is not None and best_price is not None and sale == best_price),
            }
        )
    return offers

# --- Helpers internos ---

def normalize_sku(value: str) -> str:
    return (value or '').strip().upper()

async def _get_category_name(session: AsyncSession, category_id: int | None) -> str | None:
    if not category_id:
        return None
    c = await session.get(Category, category_id)
    return c.name if c else None

def _slugify3(name: str | None, fallback: str) -> str:
    """Toma hasta 3 letras del nombre, removiendo acentos/diacríticos.

    Evita usar clases Unicode (\\p{M}) no soportadas por `re` estándar en Python.
    """
    if not name:
        return fallback
    import unicodedata
    # Normalizar a NFD y eliminar marcas combinadas (Mn)
    x = unicodedata.normalize('NFD', name)
    x = ''.join(ch for ch in x if unicodedata.category(ch) != 'Mn')
    # Mantener sólo letras A-Z
    x = ''.join(ch for ch in x if ('A' <= ch <= 'Z') or ('a' <= ch <= 'z'))
    x = (x[:3].upper() or fallback)
    return x.ljust(3, 'X')

def build_canonical_sku(cat_name: str | None, sub_name: str | None, next_seq: int) -> str:
    XXX = _slugify3(cat_name, 'SIN')
    YYY = _slugify3(sub_name, 'GEN')
    num = str(int(next_seq)).rjust(4, '0')
    return f"{XXX}_{num}_{YYY}"

async def _audit(session: AsyncSession, action: str, table: str, entity_id: int | None, meta: dict | None, sess: SessionData | None, request: Request | None):
    try:
        al = AuditLog(action=action, table=table, entity_id=entity_id, meta=meta or {}, user_id=(sess.user.id if sess and sess.user else None), ip=(request.client.host if request and request.client else None))
        session.add(al)
        await session.commit()
    except Exception:
        pass
