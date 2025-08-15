"""Endpoints para importar listas de precios de proveedores."""

from fastapi import APIRouter, UploadFile, File, Form, HTTPException, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from io import BytesIO
from datetime import datetime
import pandas as pd

from db.models import (
    ImportJob,
    ImportJobRow,
    Supplier,
    Category,
    Product,
    SupplierProduct,
)
from db.session import get_session
from services.suppliers.parsers import SUPPLIER_PARSERS

router = APIRouter()


async def _get_or_create_category_path(db: AsyncSession, path: str) -> Category:
    """Crea la jerarquía de categorías completa y devuelve la última."""
    parent_id: int | None = None
    parent: Category | None = None
    for name in [p.strip() for p in path.split(">") if p.strip()]:
        stmt = select(Category).where(
            Category.name == name, Category.parent_id == parent_id
        )
        res = await db.execute(stmt)
        cat = res.scalar_one_or_none()
        if not cat:
            cat = Category(name=name, parent_id=parent_id)
            db.add(cat)
            await db.flush()
        parent_id = cat.id
        parent = cat
    if not parent:
        raise ValueError("category_path vacío")
    return parent


async def _upsert_product(
    db: AsyncSession, code: str, title: str, category: Category
) -> Product:
    res = await db.execute(select(Product).where(Product.sku_root == code))
    prod = res.scalar_one_or_none()
    if not prod:
        prod = Product(sku_root=code, title=title, category_id=category.id)
        db.add(prod)
        await db.flush()
    else:
        prod.title = title
        prod.category_id = category.id
    return prod


async def _upsert_supplier_product(
    db: AsyncSession, supplier_id: int, data: dict, product: Product
) -> None:
    code = data["codigo"]
    parts = [p.strip() for p in data.get("categoria_path", "").split(">") if p.strip()]
    stmt = select(SupplierProduct).where(
        SupplierProduct.supplier_id == supplier_id,
        SupplierProduct.supplier_product_id == code,
    )
    res = await db.execute(stmt)
    sp = res.scalar_one_or_none()
    if not sp:
        sp = SupplierProduct(
            supplier_id=supplier_id,
            supplier_product_id=code,
        )
        db.add(sp)
    sp.title = data["nombre"]
    sp.category_level_1 = parts[0] if len(parts) > 0 else None
    sp.category_level_2 = parts[1] if len(parts) > 1 else None
    sp.category_level_3 = parts[2] if len(parts) > 2 else None
    sp.min_purchase_qty = data.get("compra_minima")
    sp.current_purchase_price = data.get("precio_compra")
    sp.current_sale_price = data.get("precio_venta")
    sp.last_seen_at = datetime.utcnow()
    sp.internal_product_id = product.id
    await db.flush()


@router.post("/suppliers/{supplier_id}/price-list/upload")
async def upload_price_list(
    supplier_id: int,
    file: UploadFile = File(...),
    dry_run: bool = Form(True),
    db: AsyncSession = Depends(get_session),
):
    supplier = await db.get(Supplier, supplier_id)
    if not supplier:
        raise HTTPException(status_code=404, detail="Proveedor no encontrado")

    parser = SUPPLIER_PARSERS.get(supplier.slug)
    if not parser:
        raise HTTPException(status_code=400, detail="Proveedor no soportado (parser faltante)")

    ext = (file.filename or "").lower()
    content = await file.read()
    try:
        if ext.endswith(".xlsx"):
            df = pd.read_excel(BytesIO(content))
        elif ext.endswith(".csv"):
            df = pd.read_csv(BytesIO(content))
        else:
            raise HTTPException(
                status_code=400,
                detail="Formato no soportado. Use .xlsx o .csv",
            )
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Error leyendo archivo: {e}")

    try:
        parsed_rows = parser.parse_df(df)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

    job = ImportJob(
        supplier_id=supplier_id, filename=file.filename or "", status="DRY_RUN"
    )
    db.add(job)
    await db.flush()

    for idx, data in enumerate(parsed_rows):
        db.add(
            ImportJobRow(
                job_id=job.id,
                row_index=int(idx),
                status="ok",
                error=None,
                row_json_normalized=data,
            )
        )

    summary = {"total_rows": len(parsed_rows)}
    job.summary_json = summary

    if not dry_run:
        for data in parsed_rows:
            cat = await _get_or_create_category_path(db, data["categoria_path"])
            prod = await _upsert_product(db, data["codigo"], data["nombre"], cat)
            await _upsert_supplier_product(db, supplier_id, data, prod)
        job.status = "COMMITTED"

    await db.commit()
    return {"job_id": job.id, "summary": summary}


@router.get("/imports/{job_id}")
async def get_import(
    job_id: int,
    limit: int = Query(50, ge=1, le=500),
    db: AsyncSession = Depends(get_session),
):
    """Devuelve el resumen del job y las primeras ``limit`` filas."""
    res = await db.execute(select(ImportJob).where(ImportJob.id == job_id))
    job = res.scalar_one_or_none()
    if not job:
        raise HTTPException(status_code=404, detail="Job no encontrado")
    res = await db.execute(
        select(ImportJobRow)
        .where(ImportJobRow.job_id == job_id)
        .order_by(ImportJobRow.row_index)
        .limit(limit)
    )
    rows = [
        {
            "row_index": r.row_index,
            "status": r.status,
            "error": r.error,
            "data": r.row_json_normalized,
        }
        for r in res.scalars()
    ]
    return {"job_id": job.id, "status": job.status, "summary": job.summary_json, "rows": rows}


@router.post("/imports/{job_id}/commit")
async def commit_import(job_id: int, db: AsyncSession = Depends(get_session)):
    res = await db.execute(select(ImportJob).where(ImportJob.id == job_id))
    job = res.scalar_one_or_none()
    if not job:
        raise HTTPException(status_code=404, detail="Job no encontrado")
    if job.status != "DRY_RUN":
        raise HTTPException(status_code=400, detail="Job ya aplicado")
    res = await db.execute(select(ImportJobRow).where(ImportJobRow.job_id == job_id))
    rows = res.scalars().all()
    counts = {"categories": 0, "products": 0, "supplier_products": 0}
    for r in rows:
        data = r.row_json_normalized
        cat = await _get_or_create_category_path(db, data["categoria_path"])
        counts["categories"] += 1
        prod = await _upsert_product(db, data["codigo"], data["nombre"], cat)
        counts["products"] += 1
        await _upsert_supplier_product(db, job.supplier_id, data, prod)
        counts["supplier_products"] += 1
    job.status = "COMMITTED"
    await db.commit()
    return counts
