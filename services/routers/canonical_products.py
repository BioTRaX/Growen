"""Endpoints para productos canónicos y equivalencias."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
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
from services.auth import require_csrf, require_roles

canonical_router = APIRouter(prefix="/canonical-products", tags=["catalog"])
equivalences_router = APIRouter(prefix="/equivalences", tags=["catalog"])


class CanonicalCreate(BaseModel):
    name: str
    brand: str | None = None
    specs_json: dict | None = None


class CanonicalUpdate(BaseModel):
    name: str | None = None
    brand: str | None = None
    specs_json: dict | None = None


@canonical_router.post(
    "",
    dependencies=[Depends(require_csrf), Depends(require_roles("admin"))],
)
async def create_canonical_product(
    req: CanonicalCreate, session: AsyncSession = Depends(get_session)
) -> dict:
    """Crea un producto canónico y genera un ``ng_sku`` único."""
    cp = CanonicalProduct(name=req.name, brand=req.brand, specs_json=req.specs_json)
    session.add(cp)
    await session.flush()
    cp.ng_sku = f"NG-{cp.id:06d}"
    await session.commit()
    await session.refresh(cp)
    return {
        "id": cp.id,
        "ng_sku": cp.ng_sku,
        "name": cp.name,
        "brand": cp.brand,
        "specs_json": cp.specs_json,
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
                "name": cp.name,
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
        "name": cp.name,
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
    session: AsyncSession = Depends(get_session),
) -> dict:
    """Actualiza un producto canónico."""
    cp = await session.get(CanonicalProduct, canonical_id)
    if not cp:
        raise HTTPException(status_code=404, detail="Canonical product not found")
    data = req.model_dump(exclude_unset=True)
    for k, v in data.items():
        setattr(cp, k, v)
    await session.commit()
    await session.refresh(cp)
    return {
        "id": cp.id,
        "ng_sku": cp.ng_sku,
        "name": cp.name,
        "brand": cp.brand,
        "specs_json": cp.specs_json,
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
