# NG-HEADER: Nombre de archivo: products_ex.py
# NG-HEADER: Ubicación: services/routers/products_ex.py
# NG-HEADER: Descripción: Pendiente de descripción
# NG-HEADER: Lineamientos: Ver AGENTS.md
from __future__ import annotations

from decimal import Decimal
from typing import Literal, Annotated

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from db.models import (
    AuditLog,
    CanonicalProduct,
    PriceHistory,
    ProductEquivalence,
    Supplier,
    SupplierProduct,
    UserPreference,
)
from db.session import get_session
from services.auth import current_session, require_csrf, require_roles, SessionData

router = APIRouter(prefix="/products-ex", tags=["catalog"])


class UpdateSalePriceIn(BaseModel):
    sale_price: Annotated[Decimal, Field(gt=0, max_digits=12, decimal_places=2)]
    note: str | None = None


class UpdateBuyPriceIn(BaseModel):
    buy_price: Annotated[Decimal, Field(gt=0, max_digits=12, decimal_places=2)]
    note: str | None = None

class UpdateSupplierSalePriceIn(BaseModel):
    sale_price: Annotated[Decimal, Field(gt=0, max_digits=12, decimal_places=2)]
    note: str | None = None


class BulkSalePriceIn(BaseModel):
    product_ids: list[int]
    mode: Literal["set", "inc", "dec", "inc_pct", "dec_pct"]
    value: Annotated[Decimal, Field(gt=0, max_digits=12, decimal_places=4)]
    note: str | None = None


def _client_ip(req: Request) -> str | None:
    xff = req.headers.get("x-forwarded-for")
    if xff:
        return xff.split(",")[0].strip()
    client = req.client
    return client.host if client else None


@router.patch(
    "/products/{product_id}/sale-price",
    dependencies=[Depends(require_csrf), Depends(require_roles("colaborador", "admin"))],
)
async def update_sale_price(
    product_id: int,
    data: UpdateSalePriceIn,
    request: Request,
    session_data: SessionData = Depends(current_session),
    db: AsyncSession = Depends(get_session),
):
    cp = await db.get(CanonicalProduct, product_id)
    if not cp:
        raise HTTPException(status_code=404, detail="Producto canónico no encontrado")
    old = Decimal(cp.sale_price or 0)
    new = Decimal(data.sale_price)
    cp.sale_price = new
    db.add(cp)
    db.add(
        PriceHistory(
            entity_type="canonical",
            entity_id=product_id,
            price_old=old,
            price_new=new,
            note=data.note,
            user_id=session_data.user.id if session_data.user else None,
            ip=_client_ip(request),
        )
    )
    db.add(
        AuditLog(
            action="update",
            table="canonical_products",
            entity_id=product_id,
            meta={"field": "sale_price", "old": str(old), "new": str(new), "note": data.note},
            user_id=session_data.user.id if session_data.user else None,
            ip=_client_ip(request),
        )
    )
    await db.commit()
    await db.refresh(cp)
    return {"id": cp.id, "sale_price": float(cp.sale_price) if cp.sale_price is not None else None}


@router.patch(
    "/supplier-items/{supplier_item_id}/buy-price",
    dependencies=[Depends(require_csrf), Depends(require_roles("colaborador", "admin"))],
)
async def update_buy_price(
    supplier_item_id: int,
    data: UpdateBuyPriceIn,
    request: Request,
    session_data: SessionData = Depends(current_session),
    db: AsyncSession = Depends(get_session),
):
    sp = await db.get(SupplierProduct, supplier_item_id)
    if not sp:
        raise HTTPException(status_code=404, detail="Oferta de proveedor no encontrada")
    old = Decimal(sp.current_purchase_price or 0)
    new = Decimal(data.buy_price)
    sp.current_purchase_price = new
    # Si no hay precio de venta cargado aún, por defecto igualar a compra
    if getattr(sp, "current_sale_price", None) is None:
        sp.current_sale_price = new
    db.add(sp)
    db.add(
        PriceHistory(
            entity_type="supplier",
            entity_id=supplier_item_id,
            price_old=old,
            price_new=new,
            note=data.note,
            user_id=session_data.user.id if session_data.user else None,
            ip=_client_ip(request),
        )
    )
    db.add(
        AuditLog(
            action="update",
            table="supplier_products",
            entity_id=supplier_item_id,
            meta={"field": "current_purchase_price", "old": str(old), "new": str(new), "note": data.note},
            user_id=session_data.user.id if session_data.user else None,
            ip=_client_ip(request),
        )
    )
    await db.commit()
    await db.refresh(sp)
    return {"id": sp.id, "buy_price": float(sp.current_purchase_price) if sp.current_purchase_price is not None else None}


@router.patch(
    "/supplier-items/{supplier_item_id}/sale-price",
    dependencies=[Depends(require_csrf), Depends(require_roles("colaborador", "admin"))],
)
async def update_supplier_sale_price(
    supplier_item_id: int,
    data: UpdateSupplierSalePriceIn,
    request: Request,
    session_data: SessionData = Depends(current_session),
    db: AsyncSession = Depends(get_session),
):
    """Actualiza el precio de venta a nivel SupplierProduct (cuando no hay canónico).

    Registra PriceHistory con entity_type="supplier" y AuditLog.
    """
    sp = await db.get(SupplierProduct, supplier_item_id)
    if not sp:
        raise HTTPException(status_code=404, detail="Oferta de proveedor no encontrada")
    old = Decimal(sp.current_sale_price or 0)
    new = Decimal(data.sale_price)
    sp.current_sale_price = new
    db.add(sp)
    db.add(
        PriceHistory(
            entity_type="supplier",
            entity_id=supplier_item_id,
            price_old=old,
            price_new=new,
            note=data.note,
            user_id=session_data.user.id if session_data.user else None,
            ip=_client_ip(request),
        )
    )
    db.add(
        AuditLog(
            action="update",
            table="supplier_products",
            entity_id=supplier_item_id,
            meta={"field": "current_sale_price", "old": str(old), "new": str(new), "note": data.note},
            user_id=session_data.user.id if session_data.user else None,
            ip=_client_ip(request),
        )
    )
    await db.commit()
    await db.refresh(sp)
    return {"id": sp.id, "sale_price": float(sp.current_sale_price) if sp.current_sale_price is not None else None}


class FillMissingSupplierSaleIn(BaseModel):
    supplier_id: int | None = None


@router.post(
    "/supplier-items/fill-missing-sale",
    dependencies=[Depends(require_csrf), Depends(require_roles("colaborador", "admin"))],
)
async def fill_missing_supplier_sale(
    body: FillMissingSupplierSaleIn,
    request: Request,
    session_data: SessionData = Depends(current_session),
    db: AsyncSession = Depends(get_session),
):
    """Completa precios de venta faltantes a nivel SupplierProduct con el valor de compra actual.

    - Si `supplier_id` viene en el body, limita el alcance a ese proveedor.
    - No genera PriceHistory (se considera un backfill de default), pero registra AuditLog.
    """
    q = select(SupplierProduct).where(SupplierProduct.current_sale_price.is_(None))
    if body.supplier_id:
        q = q.where(SupplierProduct.supplier_id == body.supplier_id)
    q = q.where(SupplierProduct.current_purchase_price.is_not(None))
    rows = (await db.execute(q)).scalars().all()
    updated = 0
    for sp in rows:
        sp.current_sale_price = sp.current_purchase_price
        db.add(sp)
        updated += 1
    if updated:
        await db.commit()
    db.add(
        AuditLog(
            action="supplier_items_fill_missing_sale",
            table="supplier_products",
            entity_id=None,
            meta={
                "updated": updated,
                "scope_supplier_id": body.supplier_id,
            },
            user_id=session_data.user.id if session_data.user else None,
            ip=_client_ip(request),
        )
    )
    await db.commit()
    return {"updated": updated}


# ------------------------------- Diagnóstico -------------------------------
class SupplierItemDiag(BaseModel):
    id: int
    supplier_id: int
    supplier_sku: str | None
    internal_product_id: int | None
    current_purchase_price: float | None
    current_sale_price: float | None
    sale_missing: bool


@router.get(
    "/diagnostics/supplier-item/{supplier_item_id}",
    dependencies=[Depends(require_roles("colaborador", "admin"))],
)
async def diag_supplier_item(
    supplier_item_id: int,
    db: AsyncSession = Depends(get_session),
):
    sp = await db.get(SupplierProduct, supplier_item_id)
    if not sp:
        raise HTTPException(status_code=404, detail="Oferta de proveedor no encontrada")
    return SupplierItemDiag(
        id=sp.id,
        supplier_id=sp.supplier_id,
        supplier_sku=sp.supplier_product_id,
        internal_product_id=sp.internal_product_id,
        current_purchase_price=float(sp.current_purchase_price) if sp.current_purchase_price is not None else None,
        current_sale_price=float(sp.current_sale_price) if sp.current_sale_price is not None else None,
        sale_missing=(sp.current_sale_price is None),
    )


class MissingSaleSummary(BaseModel):
    count: int
    sample_ids: list[int]


@router.get(
    "/diagnostics/missing-sale",
    dependencies=[Depends(require_roles("colaborador", "admin"))],
)
async def diag_missing_sale(
    supplier_id: int | None = None,
    limit: int = 20,
    db: AsyncSession = Depends(get_session),
):
    q = select(SupplierProduct.id).where(SupplierProduct.current_sale_price.is_(None))
    if supplier_id:
        q = q.where(SupplierProduct.supplier_id == supplier_id)
    all_ids = (await db.execute(q)).scalars().all()
    return MissingSaleSummary(count=len(all_ids), sample_ids=list(map(int, all_ids[: max(0, min(limit, 100))])))


@router.post(
    "/diagnostics/supplier-item/{supplier_item_id}/clear-sale",
    dependencies=[Depends(require_roles("colaborador", "admin"))],
)
async def diag_clear_supplier_sale(
    supplier_item_id: int,
    db: AsyncSession = Depends(get_session),
):
    sp = await db.get(SupplierProduct, supplier_item_id)
    if not sp:
        raise HTTPException(status_code=404, detail="Oferta de proveedor no encontrada")
    sp.current_sale_price = None
    db.add(sp)
    await db.commit()
    return {"id": sp.id, "current_sale_price": None}


@router.post(
    "/products/bulk-sale-price",
    dependencies=[Depends(require_csrf), Depends(require_roles("colaborador", "admin"))],
)
async def bulk_sale_price(
    body: BulkSalePriceIn,
    request: Request,
    session_data: SessionData = Depends(current_session),
    db: AsyncSession = Depends(get_session),
):
    updated = 0
    for pid in body.product_ids:
        cp = await db.get(CanonicalProduct, pid)
        if not cp:
            continue
        old = Decimal(cp.sale_price or 0)
        val = Decimal(str(body.value))
        if body.mode == "set":
            new = val
        elif body.mode == "inc":
            new = old + val
        elif body.mode == "dec":
            new = max(Decimal("0.00"), old - val)
        elif body.mode == "inc_pct":
            new = (old * (Decimal("1.0") + val / Decimal("100"))).quantize(Decimal("0.01"))
        else:  # dec_pct
            new = (old * (Decimal("1.0") - val / Decimal("100"))).quantize(Decimal("0.01"))
        cp.sale_price = new
        db.add(cp)
        db.add(
            PriceHistory(
                entity_type="canonical",
                entity_id=pid,
                price_old=old,
                price_new=new,
                note=body.note,
                user_id=session_data.user.id if session_data.user else None,
                ip=_client_ip(request),
            )
        )
        updated += 1
    db.add(
        AuditLog(
            action="bulk_update",
            table="canonical_products",
            entity_id=None,
            meta={"count": updated, "mode": body.mode, "value": str(body.value), "ids": body.product_ids},
            user_id=session_data.user.id if session_data.user else None,
            ip=_client_ip(request),
        )
    )
    await db.commit()
    return {"updated": updated}


@router.get(
    "/products/{product_id}/offerings",
    dependencies=[Depends(require_roles("cliente", "proveedor", "colaborador", "admin"))],
)
async def product_offerings(product_id: int, db: AsyncSession = Depends(get_session)):
    q = (
        select(SupplierProduct, Supplier)
        .join(ProductEquivalence, ProductEquivalence.supplier_product_id == SupplierProduct.id)
        .join(Supplier, Supplier.id == SupplierProduct.supplier_id)
        .where(ProductEquivalence.canonical_product_id == product_id)
        .order_by(SupplierProduct.current_purchase_price.asc().nulls_last())
    )
    result = await db.execute(q)
    rows = result.all()
    return [
        {
            "supplier_item_id": sp.id,
            "supplier_name": sup.name,
            "supplier_sku": sp.supplier_product_id,
            "buy_price": float(sp.current_purchase_price) if sp.current_purchase_price is not None else None,
            "updated_at": sp.last_seen_at.isoformat() if sp.last_seen_at else None,
        }
        for sp, sup in rows
    ]


@router.get(
    "/products/internal/{product_id}/offerings",
    dependencies=[Depends(require_roles("cliente", "proveedor", "colaborador", "admin"))],
)
async def product_offerings_internal(product_id: int, db: AsyncSession = Depends(get_session)):
    q = (
        select(SupplierProduct, Supplier)
        .join(Supplier, Supplier.id == SupplierProduct.supplier_id)
        .where(SupplierProduct.internal_product_id == product_id)
        .order_by(SupplierProduct.current_purchase_price.asc().nulls_last())
    )
    result = await db.execute(q)
    rows = result.all()
    return [
        {
            "supplier_item_id": sp.id,
            "supplier_name": sup.name,
            "supplier_sku": sp.supplier_product_id,
            "buy_price": float(sp.current_purchase_price) if sp.current_purchase_price is not None else None,
            "updated_at": sp.last_seen_at.isoformat() if sp.last_seen_at else None,
        }
        for sp, sup in rows
    ]


class TablePrefs(BaseModel):
    columnOrder: list[str] | None = None
    columnVisibility: dict[str, bool] | None = None
    columnWidths: dict[str, int] | None = None


SCOPE_PRODUCTS = "products_table"
SCOPE_PRODUCT_DETAIL = "product_detail_style"


@router.get("/users/me/preferences/products-table")
async def get_prefs(session_data: SessionData = Depends(current_session), db: AsyncSession = Depends(get_session)):
    if not session_data.user:
        return {}
    row = await db.scalar(select(UserPreference).where(UserPreference.user_id == session_data.user.id, UserPreference.scope == SCOPE_PRODUCTS))
    return row.data if row else {}


@router.put("/users/me/preferences/products-table", dependencies=[Depends(require_csrf)])
async def put_prefs(data: TablePrefs, session_data: SessionData = Depends(current_session), db: AsyncSession = Depends(get_session)):
    if not session_data.user:
        raise HTTPException(status_code=401, detail="Auth required")
    row = await db.scalar(select(UserPreference).where(UserPreference.user_id == session_data.user.id, UserPreference.scope == SCOPE_PRODUCTS))
    payload = data.model_dump(exclude_none=True)
    if row:
        row.data = payload
    else:
        row = UserPreference(user_id=session_data.user.id, scope=SCOPE_PRODUCTS, data=payload)
        db.add(row)
    await db.commit()
    return {"status": "ok"}


class ProductDetailStyle(BaseModel):
    style: Literal["default", "minimalDark"]


@router.get("/users/me/preferences/product-detail")
async def get_product_detail_pref(session_data: SessionData = Depends(current_session), db: AsyncSession = Depends(get_session)):
    """Devuelve la preferencia de estilo de ficha de producto del usuario actual."""
    if not session_data.user:
        return {}
    row = await db.scalar(select(UserPreference).where(UserPreference.user_id == session_data.user.id, UserPreference.scope == SCOPE_PRODUCT_DETAIL))
    return row.data if row else {}


@router.put("/users/me/preferences/product-detail", dependencies=[Depends(require_csrf)])
async def put_product_detail_pref(data: ProductDetailStyle, session_data: SessionData = Depends(current_session), db: AsyncSession = Depends(get_session)):
    """Guarda la preferencia de estilo de ficha de producto para el usuario actual."""
    if not session_data.user:
        raise HTTPException(status_code=401, detail="Auth required")
    row = await db.scalar(select(UserPreference).where(UserPreference.user_id == session_data.user.id, UserPreference.scope == SCOPE_PRODUCT_DETAIL))
    payload = data.model_dump()
    if row:
        row.data = payload
    else:
        row = UserPreference(user_id=session_data.user.id, scope=SCOPE_PRODUCT_DETAIL, data=payload)
        db.add(row)
    await db.commit()
    return {"status": "ok"}
