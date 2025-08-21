"""Endpoints para gestionar proveedores y categorías."""
from __future__ import annotations

import os
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ValidationError
from sqlalchemy import func, select, or_
from sqlalchemy.ext.asyncio import AsyncSession

from db.models import (
    Category,
    Supplier,
    SupplierFile,
    SupplierPriceHistory,
    SupplierProduct,
    Product,
    ProductEquivalence,
)
from db.session import get_session
from services.auth import require_csrf, require_roles

router = APIRouter(tags=["catalog"])

# Tamaño de página por defecto para el historial de precios
DEFAULT_PRICE_HISTORY_PAGE_SIZE = int(os.getenv("PRICE_HISTORY_PAGE_SIZE", "20"))


# ------------------------------- Proveedores -------------------------------


class SupplierCreate(BaseModel):
    slug: str
    name: str


class SupplierUpdate(BaseModel):
    name: str


@router.get("/suppliers")
async def list_suppliers(
    session: AsyncSession = Depends(get_session),
) -> List[dict]:
    """Lista proveedores con estadísticas básicas."""

    result = await session.execute(
        select(
            Supplier,
            func.count(SupplierFile.id).label("files_count"),
            func.max(SupplierFile.uploaded_at).label("last_upload"),
        ).outerjoin(SupplierFile, SupplierFile.supplier_id == Supplier.id)
        .group_by(Supplier.id)
        .order_by(Supplier.id)
    )
    rows = result.all()
    return [
        {
            "id": supplier.id,
            "slug": supplier.slug,
            "name": supplier.name,
            "created_at": supplier.created_at.isoformat(),
            "last_upload_at": last_upload.isoformat() if last_upload else None,
            "files_count": files_count,
        }
        for supplier, files_count, last_upload in rows
    ]


@router.get("/suppliers/{supplier_id}/files")
async def list_supplier_files(
    supplier_id: int, session: AsyncSession = Depends(get_session)
) -> List[dict]:
    """Lista archivos subidos por un proveedor."""

    result = await session.execute(
        select(SupplierFile).where(SupplierFile.supplier_id == supplier_id)
    )
    files = result.scalars().all()
    return [
        {
            "id": f.id,
            "filename": f.filename,
            "sha256": f.sha256,
            "rows": f.rows,
            "processed": f.processed,
            "dry_run": f.dry_run,
            "uploaded_at": f.uploaded_at.isoformat(),
        }
        for f in files
    ]


@router.post(
    "/suppliers",
    dependencies=[Depends(require_csrf), Depends(require_roles("admin"))],
)
async def create_supplier(
    request: Request, session: AsyncSession = Depends(get_session)
):
    """Crea un nuevo proveedor validando formato y unicidad de ``slug``."""

    if request.headers.get("content-type") != "application/json":
        raise HTTPException(
            status_code=415, detail="Content-Type debe ser application/json"
        )
    try:
        payload = SupplierCreate.model_validate(await request.json())
    except ValidationError:
        return JSONResponse(
            status_code=400,
            content={"code": "invalid_payload", "message": "Faltan campos"},
        )

    existing = await session.scalar(
        select(Supplier).where(Supplier.slug == payload.slug)
    )
    if existing:
        return JSONResponse(
            status_code=409,
            content={"code": "slug_conflict", "message": "Slug ya utilizado"},
        )
    supplier = Supplier(slug=payload.slug, name=payload.name)
    session.add(supplier)
    await session.commit()
    await session.refresh(supplier)
    return {
        "id": supplier.id,
        "slug": supplier.slug,
        "name": supplier.name,
        "created_at": supplier.created_at.isoformat(),
    }


@router.patch(
    "/suppliers/{supplier_id}",
    dependencies=[Depends(require_csrf), Depends(require_roles("admin"))],
)
async def update_supplier(
    supplier_id: int, req: SupplierUpdate, session: AsyncSession = Depends(get_session)
) -> dict:
    """Actualiza el nombre de un proveedor existente."""

    supplier = await session.get(Supplier, supplier_id)
    if not supplier:
        raise HTTPException(status_code=404, detail="Proveedor no encontrado")
    supplier.name = req.name
    await session.commit()
    await session.refresh(supplier)
    return {
        "id": supplier.id,
        "slug": supplier.slug,
        "name": supplier.name,
    }


# ------------------------------- Categorías -------------------------------


class CategoryGenRequest(BaseModel):
    file_id: int
    dry_run: bool = True


def _build_category_path(cat: Category, lookup: dict[int, Category]) -> str:
    parts: List[str] = [cat.name]
    parent_id = cat.parent_id
    while parent_id:
        parent = lookup[parent_id]
        parts.append(parent.name)
        parent_id = parent.parent_id
    return ">".join(reversed(parts))


@router.get("/categories")
async def list_categories(
    session: AsyncSession = Depends(get_session),
) -> List[dict]:
    """Lista categorías con su jerarquía completa."""

    result = await session.execute(select(Category))
    cats = result.scalars().all()
    lookup = {c.id: c for c in cats}
    return [
        {
            "id": c.id,
            "name": c.name,
            "parent_id": c.parent_id,
            "path": _build_category_path(c, lookup),
        }
        for c in cats
    ]


@router.get("/categories/search")
async def search_categories(q: str, session: AsyncSession = Depends(get_session)) -> List[dict]:
    """Busca categorías por nombre o path parcial."""

    result = await session.execute(
        select(Category).where(Category.name.ilike(f"%{q}%"))
    )
    cats = result.scalars().all()
    lookup = {c.id: c for c in cats}
    return [
        {
            "id": c.id,
            "name": c.name,
            "parent_id": c.parent_id,
            "path": _build_category_path(c, lookup),
        }
        for c in cats
    ]


@router.post(
    "/categories/generate-from-supplier-file",
    dependencies=[Depends(require_csrf), Depends(require_roles("admin"))],
)
async def generate_categories(
    req: CategoryGenRequest, session: AsyncSession = Depends(get_session)
) -> dict:
    """Genera categorías a partir de un archivo de proveedor."""

    # Obtener productos asociados al archivo
    stmt = (
        select(SupplierProduct)
        .join(SupplierPriceHistory, SupplierPriceHistory.supplier_product_fk == SupplierProduct.id)
        .where(SupplierPriceHistory.file_fk == req.file_id)
    )
    result = await session.execute(stmt)
    products = result.scalars().all()

    paths = set()
    for p in products:
        levels = [
            lvl
            for lvl in [p.category_level_1, p.category_level_2, p.category_level_3]
            if lvl
        ]
        if levels:
            paths.add(">".join(levels))

    # Categorías existentes para comparar
    existing_result = await session.execute(select(Category))
    existing_cats = existing_result.scalars().all()
    lookup = {c.id: c for c in existing_cats}
    existing_paths = {_build_category_path(c, lookup) for c in existing_cats}

    proposed = []
    created: List[str] = []
    skipped: List[str] = []

    for path in sorted(paths):
        if path in existing_paths:
            proposed.append({"path": path, "status": "exists"})
            skipped.append(path)
            continue
        proposed.append({"path": path, "status": "new"})
        if req.dry_run:
            continue
        # Crear jerarquía faltante
        parent_id = None
        for name in path.split(">"):
            q = select(Category).where(
                Category.name == name, Category.parent_id == parent_id
            )
            cat = await session.scalar(q)
            if not cat:
                cat = Category(name=name, parent_id=parent_id)
                session.add(cat)
                await session.flush()
            parent_id = cat.id
        created.append(path)
        existing_paths.add(path)

    if not req.dry_run:
        await session.commit()

    return {"proposed": proposed, "created": created, "skipped": skipped}


# ------------------------------- Productos -------------------------------


async def _category_path(session: AsyncSession, category_id: int | None) -> str | None:
    if not category_id:
        return None
    parts: List[str] = []
    current_id = category_id
    while current_id:
        cat = await session.get(Category, current_id)
        if not cat:
            break
        parts.append(cat.name)
        current_id = cat.parent_id
    return ">".join(reversed(parts)) if parts else None


@router.get(
    "/products",
    dependencies=[
        Depends(require_roles("cliente", "proveedor", "colaborador", "admin"))
    ],
)
async def list_products(
    supplier_id: Optional[int] = None,
    category_id: Optional[int] = None,
    q: Optional[str] = None,
    page: int = 1,
    page_size: int = 20,
    sort_by: str = "updated_at",
    order: str = "desc",
    *,
    session: AsyncSession = Depends(get_session),
) -> dict:
    """Lista productos de proveedores con filtros, orden y paginación."""

    max_page = int(os.getenv("PRODUCTS_PAGE_MAX", "100"))
    if page < 1 or page_size < 1 or page_size > max_page:
        raise HTTPException(status_code=400, detail="paginación inválida")

    sp = SupplierProduct
    p = Product
    s = Supplier
    eq = ProductEquivalence

    stmt = (
        select(sp, p, s, eq)
        .join(s, sp.supplier_id == s.id)
        .join(p, sp.internal_product_id == p.id)
        .outerjoin(eq, eq.supplier_product_id == sp.id)
    )

    if supplier_id is not None:
        stmt = stmt.where(sp.supplier_id == supplier_id)
    if category_id is not None:
        stmt = stmt.where(p.category_id == category_id)
    if q:
        stmt = stmt.where(
            or_(p.title.ilike(f"%{q}%"), sp.title.ilike(f"%{q}%"))
        )

    count_stmt = select(func.count()).select_from(stmt.subquery())
    total = await session.scalar(count_stmt) or 0

    sort_map = {
        "updated_at": sp.last_seen_at,
        "precio_venta": sp.current_sale_price,
        "precio_compra": sp.current_purchase_price,
        "name": p.title,
    }
    sort_col = sort_map.get(sort_by, sp.last_seen_at)
    sort_col = sort_col.asc() if order == "asc" else sort_col.desc()

    stmt = (
        stmt.order_by(sort_col)
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    result = await session.execute(stmt)
    rows = result.all()

    items = []
    for sp_obj, p_obj, s_obj, eq_obj in rows:
        cat_path = await _category_path(session, p_obj.category_id)
        items.append(
            {
                "product_id": p_obj.id,
                "name": p_obj.title,
                "supplier": {
                    "id": s_obj.id,
                    "slug": s_obj.slug,
                    "name": s_obj.name,
                },
                "precio_compra": float(sp_obj.current_purchase_price)
                if sp_obj.current_purchase_price is not None
                else None,
                "precio_venta": float(sp_obj.current_sale_price)
                if sp_obj.current_sale_price is not None
                else None,
                "compra_minima": float(sp_obj.min_purchase_qty)
                if sp_obj.min_purchase_qty is not None
                else None,
                "category_path": cat_path,
                "stock": p_obj.stock,
                "updated_at": sp_obj.last_seen_at.isoformat()
                if sp_obj.last_seen_at
                else None,
                "canonical_product_id": eq_obj.canonical_product_id if eq_obj else None,
            }
        )

    return {
        "page": page,
        "page_size": page_size,
        "total": total,
        "items": items,
    }


class StockUpdate(BaseModel):
    stock: int


@router.patch(
    "/products/{product_id}/stock",
    dependencies=[Depends(require_csrf), Depends(require_roles("manager", "admin"))],
)
async def update_product_stock(
    product_id: int,
    payload: StockUpdate,
    session: AsyncSession = Depends(get_session),
) -> dict:
    if payload.stock < 0 or payload.stock > 1_000_000_000:
        raise HTTPException(status_code=400, detail="stock fuera de rango")
    prod = await session.get(Product, product_id)
    if not prod:
        raise HTTPException(status_code=404, detail="Producto no encontrado")
    prod.stock = payload.stock
    await session.commit()
    return {"product_id": product_id, "stock": prod.stock}


# --------------------------- Historial de precios --------------------------


class PriceHistoryItem(BaseModel):
    as_of_date: str
    purchase_price: Optional[float]
    sale_price: Optional[float]
    delta_purchase_pct: Optional[float]
    delta_sale_pct: Optional[float]


class PriceHistoryResponse(BaseModel):
    page: int
    page_size: int
    total: int
    items: List[PriceHistoryItem]


@router.get(
    "/price-history",
    dependencies=[
        Depends(require_roles("cliente", "proveedor", "colaborador", "admin"))
    ],
)
async def get_price_history(
    supplier_product_id: Optional[int] = Query(None),
    product_id: Optional[int] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(DEFAULT_PRICE_HISTORY_PAGE_SIZE, ge=1, le=100),
    session: AsyncSession = Depends(get_session),
) -> PriceHistoryResponse:
    """Devuelve el historial de precios ordenado por fecha."""

    if not supplier_product_id and not product_id:
        raise HTTPException(
            status_code=400,
            detail="Debe indicar supplier_product_id o product_id",
        )

    if supplier_product_id:
        base_query = select(SupplierPriceHistory).where(
            SupplierPriceHistory.supplier_product_fk == supplier_product_id
        )
    else:
        base_query = (
            select(SupplierPriceHistory)
            .join(SupplierProduct)
            .where(SupplierProduct.internal_product_id == product_id)
        )

    total = await session.scalar(
        select(func.count()).select_from(base_query.subquery())
    )

    result = await session.execute(
        base_query.order_by(SupplierPriceHistory.as_of_date.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    rows = result.scalars().all()

    return PriceHistoryResponse(
        page=page,
        page_size=page_size,
        total=total or 0,
        items=[
            PriceHistoryItem(
                as_of_date=r.as_of_date.isoformat(),
                purchase_price=float(r.purchase_price)
                if r.purchase_price is not None
                else None,
                sale_price=float(r.sale_price)
                if r.sale_price is not None
                else None,
                delta_purchase_pct=float(r.delta_purchase_pct)
                if r.delta_purchase_pct is not None
                else None,
                delta_sale_pct=float(r.delta_sale_pct)
                if r.delta_sale_pct is not None
                else None,
            )
            for r in rows
        ],
    )
