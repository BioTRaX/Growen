# NG-HEADER: Nombre de archivo: catalog.py
# NG-HEADER: Ubicación: services/routers/catalog.py
# NG-HEADER: Descripción: Pendiente de descripción
# NG-HEADER: Lineamientos: Ver AGENTS.md
"""Endpoints para gestionar proveedores y categorías."""
from __future__ import annotations

import os
from enum import Enum
from typing import List, Optional
import hashlib
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Query, Request, UploadFile, File, Form
from fastapi.responses import JSONResponse, StreamingResponse
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
    Image,
    ProductEquivalence,
    CanonicalProduct,
    AuditLog,
)
from db.session import get_session
from services.auth import require_csrf, require_roles, current_session, SessionData

router = APIRouter(tags=["catalog"])

# Tamaño de página por defecto para el historial de precios
DEFAULT_PRICE_HISTORY_PAGE_SIZE = int(os.getenv("PRICE_HISTORY_PAGE_SIZE", "20"))


# ------------------------------- Proveedores -------------------------------


class SupplierCreate(BaseModel):
    slug: str
    name: str
    location: Optional[str] = None
    contact_name: Optional[str] = None
    contact_email: Optional[str] = None
    contact_phone: Optional[str] = None
    notes: Optional[str] = None
    extra_json: Optional[dict] = None


class SupplierUpdate(BaseModel):
    name: str
    location: Optional[str] = None
    contact_name: Optional[str] = None
    contact_email: Optional[str] = None
    contact_phone: Optional[str] = None
    notes: Optional[str] = None
    extra_json: Optional[dict] = None


ALLOWED_SUPPLIER_FILE_EXT = {"pdf", "txt", "csv", "xls", "xlsx", "ods", "png", "jpg", "jpeg", "webp"}
MAX_SUPPLIER_FILE_BYTES = int(os.getenv("SUPPLIER_FILE_MAX_BYTES", "10485760"))  # 10MB por defecto
SUPPLIER_FILES_ROOT = Path(os.getenv("SUPPLIER_FILES_ROOT", "data/suppliers"))


@router.get(
    "/suppliers",
    dependencies=[Depends(require_roles("cliente", "proveedor", "colaborador", "admin"))],
)
async def list_suppliers(
    session: AsyncSession = Depends(get_session),
) -> List[dict]:
    """Lista proveedores con estadísticas básicas."""

    result = await session.execute(
        select(
            Supplier,
            func.count(SupplierFile.id).label("files_count"),
            func.max(SupplierFile.uploaded_at).label("last_upload"),
        )
        .outerjoin(SupplierFile, SupplierFile.supplier_id == Supplier.id)
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


@router.get(
    "/suppliers/{supplier_id}",
    dependencies=[
        Depends(require_roles("cliente", "proveedor", "colaborador", "admin"))
    ],
)
async def get_supplier(
    supplier_id: int, session: AsyncSession = Depends(get_session)
) -> dict:
    supplier = await session.get(Supplier, supplier_id)
    if not supplier:
        raise HTTPException(status_code=404, detail="Proveedor no encontrado")
    return {
        "id": supplier.id,
        "slug": supplier.slug,
        "name": supplier.name,
        "location": supplier.location,
        "contact_name": supplier.contact_name,
        "contact_email": supplier.contact_email,
        "contact_phone": supplier.contact_phone,
        "notes": supplier.notes,
        "extra_json": supplier.extra_json,
        "created_at": supplier.created_at.isoformat(),
    }


@router.get(
    "/suppliers/{supplier_id}/files",
    dependencies=[
        Depends(require_roles("cliente", "proveedor", "colaborador", "admin"))
    ],
)
async def list_supplier_files(
    supplier_id: int, session: AsyncSession = Depends(get_session)
) -> List[dict]:
    """Lista archivos subidos por un proveedor."""

    result = await session.execute(
        select(SupplierFile)
        .where(SupplierFile.supplier_id == supplier_id)
        .order_by(SupplierFile.uploaded_at.desc())
    )
    files = result.scalars().all()
    return [
        {
            "id": f.id,
            "filename": f.filename,
            "original_name": f.original_name or f.filename,
            "sha256": f.sha256,
            "rows": f.rows,
            "processed": f.processed,
            "dry_run": f.dry_run,
            "uploaded_at": f.uploaded_at.isoformat(),
            "content_type": f.content_type,
            "size_bytes": f.size_bytes,
        }
        for f in files
    ]


@router.post(
    "/suppliers/{supplier_id}/files/upload",
    dependencies=[Depends(require_roles("admin", "colaborador")), Depends(require_csrf)],
)
async def upload_supplier_file(
    supplier_id: int,
    file: UploadFile = File(...),
    notes: Optional[str] = Form(None),
    session: AsyncSession = Depends(get_session),
):
    sup = await session.get(Supplier, supplier_id)
    if not sup:
        raise HTTPException(status_code=404, detail="Proveedor no encontrado")
    original_name = file.filename or "archivo"
    ext = original_name.rsplit('.', 1)[-1].lower() if '.' in original_name else ''
    if ext not in ALLOWED_SUPPLIER_FILE_EXT:
        raise HTTPException(status_code=400, detail="Tipo de archivo no permitido")
    data = await file.read()
    size = len(data)
    if size > MAX_SUPPLIER_FILE_BYTES:
        raise HTTPException(status_code=413, detail="Archivo demasiado grande")
    sha256 = hashlib.sha256(data).hexdigest()
    existing = await session.scalar(
        select(SupplierFile).where(
            SupplierFile.supplier_id == supplier_id,
            SupplierFile.sha256 == sha256,
        )
    )
    if existing:
        return {
            "id": existing.id,
            "filename": existing.filename,
            "original_name": existing.original_name or existing.filename,
            "uploaded_at": existing.uploaded_at.isoformat(),
            "sha256": existing.sha256,
            "size_bytes": existing.size_bytes,
            "content_type": existing.content_type,
            "processed": existing.processed,
            "dry_run": existing.dry_run,
            "rows": existing.rows,
            "duplicate": True,
        }
    SUPPLIER_FILES_ROOT.mkdir(parents=True, exist_ok=True)
    supplier_dir = SUPPLIER_FILES_ROOT / str(supplier_id)
    supplier_dir.mkdir(parents=True, exist_ok=True)
    safe_base = sha256[:12] + ('.' + ext if ext else '')
    disk_name = safe_base
    path = supplier_dir / disk_name
    with open(path, 'wb') as fh:
        fh.write(data)
    sf = SupplierFile(
        supplier_id=supplier_id,
        filename=disk_name,
        original_name=original_name[:255],
        content_type=file.content_type,
        size_bytes=size,
        sha256=sha256,
        rows=0,
        dry_run=True,
        processed=False,
        notes=notes,
    )
    session.add(sf)
    await session.commit()
    await session.refresh(sf)
    return {
        "id": sf.id,
        "filename": sf.filename,
        "original_name": sf.original_name,
        "uploaded_at": sf.uploaded_at.isoformat(),
        "sha256": sf.sha256,
        "size_bytes": sf.size_bytes,
        "content_type": sf.content_type,
        "processed": sf.processed,
        "dry_run": sf.dry_run,
        "rows": sf.rows,
    }


@router.get(
    "/suppliers/files/{file_id}/download",
    dependencies=[Depends(require_roles("cliente", "proveedor", "colaborador", "admin"))],
)
async def download_supplier_file(
    file_id: int, session: AsyncSession = Depends(get_session)
):
    sf = await session.get(SupplierFile, file_id)
    if not sf:
        raise HTTPException(status_code=404, detail="Archivo no encontrado")
    supplier_dir = SUPPLIER_FILES_ROOT / str(sf.supplier_id)
    path = supplier_dir / sf.filename
    if not path.exists():
        raise HTTPException(status_code=410, detail="Archivo ausente en disco")

    def iterfile():
        with open(path, 'rb') as fh:
            while True:
                chunk = fh.read(8192)
                if not chunk:
                    break
                yield chunk

    return StreamingResponse(
        iterfile(),
        media_type=sf.content_type or 'application/octet-stream',
        headers={
            'Content-Disposition': f'attachment; filename="{sf.original_name or sf.filename}"'
        },
    )


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
    supplier = Supplier(
        slug=payload.slug,
        name=payload.name,
        location=payload.location,
        contact_name=payload.contact_name,
        contact_email=payload.contact_email,
        contact_phone=payload.contact_phone,
        notes=payload.notes,
        extra_json=payload.extra_json,
    )
    session.add(supplier)
    await session.commit()
    await session.refresh(supplier)
    return {
        "id": supplier.id,
        "slug": supplier.slug,
        "name": supplier.name,
        "location": supplier.location,
        "contact_name": supplier.contact_name,
        "contact_email": supplier.contact_email,
        "contact_phone": supplier.contact_phone,
        "notes": supplier.notes,
        "extra_json": supplier.extra_json,
        "created_at": supplier.created_at.isoformat(),
    }


@router.get(
    "/suppliers/{supplier_id}/items",
    dependencies=[Depends(require_roles("cliente", "proveedor", "colaborador", "admin"))],
)
async def supplier_items_lookup(
    supplier_id: int,
    sku_like: Optional[str] = Query(None, min_length=1),
    q: Optional[str] = Query(None),
    limit: int = Query(10, ge=1, le=50),
    session: AsyncSession = Depends(get_session),
) -> List[dict]:
    """Autocomplete de ítems del proveedor por SKU (supplier_product_id) o título.

    - Retorna hasta `limit` resultados con `id`, `supplier_product_id` y `title`.
    """
    stmt = select(SupplierProduct).where(SupplierProduct.supplier_id == supplier_id)
    if sku_like:
        stmt = stmt.where(SupplierProduct.supplier_product_id.ilike(f"%{sku_like}%"))
    if q:
        stmt = stmt.where(SupplierProduct.title.ilike(f"%{q}%"))
    stmt = stmt.limit(limit)
    rows = (await session.execute(stmt)).scalars().all()
    return [
        {
            "id": r.id,
            "supplier_product_id": r.supplier_product_id,
            "title": r.title,
            "product_id": r.internal_product_id,
        }
        for r in rows
    ]


class SupplierItemCreate(BaseModel):
    """Payload para crear una oferta (SupplierProduct) manualmente.

    - supplier_product_id: SKU o identificador del proveedor (obligatorio)
    - title: título descriptivo
    - product_id: id de producto interno a asociar (opcional)
    - purchase_price / sale_price: precios actuales si se desean registrar
    """

    supplier_product_id: str
    title: str
    product_id: Optional[int] = None
    purchase_price: Optional[float] = None
    sale_price: Optional[float] = None


@router.post(
    "/suppliers/{supplier_id}/items",
    dependencies=[Depends(require_csrf), Depends(require_roles("colaborador", "admin"))],
)
async def create_supplier_item(
    supplier_id: int,
    payload: SupplierItemCreate,
    request: Request,
    session_data: SessionData = Depends(current_session),
    session: AsyncSession = Depends(get_session),
):
    """Crea un SupplierProduct manualmente.

    Reglas:
    - Enforce unicidad (supplier_id, supplier_product_id)
    - Si `product_id` se envía, validar que exista el producto.
    - Registra AuditLog con acción `supplier_item_create`.
    """
    supplier = await session.get(Supplier, supplier_id)
    if not supplier:
        raise HTTPException(status_code=404, detail="Proveedor no encontrado")

    existing = await session.scalar(
        select(SupplierProduct).where(
            SupplierProduct.supplier_id == supplier_id,
            SupplierProduct.supplier_product_id == payload.supplier_product_id,
        )
    )
    if existing:
        return JSONResponse(
            status_code=409,
            content={
                "code": "supplier_item_exists",
                "message": "Ya existe un item con ese identificador para el proveedor",
                "id": existing.id,
            },
        )

    internal_product_id: Optional[int] = None
    if payload.product_id is not None:
        prod = await session.get(Product, payload.product_id)
        if not prod:
            raise HTTPException(status_code=400, detail="product_id inválido")
        internal_product_id = prod.id

    sp = SupplierProduct(
        supplier_id=supplier_id,
        supplier_product_id=payload.supplier_product_id.strip(),
        title=payload.title.strip(),
        current_purchase_price=payload.purchase_price,
        current_sale_price=payload.sale_price,
        internal_product_id=internal_product_id,
    )
    session.add(sp)
    await session.commit()
    await session.refresh(sp)

    try:
        session.add(
            AuditLog(
                action="supplier_item_create",
                table="supplier_products",
                entity_id=sp.id,
                meta={
                    "supplier_product_id": sp.supplier_product_id,
                    "title": sp.title,
                    "product_id": sp.internal_product_id,
                    "purchase_price": sp.current_purchase_price,
                    "sale_price": sp.current_sale_price,
                },
                user_id=session_data.user.id if session_data.user else None,
                ip=(request.client.host if request and request.client else None),
            )
        )
        await session.commit()
    except Exception:
        pass

    return {
        "id": sp.id,
        "supplier_product_id": sp.supplier_product_id,
        "title": sp.title,
        "product_id": sp.internal_product_id,
        "purchase_price": float(sp.current_purchase_price) if sp.current_purchase_price is not None else None,
        "sale_price": float(sp.current_sale_price) if sp.current_sale_price is not None else None,
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
    supplier.location = req.location
    supplier.contact_name = req.contact_name
    supplier.contact_email = req.contact_email
    supplier.contact_phone = req.contact_phone
    supplier.notes = req.notes
    supplier.extra_json = req.extra_json
    await session.commit()
    await session.refresh(supplier)
    return {
        "id": supplier.id,
        "slug": supplier.slug,
        "name": supplier.name,
        "location": supplier.location,
        "contact_name": supplier.contact_name,
        "contact_email": supplier.contact_email,
        "contact_phone": supplier.contact_phone,
        "notes": supplier.notes,
        "extra_json": supplier.extra_json,
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


@router.get(
    "/categories",
    dependencies=[
        Depends(require_roles("cliente", "proveedor", "colaborador", "admin"))
    ],
)
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


@router.get(
    "/categories/search",
    dependencies=[
        Depends(require_roles("cliente", "proveedor", "colaborador", "admin"))
    ],
)
async def search_categories(
    q: str, session: AsyncSession = Depends(get_session)
) -> List[dict]:
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


class ProductSortBy(str, Enum):
    updated_at = "updated_at"
    precio_venta = "precio_venta"
    precio_compra = "precio_compra"
    name = "name"
    created_at = "created_at"


class SortOrder(str, Enum):
    asc = "asc"
    desc = "desc"


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
    stock: Optional[str] = None,
    created_since_days: Optional[int] = None,
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

    try:
        sort_by_enum = ProductSortBy(sort_by)
    except ValueError:
        raise HTTPException(status_code=400, detail="sort_by inválido")

    try:
        order_enum = SortOrder(order)
    except ValueError:
        raise HTTPException(status_code=400, detail="order inválido")

    sp = SupplierProduct
    p = Product
    s = Supplier
    eq = ProductEquivalence
    cp = CanonicalProduct

    stmt = (
        select(sp, p, s, eq, cp)
        .join(s, sp.supplier_id == s.id)
        .join(p, sp.internal_product_id == p.id)
        .outerjoin(eq, eq.supplier_product_id == sp.id)
        .outerjoin(cp, cp.id == eq.canonical_product_id)
    )

    if supplier_id is not None:
        stmt = stmt.where(sp.supplier_id == supplier_id)
    if category_id is not None:
        stmt = stmt.where(p.category_id == category_id)
    if q:
        stmt = stmt.where(
            or_(p.title.ilike(f"%{q}%"), sp.title.ilike(f"%{q}%"))
        )
    # Stock filter: 'gt:0' or 'eq:0'
    if stock:
        try:
            op, val = stock.split(":", 1)
            val_i = int(val)
        except Exception:
            raise HTTPException(status_code=400, detail="stock inválido (use gt:0 o eq:0)")
        if op == "gt":
            stmt = stmt.where(p.stock > val_i)
        elif op == "eq":
            stmt = stmt.where(p.stock == val_i)
        else:
            raise HTTPException(status_code=400, detail="stock inválido (op debe ser gt o eq)")
    # Filtro de productos creados recientemente
    if created_since_days is not None:
        if created_since_days < 0 or created_since_days > 365:
            raise HTTPException(status_code=400, detail="created_since_days fuera de rango (0-365)")
        from datetime import datetime, timedelta
        cutoff = datetime.utcnow() - timedelta(days=created_since_days)
        stmt = stmt.where(p.created_at >= cutoff)

    count_stmt = select(func.count()).select_from(stmt.subquery())
    total = await session.scalar(count_stmt) or 0

    sort_map = {
        ProductSortBy.updated_at: sp.last_seen_at,
        ProductSortBy.precio_venta: sp.current_sale_price,
        ProductSortBy.precio_compra: sp.current_purchase_price,
        ProductSortBy.name: p.title,
        ProductSortBy.created_at: p.created_at,
    }
    sort_col = sort_map[sort_by_enum]
    sort_col = sort_col.asc() if order_enum == SortOrder.asc else sort_col.desc()

    stmt = (
        stmt.order_by(sort_col)
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    result = await session.execute(stmt)
    rows = result.all()

    items = []
    for sp_obj, p_obj, s_obj, eq_obj, cp_obj in rows:
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
                "canonical_sale_price": float(cp_obj.sale_price) if (cp_obj and cp_obj.sale_price is not None) else None,
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


class ProductCreate(BaseModel):
    title: str
    category_id: Optional[int] = None
    initial_stock: int = 0
    status: Optional[str] = None
    # Campos opcionales para autocreación de SupplierProduct desde flujo de compras
    supplier_id: Optional[int] = None
    supplier_sku: Optional[str] = None
    # Permite, si se conoce, enlazar directamente con un producto canónico
    canonical_product_id: Optional[int] = None
    # Diagnóstico: contexto de compra (no es necesario validar existencia de línea aquí)
    purchase_id: Optional[int] = None
    purchase_line_index: Optional[int] = None

    def validate_values(self):
        if self.initial_stock < 0:
            raise ValueError("initial_stock debe ser >= 0")


def _slugify(value: str) -> str:
    value = value.lower().strip()
    repl = []
    for ch in value:
        if ch.isalnum():
            repl.append(ch)
        elif ch in {" ", "-", "_"}:
            repl.append("-")
    slug = "".join(repl)
    while "--" in slug:
        slug = slug.replace("--", "-")
    return slug.strip("-")[:180]


def _gen_sku_root(title: str) -> str:
    base = ''.join([c for c in title.upper() if c.isalnum()])[:8]
    if not base:
        base = "PRD"
    return base


@router.post(
    "/products",
    dependencies=[Depends(require_csrf), Depends(require_roles("colaborador", "admin"))],
)
async def create_product(
    payload: ProductCreate,
    session: AsyncSession = Depends(get_session),
    request: Request = None,
    sess: SessionData = Depends(current_session),
):
    try:
        payload.validate_values()
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    # Validar categoría si se provee
    if payload.category_id is not None:
        cat = await session.get(Category, payload.category_id)
        if not cat:
            raise HTTPException(status_code=400, detail="category_id inválido")
    sku_root = _gen_sku_root(payload.title)
    slug = _slugify(payload.title)
    # Reglas de stock inicial:
    # - Si la creación se hace en contexto de compra (purchase_id) o se pasa supplier_id+supplier_sku
    #   siempre forzamos stock=0 para evitar doble sumatoria (la confirmación aplicará las cantidades).
    force_zero = bool(payload.purchase_id or (payload.supplier_id and payload.supplier_sku))
    initial_stock = 0 if force_zero else payload.initial_stock
    prod = Product(
        sku_root=sku_root,
        title=payload.title,
        category_id=payload.category_id,
        status=payload.status or "active",
        slug=slug,
        stock=initial_stock,
    )
    session.add(prod)
    await session.commit()
    await session.refresh(prod)
    supplier_product_id = None
    created_supplier_product_id = None
    created_equivalence_id = None
    canonical_product_id = None
    import logging
    logger = logging.getLogger("app")

    # Intentar autocreación de SupplierProduct si vienen datos
    if payload.supplier_id and payload.supplier_sku:
        from db.models import SupplierProduct, ProductEquivalence, CanonicalProduct, Supplier
        # Validar proveedor
        sup = await session.get(Supplier, payload.supplier_id)
        if sup:
            # ¿Existe ya un SupplierProduct con ese SKU?
            existing_sp = await session.scalar(
                select(SupplierProduct).where(
                    SupplierProduct.supplier_id == payload.supplier_id,
                    SupplierProduct.supplier_product_id == payload.supplier_sku,
                )
            )
            if existing_sp and existing_sp.internal_product_id and existing_sp.internal_product_id != prod.id:
                # Evitar sobreescribir vínculo existente; se registrará en log
                supplier_product_id = existing_sp.id
            elif existing_sp:
                # Completar internal_product_id si faltaba
                if not existing_sp.internal_product_id:
                    existing_sp.internal_product_id = prod.id
                    supplier_product_id = existing_sp.id
                    created_supplier_product_id = existing_sp.id  # Se considera actualización
            else:
                # Crear nuevo SupplierProduct
                sp = SupplierProduct(
                    supplier_id=payload.supplier_id,
                    supplier_product_id=payload.supplier_sku,
                    title=payload.title[:200],
                    internal_product_id=prod.id,
                )
                session.add(sp)
                await session.flush()
                supplier_product_id = sp.id
                created_supplier_product_id = sp.id
            # Crear equivalencia canónica opcional
            if payload.canonical_product_id:
                canonical = await session.get(CanonicalProduct, payload.canonical_product_id)
                if canonical and supplier_product_id:
                    canonical_product_id = canonical.id
                    existing_eq = await session.scalar(
                        select(ProductEquivalence).where(
                            ProductEquivalence.supplier_id == payload.supplier_id,
                            ProductEquivalence.supplier_product_id == supplier_product_id,
                        )
                    )
                    if not existing_eq:
                        eq = ProductEquivalence(
                            supplier_id=payload.supplier_id,
                            supplier_product_id=supplier_product_id,
                            canonical_product_id=canonical.id,
                            confidence=1.0,
                            source="auto_create",
                        )
                        session.add(eq)
                        await session.flush()
                        created_equivalence_id = eq.id
        await session.commit()
        await session.refresh(prod)

    # audit + logging estructurado
    try:
        meta_log = {
            "title": prod.title,
            "category_id": prod.category_id,
            "initial_stock_requested": payload.initial_stock,
            "initial_stock_final": initial_stock,
            "initial_stock_forced_zero": force_zero,
            "auto_link": bool(payload.supplier_id and payload.supplier_sku),
            "supplier_id": payload.supplier_id,
            "supplier_sku": payload.supplier_sku,
            "supplier_product_id": supplier_product_id,
            "created_supplier_product_id": created_supplier_product_id,
            "created_equivalence_id": created_equivalence_id,
            "canonical_product_id": canonical_product_id,
            "purchase_context": {
                "purchase_id": payload.purchase_id,
                "line_index": payload.purchase_line_index,
            },
        }
        try:
            logger.info(
                "product_create: id=%s supplier_id=%s supplier_sku=%s supplier_product_id=%s created_supplier_product_id=%s canonical_product_id=%s purchase_id=%s line_index=%s forced_zero=%s initial_stock=%s",
                prod.id,
                payload.supplier_id,
                payload.supplier_sku,
                supplier_product_id,
                created_supplier_product_id,
                canonical_product_id,
                payload.purchase_id,
                payload.purchase_line_index,
                force_zero,
                initial_stock,
            )
        except Exception:
            pass
        session.add(
            AuditLog(
                action="product_create",
                table="products",
                entity_id=prod.id,
                meta=meta_log,
                user_id=sess.user.id if sess and sess.user else None,
                ip=(request.client.host if request and request.client else None),
            )
        )
        await session.commit()
    except Exception:
        pass
    return {
        "id": prod.id,
        "title": prod.title,
        "sku_root": prod.sku_root,
        "slug": prod.slug,
        "stock": prod.stock,
        "category_id": prod.category_id,
        "status": prod.status,
        "supplier_product_id": supplier_product_id,
        "canonical_product_id": canonical_product_id,
    }


@router.patch(
    "/products/{product_id}/stock",
    dependencies=[Depends(require_csrf), Depends(require_roles("colaborador", "admin"))],
)
async def update_product_stock(
    product_id: int,
    payload: StockUpdate,
    session: AsyncSession = Depends(get_session),
    request: Request = None,
    sess: SessionData = Depends(current_session),
) -> dict:
    if payload.stock < 0 or payload.stock > 1_000_000_000:
        raise HTTPException(status_code=400, detail="stock fuera de rango")
    prod = await session.get(Product, product_id)
    if not prod:
        raise HTTPException(status_code=404, detail="Producto no encontrado")
    old = int(prod.stock or 0)
    prod.stock = payload.stock
    await session.commit()
    # audit
    try:
        session.add(
            AuditLog(
                action="product_stock_update",
                table="products",
                entity_id=product_id,
                meta={"old": old, "new": prod.stock},
                user_id=sess.user.id if sess and sess.user else None,
                ip=(request.client.host if request and request.client else None),
            )
        )
        await session.commit()
    except Exception:
        pass
    return {"product_id": product_id, "stock": prod.stock}


# ------------------------------ Producto por id ------------------------------


@router.get(
    "/products/{product_id}",
    dependencies=[Depends(require_roles("cliente", "proveedor", "colaborador", "admin"))],
)
async def get_product(product_id: int, session: AsyncSession = Depends(get_session)):
    prod = await session.get(Product, product_id)
    if not prod:
        raise HTTPException(status_code=404, detail="Producto no encontrado")
    imgs = (
        await session.execute(
            select(Image)
            .where(Image.product_id == product_id, Image.active == True)
            .order_by(Image.sort_order.asc().nulls_last(), Image.id.asc())
        )
    ).scalars().all()
    cat_path = await _category_path(session, prod.category_id)
    return {
        "id": prod.id,
        "title": prod.title,
        "slug": prod.slug,
        "stock": prod.stock,
        "sku_root": prod.sku_root,
        "category_path": cat_path,
        "description_html": prod.description_html,
        "images": [
            {
                "id": im.id,
                "url": im.url,
                "alt_text": im.alt_text,
                "title_text": im.title_text,
                "is_primary": im.is_primary,
                "locked": im.locked,
                "active": im.active,
            }
            for im in imgs
        ],
    }


class ProductUpdate(BaseModel):
    description_html: str | None = None


class ProductsDeleteRequest(BaseModel):
    ids: List[int]
    hard: bool = False  # futuro: permitir soft-delete si se agrega flag


@router.patch(
    "/products/{product_id}",
    dependencies=[Depends(require_csrf), Depends(require_roles("colaborador", "admin"))],
)
async def patch_product(product_id: int, payload: ProductUpdate, session: AsyncSession = Depends(get_session), request: Request = None, sess: SessionData = Depends(current_session)) -> dict:
    prod = await session.get(Product, product_id)
    if not prod:
        raise HTTPException(status_code=404, detail="Producto no encontrado")
    data = payload.model_dump(exclude_none=True)
    old_desc = getattr(prod, "description_html", None)
    if "description_html" in data:
        prod.description_html = data["description_html"]
    await session.commit()
    # audit description change
    try:
        session.add(
            AuditLog(
                action="product_update",
                table="products",
                entity_id=product_id,
                meta={"fields": list(data.keys()), "desc_len_old": (len(old_desc or "") if old_desc is not None else None), "desc_len_new": (len(prod.description_html or "") if prod.description_html is not None else None)},
                user_id=sess.user.id if sess and sess.user else None,
                ip=(request.client.host if request and request.client else None),
            )
        )
        await session.commit()
    except Exception:
        pass
    return {"status": "ok"}


@router.get(
    "/products/{product_id}/audit-logs",
    dependencies=[Depends(require_roles("colaborador", "admin"))],
)
async def product_audit_logs(product_id: int, session: AsyncSession = Depends(get_session), limit: int = Query(50, ge=1, le=500)) -> dict:
    rows = (await session.execute(
        select(AuditLog)
        .where(AuditLog.table == "products", AuditLog.entity_id == product_id)
        .order_by(AuditLog.created_at.desc())
        .limit(limit)
    )).scalars().all()
    items = [
        {
            "action": r.action,
            "created_at": r.created_at.isoformat() if getattr(r, "created_at", None) else None,
            "meta": r.meta or {},
        }
        for r in rows
    ]
    return {"items": items}


@router.delete(
    "/products",
    dependencies=[Depends(require_csrf), Depends(require_roles("colaborador", "admin"))],
)
async def delete_products(payload: ProductsDeleteRequest, session: AsyncSession = Depends(get_session), request: Request = None, sess: SessionData = Depends(current_session)) -> dict:
    if not payload.ids:
        raise HTTPException(status_code=400, detail="ids requerido")
    # Limitar tamaño lote
    if len(payload.ids) > 200:
        raise HTTPException(status_code=400, detail="máx 200 ids por solicitud")
    # Borrado en cascada por constraints (ondelete=CASCADE en varias FK). Usamos delete por id.
    deleted = 0
    for pid in payload.ids:
        prod = await session.get(Product, pid)
        if prod:
            await session.delete(prod)
            deleted += 1
    await session.commit()
    # audit (no detallamos todos para no inflar tabla; registramos lote)
    try:
        session.add(
            AuditLog(
                action="products_delete_bulk",
                table="products",
                entity_id=None,
                meta={"count": deleted, "requested": len(payload.ids)},
                user_id=sess.user.id if sess and sess.user else None,
                ip=(request.client.host if request and request.client else None),
            )
        )
        await session.commit()
    except Exception:
        pass
    return {"requested": len(payload.ids), "deleted": deleted}


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
