"""Endpoints para importar listas de precios de proveedores."""

from fastapi import APIRouter, UploadFile, File, Form, HTTPException, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from io import BytesIO
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

router = APIRouter()


async def _upsert_category(db: AsyncSession, name: str) -> Category:
    name = name.strip()
    res = await db.execute(select(Category).where(Category.name == name))
    cat = res.scalar_one_or_none()
    if not cat:
        cat = Category(name=name)
        db.add(cat)
        await db.flush()
    return cat


async def _upsert_product(db: AsyncSession, code: str, title: str, category: Category) -> Product:
    res = await db.execute(select(Product).where(Product.sku_root == code))
    prod = res.scalar_one_or_none()
    if not prod:
        prod = Product(sku_root=code, title=title, category_id=category.id)
        db.add(prod)
        await db.flush()
    return prod


async def _upsert_supplier_product(db: AsyncSession, supplier_id: int, code: str, title: str, category: Category, product: Product) -> None:
    res = await db.execute(
        select(SupplierProduct).where(
            SupplierProduct.supplier_id == supplier_id,
            SupplierProduct.supplier_product_id == code,
        )
    )
    sp = res.scalar_one_or_none()
    if not sp:
        sp = SupplierProduct(
            supplier_id=supplier_id,
            supplier_product_id=code,
            title=title,
            category_level_1=category.name,
            internal_product_id=product.id,
        )
        db.add(sp)
    else:
        sp.title = title
        sp.category_level_1 = category.name
        sp.internal_product_id = product.id
    await db.flush()


@router.post("/suppliers/{supplier_id}/price-list/upload")
async def upload_price_list(
    supplier_id: int,
    file: UploadFile = File(...),
    dry_run: bool = Form(True),
    db: AsyncSession = Depends(get_session),
):
    ext = (file.filename or "").lower()
    content = await file.read()
    try:
        if ext.endswith(".xlsx"):
            df = pd.read_excel(BytesIO(content))
        elif ext.endswith(".csv"):
            df = pd.read_csv(BytesIO(content))
        else:
            raise HTTPException(status_code=400, detail="Formato no soportado. Use .xlsx o .csv")
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Error leyendo archivo: {e}")

    required = ["codigo", "nombre", "categoria", "precio"]
    lower_cols = [c.lower() for c in df.columns]
    missing = [c for c in required if c not in lower_cols]
    if missing:
        raise HTTPException(status_code=400, detail=f"Columnas faltantes: {missing}")

    rows = []
    for idx, row in df.iterrows():
        data = {
            "codigo": str(row[lower_cols.index("codigo")]).strip(),
            "nombre": str(row[lower_cols.index("nombre")]).strip(),
            "categoria": str(row[lower_cols.index("categoria")]).strip(),
            "precio": float(row[lower_cols.index("precio")]),
        }
        rows.append((idx, data))

    job = ImportJob(supplier_id=supplier_id, filename=file.filename or "", status="DRY_RUN")
    db.add(job)
    await db.flush()

    for idx, data in rows:
        db.add(
            ImportJobRow(
                job_id=job.id,
                row_index=int(idx),
                status="ok",
                error=None,
                row_json_normalized=data,
            )
        )

    summary = {"total_rows": len(rows)}
    job.summary_json = summary

    if not dry_run:
        for _, data in rows:
            cat = await _upsert_category(db, data["categoria"])
            prod = await _upsert_product(db, data["codigo"], data["nombre"], cat)
            await _upsert_supplier_product(db, supplier_id, data["codigo"], data["nombre"], cat, prod)
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
        cat = await _upsert_category(db, data["categoria"])
        counts["categories"] += 1
        prod = await _upsert_product(db, data["codigo"], data["nombre"], cat)
        counts["products"] += 1
        await _upsert_supplier_product(db, job.supplier_id, data["codigo"], data["nombre"], cat, prod)
        counts["supplier_products"] += 1
    job.status = "COMMITTED"
    await db.commit()
    return counts
