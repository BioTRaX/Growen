"""Endpoints para importar listas de precios de proveedores."""

from fastapi import APIRouter, UploadFile, File, Form, HTTPException, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from io import BytesIO
from datetime import datetime, date
import pandas as pd

from db.models import (
    ImportJob,
    ImportJobRow,
    Supplier,
    Category,
    Product,
    SupplierProduct,
    SupplierPriceHistory,
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

    # Preparar estructuras para deduplicar y comparar contra la base
    seen_codes: set[str] = set()
    codes = [r.get("codigo") for r in parsed_rows if r.get("codigo")]
    existing_map: dict[str, SupplierProduct] = {}
    if codes:
        res = await db.execute(
            select(SupplierProduct).where(
                SupplierProduct.supplier_id == supplier_id,
                SupplierProduct.supplier_product_id.in_(codes),
            )
        )
        existing_map = {sp.supplier_product_id: sp for sp in res.scalars()}

    kpis = {
        "total": len(parsed_rows),
        "errors": 0,
        "duplicates_in_file": 0,
        "unchanged": 0,
        "new": 0,
        "changed": 0,
    }

    for idx, data in enumerate(parsed_rows):
        code = data.get("codigo")
        purchase = data.get("precio_compra")
        sale = data.get("precio_venta")
        status = "ok"
        error = None

        if not code or code in seen_codes:
            status = "duplicate_in_file"
            error = "Código duplicado en archivo"
            kpis["duplicates_in_file"] += 1
        else:
            seen_codes.add(code)
            if purchase in (None, 0) or sale in (None, 0):
                status = "error"
                error = "Precios inválidos"
                kpis["errors"] += 1
            else:
                sp = existing_map.get(code)
                if sp:
                    prev_p = float(sp.current_purchase_price or 0)
                    prev_s = float(sp.current_sale_price or 0)
                    delta_p = round(float(purchase) - prev_p, 2)
                    delta_s = round(float(sale) - prev_s, 2)
                    data["delta_compra"] = delta_p
                    data["delta_venta"] = delta_s
                    data["delta_pct"] = (
                        round(delta_s / prev_s * 100, 2) if prev_s else None
                    )
                    if delta_p == 0 and delta_s == 0:
                        status = "unchanged"
                        kpis["unchanged"] += 1
                    else:
                        status = "changed"
                        kpis["changed"] += 1
                else:
                    status = "new"
                    kpis["new"] += 1

        db.add(
            ImportJobRow(
                job_id=job.id,
                row_index=int(idx),
                status=status,
                error=error,
                row_json_normalized=data,
            )
        )

    job.summary_json = kpis

    await db.commit()
    return {"job_id": job.id, "summary": kpis, "kpis": kpis}


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

    result = {
        "inserted": 0,
        "updated": 0,
        "unchanged": 0,
        "skipped_duplicates": 0,
        "errors": 0,
        "price_changes": 0,
    }

    for r in rows:
        data = r.row_json_normalized
        if r.status == "error":
            result["errors"] += 1
            continue
        if r.status == "duplicate_in_file":
            result["skipped_duplicates"] += 1
            continue
        if r.status == "unchanged":
            result["unchanged"] += 1
            continue

        cat = await _get_or_create_category_path(db, data["categoria_path"])
        prod = await _upsert_product(db, data["codigo"], data["nombre"], cat)

        stmt = select(SupplierProduct).where(
            SupplierProduct.supplier_id == job.supplier_id,
            SupplierProduct.supplier_product_id == data["codigo"],
        )
        sp = (await db.execute(stmt)).scalar_one_or_none()
        if not sp:
            sp = SupplierProduct(
                supplier_id=job.supplier_id,
                supplier_product_id=data["codigo"],
            )
            db.add(sp)
            result["inserted"] += 1
        else:
            result["updated"] += 1

        parts = [
            p.strip() for p in data.get("categoria_path", "").split(">") if p.strip()
        ]
        sp.title = data["nombre"]
        sp.category_level_1 = parts[0] if len(parts) > 0 else None
        sp.category_level_2 = parts[1] if len(parts) > 1 else None
        sp.category_level_3 = parts[2] if len(parts) > 2 else None
        sp.min_purchase_qty = data.get("compra_minima")
        sp.last_seen_at = datetime.utcnow()
        sp.current_purchase_price = data.get("precio_compra")
        sp.current_sale_price = data.get("precio_venta")
        sp.internal_product_id = prod.id

        if r.status == "changed":
            prev_purchase = data.get("precio_compra") - data.get("delta_compra", 0)
            prev_sale = data.get("precio_venta") - data.get("delta_venta", 0)
            delta_purchase_pct = (
                (data.get("delta_compra", 0) / prev_purchase * 100)
                if prev_purchase
                else None
            )
            delta_sale_pct = (
                (data.get("delta_venta", 0) / prev_sale * 100)
                if prev_sale
                else None
            )
            db.add(
                SupplierPriceHistory(
                    supplier_product_fk=sp.id,
                    file_fk=None,
                    as_of_date=date.today(),
                    purchase_price=data.get("precio_compra"),
                    sale_price=data.get("precio_venta"),
                    delta_purchase_pct=delta_purchase_pct,
                    delta_sale_pct=delta_sale_pct,
                )
            )
            result["price_changes"] += 1

    job.status = "COMMITTED"
    await db.commit()
    return result
