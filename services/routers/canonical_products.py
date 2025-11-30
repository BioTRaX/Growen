# NG-HEADER: Nombre de archivo: canonical_products.py
# NG-HEADER: Ubicación: services/routers/canonical_products.py
# NG-HEADER: Descripción: API de productos canónicos y equivalencias.
# NG-HEADER: Lineamientos: Ver AGENTS.md
"""Endpoints para productos canónicos y equivalencias."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from decimal import Decimal

from db.models import (
    CanonicalProduct,
    ProductEquivalence,
    Supplier,
    SupplierProduct,
)
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
    """Crea un producto canónico y genera un ``ng_sku`` único.

    Si no viene ``sku_custom``, genera uno en base a categoría/subcategoría y próxima secuencia por categoría.
    Valida unicidad (mayúsculas).
    """
    sku_custom = (req.sku_custom or '').strip() or None
    if sku_custom:
        sku_custom = normalize_sku(sku_custom)
    # Autogeneración de SKU si no viene definido:
    # - Si hay categoría, la secuencia es por categoría
    # - Si no hay categoría, la secuencia agrupa por category_id NULL y usa prefijos por defecto
    if not sku_custom:
        # Determinar secuencia inicial según categoría (o NULL)
        if req.category_id is not None:
            base_query = select(CanonicalProduct).where(CanonicalProduct.category_id == req.category_id)
        else:
            base_query = select(CanonicalProduct).where(CanonicalProduct.category_id.is_(None))
        total = await session.scalar(select(func.count()).select_from(base_query.subquery())) or 0
        next_seq = int(total) + 1
        cat_name = await _get_category_name(session, req.category_id)
        sub_name = await _get_category_name(session, req.subcategory_id) if req.subcategory_id else None
        # Reintento ante colisión: incrementar secuencia y reconstruir
        attempts = 0
        while attempts < 5:
            candidate = build_canonical_sku(cat_name, sub_name, next_seq)
            exists = await session.scalar(select(CanonicalProduct).where(CanonicalProduct.sku_custom == candidate))
            if not exists:
                sku_custom = candidate
                break
            attempts += 1
            next_seq += 1
        if not sku_custom:
            # Último recurso: usar sufijo aleatorio corto para no bloquear creación
            import random, string
            suf = ''.join(random.choices(string.ascii_uppercase + string.digits, k=2))
            sku_custom = f"{build_canonical_sku(cat_name, sub_name, next_seq)}{suf}"
    # Unicidad
    if sku_custom:
        exists = await session.scalar(select(CanonicalProduct).where(CanonicalProduct.sku_custom == sku_custom))
        if exists:
            raise HTTPException(status_code=409, detail="SKU canónico duplicado")
    cp = CanonicalProduct(
        name=req.name,
        brand=req.brand,
        specs_json=req.specs_json,
        sku_custom=sku_custom,
        category_id=req.category_id,
        subcategory_id=req.subcategory_id,
    )
    session.add(cp)
    # Insert first to get an id, then set ng_sku and commit
    await session.flush()
    cp.ng_sku = f"NG-{cp.id:06d}"
    await session.commit()
    await session.refresh(cp)
    # Auditoría
    # Incluir correlation id si viene del request
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
from db.models import Category, AuditLog
from sqlalchemy import text

def normalize_sku(value: str) -> str:
    return (value or '').strip().upper()

async def _get_category_name(session: AsyncSession, category_id: int | None) -> str | None:
    if not category_id:
        return None
    c = await session.get(Category, category_id)
    return c.name if c else None

def _slugify3(name: str | None, fallback: str) -> str:
    """Toma hasta 3 letras del nombre, removiendo acentos/diacríticos.

    Evita usar clases Unicode (\p{M}) no soportadas por `re` estándar en Python.
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
