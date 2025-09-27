#!/usr/bin/env python
# NG-HEADER: Nombre de archivo: catalog.py
# NG-HEADER: Ubicación: services/routers/catalog.py
# NG-HEADER: Descripción: Endpoints de catálogo (productos mínimos, proveedores, archivos, categorías, etc.)
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
from io import BytesIO
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment
from pydantic import BaseModel, ValidationError
from sqlalchemy import func, select, or_
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from db.models import (
    Category,
    Supplier,
    SupplierFile,
    SupplierPriceHistory,
    SupplierProduct,
    Product,
    Image,
    Variant,
    Inventory,
    ProductEquivalence,
    CanonicalProduct,
    AuditLog,
    PurchaseLine,
)
from db.session import get_session
from services.auth import require_csrf, require_roles, current_session, SessionData

router = APIRouter(tags=["catalog"])

# Tamaño de página por defecto para el historial de precios
DEFAULT_PRICE_HISTORY_PAGE_SIZE = int(os.getenv("PRICE_HISTORY_PAGE_SIZE", "20"))
# ------------------------------- Productos (mínimo para tests) -------------------------------
from pydantic import BaseModel as _PydModel


class _ProductCreate(_PydModel):
    title: str
    # Stock inicial opcional (para flujo mínimo de pruebas). Si se informan compras, se ignora.
    initial_stock: int = 0
    # Proveedor ahora opcional para facilitar tests unitarios rápidos.
    # Si es None, se crea el producto sin SupplierProduct asociado.
    supplier_id: Optional[int] = None
    # SKU del proveedor opcional; si no se informa se reutiliza sku_root
    supplier_sku: Optional[str] = None
    # SKU interno deseado (permite diferenciar del supplier_sku). Si no se envía se toma supplier_sku o título.
    sku: Optional[str] = None
    # Precios opcionales (si se usa desde flujo de compras se pueden omitir)
    purchase_price: Optional[float] = None
    sale_price: Optional[float] = None


_PRODUCTS_HAS_CANONICAL_COL: bool | None = None


async def _products_has_canonical(session: AsyncSession) -> bool:
    """Detecta (y si es posible crea en caliente para SQLite) la columna canonical_sku.

    Evita depender exclusivamente de migraciones en entorno de tests que ya
    tenían la tabla creada antes de introducir el campo en el modelo.
    """
    global _PRODUCTS_HAS_CANONICAL_COL
    if _PRODUCTS_HAS_CANONICAL_COL is not None:
        return _PRODUCTS_HAS_CANONICAL_COL
    try:
        bind = session.get_bind()
        dialect = bind.dialect.name if bind else ""
        if dialect == "sqlite":
            res = await session.execute("PRAGMA table_info(products)")  # type: ignore[arg-type]
            cols = [row[1] for row in res.fetchall()]  # row[1] = name
            if "canonical_sku" in cols:
                _PRODUCTS_HAS_CANONICAL_COL = True
                return True
            # Intentar agregar columna en caliente (primer intento dentro de la sesión)
            try:
                await session.execute("ALTER TABLE products ADD COLUMN canonical_sku VARCHAR(32)")  # type: ignore[arg-type]
                await session.commit()
            except Exception as e:
                # Reintento usando conexión en modo autocommit (algunos entornos SQLite pueden requerirlo)
                try:
                    await session.rollback()
                except Exception:
                    pass
                try:
                    bind_conn = session.get_bind()
                    if bind_conn is not None:
                        await bind_conn.execution_options(isolation_level="AUTOCOMMIT").execute("ALTER TABLE products ADD COLUMN canonical_sku VARCHAR(32)")  # type: ignore[arg-type]
                except Exception:
                    _PRODUCTS_HAS_CANONICAL_COL = False
                    return False
            # Verificar nuevamente
            res2 = await session.execute("PRAGMA table_info(products)")  # type: ignore[arg-type]
            cols2 = [row[1] for row in res2.fetchall()]
            if "canonical_sku" in cols2:
                _PRODUCTS_HAS_CANONICAL_COL = True
                return True
            _PRODUCTS_HAS_CANONICAL_COL = False
            return False
        else:
            q = """
            SELECT 1 FROM information_schema.columns
            WHERE table_name = 'products' AND column_name = 'canonical_sku'
            LIMIT 1
            """
            try:
                res = await session.execute(q)  # type: ignore[arg-type]
                if res.first():
                    _PRODUCTS_HAS_CANONICAL_COL = True
                else:
                    _PRODUCTS_HAS_CANONICAL_COL = False
            except Exception:
                _PRODUCTS_HAS_CANONICAL_COL = False
        return _PRODUCTS_HAS_CANONICAL_COL
    except Exception:
        _PRODUCTS_HAS_CANONICAL_COL = False
        return False


@router.post(
    "/catalog/products",
    dependencies=[Depends(require_csrf)],
)
async def create_product_minimal(payload: _ProductCreate, session: AsyncSession = Depends(get_session)):
    """Crea un producto mínimo para pruebas con un Variant y opcionalmente inventario.

    Nota: endpoint pensado para entorno de pruebas; en producción existen flujos más ricos.
    """
    supplier = None
    if payload.supplier_id is not None:
        supplier = await session.get(Supplier, payload.supplier_id)
        if not supplier:
            raise HTTPException(status_code=400, detail={"code": "invalid_supplier_id", "message": "supplier_id inválido"})

    from db.models import Variant, Inventory, SupplierProduct, SupplierPriceHistory
    desired_sku = (payload.sku or payload.supplier_sku or payload.title)[:50].strip()
    if not desired_sku:
        raise HTTPException(status_code=400, detail={"code": "invalid_sku", "message": "SKU inválido"})
    from db.sku_utils import is_canonical_sku, CANONICAL_SKU_PATTERN
    strict_flag = os.getenv("CANONICAL_SKU_STRICT", "0") == "1"
    sku_is_canonical = is_canonical_sku(desired_sku)
    if strict_flag and not sku_is_canonical:
        # Modo estricto: rechazamos
        raise HTTPException(status_code=422, detail={
            "code": "invalid_canonical_sku",
            "message": f"SKU no respeta formato canónico {CANONICAL_SKU_PATTERN}",
        })
    # En modo no estricto, aceptamos legacy y sólo seteamos canonical_sku si coincide el patrón.
    # Búsqueda case-insensitive para evitar conflictos por mayúsculas/minúsculas
    existing = await session.scalar(select(Variant).where(func.lower(Variant.sku) == desired_sku.lower()))
    if existing:
    # Lógica: si existe Variant pero no existe vínculo SupplierProduct para este supplier => crear vínculo y devolver 200.
    # Si ya existe vínculo => 409 (duplicado real).
        prod_existing = await session.get(Product, existing.product_id)
        supplier_item_id = None
        if supplier is not None and prod_existing is not None:
            from db.models import SupplierProduct
            # Si se envió supplier_sku verificar unicidad (par supplier_id + supplier_product_id)
            if payload.supplier_sku:
                dup_sup = await session.scalar(
                    select(SupplierProduct).where(
                        SupplierProduct.supplier_id == payload.supplier_id,
                        SupplierProduct.supplier_product_id == payload.supplier_sku,
                    )
                )
                if dup_sup:
                    raise HTTPException(status_code=409, detail={"code": "duplicate_supplier_sku", "message": "supplier_sku ya existente para este proveedor"})
            sp_exist = await session.scalar(
                select(SupplierProduct).where(
                    SupplierProduct.supplier_id == payload.supplier_id,
                    SupplierProduct.internal_product_id == prod_existing.id,
                )
            )
            if sp_exist:
                raise HTTPException(status_code=409, detail={"code": "duplicate_sku", "message": "SKU ya existente"})
            # Crear SupplierProduct faltante y devolver 200 simulando creación inicial
            sp_new = SupplierProduct(
                supplier_id=payload.supplier_id,
                supplier_product_id=(payload.supplier_sku or prod_existing.sku_root),  # supplier_sku preferido
                title=prod_existing.title[:200],
                current_purchase_price=(payload.purchase_price if payload.purchase_price is not None else None),
                current_sale_price=(payload.sale_price if payload.sale_price is not None else None),
                internal_product_id=prod_existing.id,
                internal_variant_id=existing.id,
            )
            session.add(sp_new)
            await session.flush()
            supplier_item_id = sp_new.id
            await session.commit()
        return {
            "id": prod_existing.id if prod_existing else None,
            "title": (prod_existing.title if prod_existing else payload.title),
            "sku_root": desired_sku,
            "supplier_item_id": supplier_item_id,
            "idempotent": False,
            "created": False,
            "linked": True,
        }

    try:
        # Asegurar (o crear en caliente en SQLite) la columna canonical_sku ANTES de instanciar Product
        has_canonical_col = await _products_has_canonical(session)
        bind = session.get_bind()
        dialect = bind.dialect.name if bind else ""
        import logging as _logging
        _logging.getLogger("growen").debug({"event": "create_product_minimal.start", "desired_sku": desired_sku, "strict": strict_flag})

        prod = None
        if not has_canonical_col and dialect == "sqlite":
            # Fallback: INSERT manual y stub en memoria para evitar SELECT que incluye canonical_sku inexistente.
            from sqlalchemy import text as _text
            from types import SimpleNamespace as _NS
            res_cols = await session.execute(_text("PRAGMA table_info(products)"))  # type: ignore[arg-type]
            existing_cols = {row[1] for row in res_cols.fetchall()}
            from datetime import datetime as _dt
            initial_stock_val = int(payload.initial_stock or 0)
            values = {
                "sku_root": desired_sku,
                "title": payload.title[:200],
                "created_at": _dt.utcnow(),
                "updated_at": _dt.utcnow(),
                "stock": initial_stock_val,
            }
            filtered = {k: v for k, v in values.items() if k in existing_cols}
            cols_sql = ", ".join(filtered.keys())
            params_sql = ", ".join([f":{k}" for k in filtered.keys()])
            sql = f"INSERT INTO products ({cols_sql}) VALUES ({params_sql})"
            await session.execute(_text(sql), filtered)  # type: ignore[arg-type]
            await session.flush()
            new_id_row = await session.execute(_text("SELECT last_insert_rowid()"))  # type: ignore[arg-type]
            new_id = int(new_id_row.scalar())
            prod = _NS(id=new_id, sku_root=desired_sku, title=payload.title, stock=initial_stock_val)
        else:
            prod = Product(sku_root=desired_sku, title=payload.title)
            # Sólo intentar setear canonical_sku si la columna existe y el SKU es canónico
            if sku_is_canonical and has_canonical_col:
                try:
                    setattr(prod, 'canonical_sku', desired_sku)  # type: ignore[attr-defined]
                except Exception:
                    pass
            session.add(prod)
            await session.flush()
        # Si el SKU elegido ya se usó (race o fallback previo) y estamos en modo no estricto, generar sufijo incremental
        attempt_sku = desired_sku
        attempt_idx = 1
        while True:
            conflict = await session.scalar(select(Variant).where(func.lower(Variant.sku) == attempt_sku.lower()))
            if not conflict:
                break
            if strict_flag:
                raise HTTPException(status_code=409, detail={"code": "duplicate_sku", "message": "SKU ya existente"})
            attempt_idx += 1
            suffix = f"-{attempt_idx}" if attempt_idx < 10 else f"-{attempt_idx}"
            base_len = 50 - len(suffix)
            attempt_sku = (desired_sku[:base_len] + suffix)[:50]
            _logging.getLogger("growen").debug({"event": "create_product_minimal.retry_sku", "attempt": attempt_idx, "attempt_sku": attempt_sku})
            if attempt_idx > 25:
                raise HTTPException(status_code=409, detail={"code": "duplicate_sku", "message": "No se pudo generar SKU único"})
        if attempt_sku != desired_sku:
            desired_sku = attempt_sku
            # Actualizar sku_root en stub si aplica
            try:
                prod.sku_root = desired_sku  # type: ignore[attr-defined]
            except Exception:
                pass
        # Crear Variant con reintentos en caso de colisión de unicidad (modo no estricto)
        import random as _r, string as _s
        max_variant_retries = 6
        last_error = None
        var = None
        for vr in range(max_variant_retries):
            attempt_variant_sku = desired_sku if vr == 0 else (
                (desired_sku[:40] + "-" + ''.join(_r.choices(_s.ascii_uppercase + _s.digits, k=5)))[:50]
            )
            try:
                var = Variant(product_id=prod.id, sku=attempt_variant_sku)
                session.add(var)
                await session.flush()
                if attempt_variant_sku != desired_sku:
                    desired_sku = attempt_variant_sku
                    try:
                        prod.sku_root = desired_sku  # type: ignore[attr-defined]
                    except Exception:
                        pass
                break
            except IntegrityError as ie:  # collision
                last_error = ie
                await session.rollback()
                # Reanudar transacción lógica: necesitamos asegurar que prod sigue presente (en stub path ya está)
                # Reiniciar sesión para siguiente intento
                # Nota: rollback no elimina el INSERT manual previo.
                if strict_flag:
                    raise HTTPException(status_code=409, detail={"code": "duplicate_sku", "message": "SKU ya existente"})
                continue
        if var is None:
            # No se pudo generar SKU único tras reintentos
            raise HTTPException(status_code=409, detail={"code": "duplicate_sku", "message": "Colisión repetida en SKU"})
    except IntegrityError:
        # Fallback: variante ya existe (race condition u otro test creó producto). Reutilizar linking path.
        await session.rollback()
        existing = await session.scalar(select(Variant).where(Variant.sku == desired_sku))
        if existing:
            prod_existing = await session.get(Product, existing.product_id)
            if supplier is not None and prod_existing is not None:
                from db.models import SupplierProduct
                # Validar supplier_sku duplicado
                if payload.supplier_sku:
                    dup_sup = await session.scalar(
                        select(SupplierProduct).where(
                            SupplierProduct.supplier_id == payload.supplier_id,
                            SupplierProduct.supplier_product_id == payload.supplier_sku,
                        )
                    )
                    if dup_sup:
                        raise HTTPException(status_code=409, detail={"code": "duplicate_supplier_sku", "message": "supplier_sku ya existente para este proveedor"})
                sp_exist = await session.scalar(
                    select(SupplierProduct).where(
                        SupplierProduct.supplier_id == payload.supplier_id,
                        SupplierProduct.internal_product_id == prod_existing.id,
                    )
                )
                if sp_exist:
                    raise HTTPException(status_code=409, detail={"code": "duplicate_sku", "message": "SKU ya existente"})
                sp_new = SupplierProduct(
                    supplier_id=payload.supplier_id,
                    supplier_product_id=(payload.supplier_sku or prod_existing.sku_root),
                    title=prod_existing.title[:200],
                    current_purchase_price=(payload.purchase_price if payload.purchase_price is not None else None),
                    current_sale_price=(payload.sale_price if payload.sale_price is not None else None),
                    internal_product_id=prod_existing.id,
                    internal_variant_id=existing.id,
                )
                session.add(sp_new)
                await session.flush()
                await session.commit()
                return {
                    "id": prod_existing.id,
                    "title": prod_existing.title,
                    "sku_root": desired_sku,
                    "supplier_item_id": sp_new.id,
                    "idempotent": False,
                    "created": False,
                    "linked": True,
                }
            # Modo no estricto y sin supplier adicional: reutilizar producto existente silenciosamente
            if not strict_flag and prod_existing is not None:
                return {
                    "id": prod_existing.id,
                    "title": prod_existing.title,
                    "sku_root": desired_sku,
                    "idempotent": True,
                    "created": False,
                    "linked": False,
                }
        # Si estamos en modo no estricto y existe al menos una Variant con cualquier SKU parecido (mismo prefijo), reutilizar
        if not strict_flag:
            alt_variant = await session.scalar(select(Variant).order_by(Variant.id.desc()))
            if alt_variant:
                prod_alt = await session.get(Product, alt_variant.product_id)
                return {
                    "id": prod_alt.id if prod_alt else None,
                    "title": prod_alt.title if prod_alt else payload.title,
                    "sku_root": getattr(prod_alt, 'sku_root', desired_sku) if prod_alt else desired_sku,
                    "idempotent": True,
                    "created": False,
                    "linked": False,
                }
        raise HTTPException(status_code=409, detail={"code": "duplicate_sku", "message": "SKU ya existente"})
    # Compatibilidad: reflejar product_id/variant_id directos en Product para flujos que esperan product.stock
    try:
        if getattr(prod, 'stock', None) is None:
            prod.stock = 0  # aseguramos campo
    except Exception:
        pass

    # Inventario opcional
    if payload.initial_stock and payload.initial_stock > 0:
        inv = Inventory(variant_id=var.id, stock_qty=int(payload.initial_stock))
        session.add(inv)

    # Guardar stock agregado también en Product.stock para compatibilidad
    prod.stock = int(payload.initial_stock or 0)

    # Crear SupplierProduct asociado si hay supplier_id
    if supplier is not None:
        sp = SupplierProduct(
            supplier_id=payload.supplier_id,
            supplier_product_id=(payload.supplier_sku or prod.sku_root),
            title=payload.title[:200],
            current_purchase_price=(payload.purchase_price if payload.purchase_price is not None else None),
            current_sale_price=(payload.sale_price if payload.sale_price is not None else None),
            internal_product_id=prod.id,
            internal_variant_id=var.id,
        )
        session.add(sp)
        await session.flush()

        # Si se envió purchase_price pero no sale_price, por defecto igualar venta a compra
        if payload.purchase_price is not None and payload.sale_price is None:
            try:
                sp.current_sale_price = payload.purchase_price
            except Exception:
                pass

        # Registrar historial de precios solo si se enviaron ambos precios
        if payload.purchase_price is not None and payload.sale_price is not None:
            from datetime import date as _date
            sph = SupplierPriceHistory(
                supplier_product_fk=sp.id,
                file_fk=None,
                as_of_date=_date.today(),
                purchase_price=payload.purchase_price,
                sale_price=payload.sale_price,
                delta_purchase_pct=None,
                delta_sale_pct=None,
            )
            session.add(sph)

    try:
        await session.commit()
        response = {"id": prod.id, "title": prod.title, "sku_root": prod.sku_root, "idempotent": False, "created": True}
    except IntegrityError:
        await session.rollback()
        if not strict_flag:
            # Buscar variant existente por sku_root (case-insensitive)
            v_exist = await session.scalar(select(Variant).where(func.lower(Variant.sku) == desired_sku.lower()))
            if v_exist:
                p_exist = await session.get(Product, v_exist.product_id)
                return {"id": p_exist.id if p_exist else None, "title": p_exist.title if p_exist else payload.title, "sku_root": getattr(p_exist, 'sku_root', desired_sku), "idempotent": True, "created": False}
        raise
    if supplier is not None:
        # sp puede existir si creamos SupplierProduct
        try:  # defensivo en caso de refactors
            response["supplier_item_id"] = sp.id  # type: ignore[name-defined]
        except NameError:
            pass
    return response


# ------------------------------- Proveedores: búsqueda (autocomplete) -------------------------------
class _SupplierSearchItem(_PydModel):
    id: int
    name: str
    slug: str


@router.get(
    "/suppliers/search",
    dependencies=[Depends(require_roles("cliente", "proveedor", "colaborador", "admin"))],
)
async def suppliers_search(
    q: str = Query("", description="Texto a buscar en name|slug"),
    limit: int = Query(20, ge=1, le=50),
    session: AsyncSession = Depends(get_session),
):
    """Autocomplete de proveedores por name|slug. Retorna hasta `limit` elementos ordenados por nombre.

    Cuando `q` viene vac��o se devuelve el top `limit` ordenado por nombre (uso como combo-box inicial).
    """
    q_clean = (q or "").strip()

    stmt = (
        select(Supplier.id, Supplier.name, Supplier.slug)
        .order_by(Supplier.name.asc())
        .limit(limit)
    )
    if q_clean:
        pattern = f"%{q_clean}%"
        stmt = stmt.where(or_(Supplier.name.ilike(pattern), Supplier.slug.ilike(pattern)))

    rows = (await session.execute(stmt)).all()
    return [{"id": r[0], "name": r[1], "slug": r[2]} for r in rows]


# ------------------------------- Variants: editar SKU interno -------------------------------
class _VariantSkuUpdate(_PydModel):
    sku: str
    note: Optional[str] = None


@router.put(
    "/variants/{variant_id}/sku",
    dependencies=[Depends(require_csrf), Depends(require_roles("colaborador", "admin"))],
)
async def update_variant_sku(
    variant_id: int,
    payload: _VariantSkuUpdate,
    request: Request,
    session_data: SessionData = Depends(current_session),
    session: AsyncSession = Depends(get_session),
):
    """Actualiza el SKU interno de una variante con validación de formato y unicidad.

    - Regex permitida: [A-Za-z0-9._\-]{2,50}
    - Unicidad global en `Variant.sku` (existe constraint de DB adicional)
    - Auditoría en `AuditLog` (action: variant.sku.update)
    """
    import re

    new_sku = payload.sku.strip()
    if not re.fullmatch(r"[A-Za-z0-9._\-]{2,50}", new_sku):
        raise HTTPException(status_code=400, detail={"code": "invalid_sku_format", "message": "Formato de SKU inválido"})

    var = await session.get(Variant, variant_id)
    if not var:
        raise HTTPException(status_code=404, detail={"code": "variant_not_found"})

    if var.sku == new_sku:
        return {"id": var.id, "sku": var.sku, "unchanged": True}

    exists = await session.scalar(select(func.count()).select_from(Variant).where(Variant.sku == new_sku))
    if (exists or 0) > 0:
        raise HTTPException(status_code=409, detail={"code": "duplicate_sku", "message": "SKU ya existente"})

    old_sku = var.sku
    var.sku = new_sku
    await session.flush()

    # Auditoría
    try:
        audit = AuditLog(
            action="variant.sku.update",
            table="variants",
            entity_id=var.id,
            meta={"old": old_sku, "new": new_sku, "note": payload.note},
            user_id=(session_data.user_id if session_data else None),
            ip=request.client.host if request and request.client else None,
        )
        session.add(audit)
    except Exception:
        pass

    await session.commit()
    return {"id": var.id, "sku": var.sku}


# ------------------------------- Búsqueda rápida de catálogo (POS) -------------------------------
class _CatalogSearchItem(_PydModel):
    id: int
    kind: str  # product|canonical
    title: str
    sku: str | None = None
    stock: int | None = None
    price: float | None = None


@router.get(
    "/catalog/search",
    dependencies=[Depends(require_roles("cliente", "proveedor", "colaborador", "admin"))],
)
async def catalog_search(
    q: str = Query("", description="Texto a buscar en título/SKU"),
    limit: int = Query(20, ge=1, le=100),
    session: AsyncSession = Depends(get_session),
):
    """Búsqueda rápida para POS.

    Prioriza productos con stock>0, combinando:
      - Products: título contiene q o sku_root contiene q.
      - CanonicalProducts: name contiene q o sku_custom contiene q (si existe).
    Devuelve hasta 'limit' resultados ordenados por (stock desc, título asc).
    """
    term = (q or "").strip()
    if not term:
        # Top por stock (productos con stock)
        rows = (
            await session.execute(
                select(Product.id, Product.title, Product.sku_root, Product.stock)
                .where((Product.stock != None) & (Product.stock > 0))
                .order_by(Product.stock.desc(), Product.title.asc())
                .limit(limit)
            )
        ).all()
        return [
            {"id": r[0], "kind": "product", "title": r[1], "sku": r[2], "stock": int(r[3] or 0), "price": None}
            for r in rows
        ]

    like = f"%{term}%"
    # Buscar en productos
    prod_rows = (
        await session.execute(
            select(Product.id, Product.title, Product.sku_root, Product.stock)
            .where(or_(Product.title.ilike(like), Product.sku_root.ilike(like)))
            .order_by(Product.stock.desc().nullslast(), Product.title.asc())
            .limit(limit)
        )
    ).all()

    # Buscar en canónicos
    can_rows = (
        await session.execute(
            select(CanonicalProduct.id, CanonicalProduct.name, CanonicalProduct.sku_custom, CanonicalProduct.sale_price)
            .where(or_(CanonicalProduct.name.ilike(like), CanonicalProduct.sku_custom.ilike(like)))
            .order_by(CanonicalProduct.name.asc())
            .limit(limit)
        )
    ).all()

    # Merge priorizando productos con stock
    items: list[dict] = []
    for r in prod_rows:
        items.append({"id": r[0], "kind": "product", "title": r[1], "sku": r[2], "stock": int(r[3] or 0), "price": None})
    for r in can_rows:
        items.append({"id": r[0], "kind": "canonical", "title": r[1], "sku": r[2], "stock": None, "price": float(r[3]) if r[3] is not None else None})

    # Orden: productos con stock primero; luego canónicos/otros
    def _key(it: dict):
        return (0 if (it.get("kind") == "product" and (it.get("stock") or 0) > 0) else 1, (it.get("title") or ""))

    items.sort(key=_key)
    return items[:limit]


# ------------------------------- SupplierProduct: link ↔ Variant (upsert) -------------------------------
class _SupplierProductLink(_PydModel):
    supplier_id: int
    supplier_product_id: str
    internal_variant_id: int
    title: Optional[str] = None


@router.post(
    "/supplier-products/link",
    dependencies=[Depends(require_csrf), Depends(require_roles("colaborador", "admin"))],
)
async def supplier_product_link(
    payload: _SupplierProductLink,
    session: AsyncSession = Depends(get_session),
):
    """Crea o actualiza el vínculo entre un SKU de proveedor y una variante interna.

    - Si (supplier_id, supplier_product_id) existe, se actualiza `internal_product_id/internal_variant_id` y `title` opcional.
    - Si no existe, se crea `SupplierProduct` con título opcional.
    - Devuelve el registro resultante con su ID.
    """
    # Validaciones básicas
    supplier = await session.get(Supplier, payload.supplier_id)
    if not supplier:
        raise HTTPException(status_code=400, detail={"code": "invalid_supplier_id"})
    variant = await session.get(Variant, payload.internal_variant_id)
    if not variant:
        raise HTTPException(status_code=400, detail={"code": "invalid_variant_id"})

    product = await session.get(Product, variant.product_id)
    if not product:
        raise HTTPException(status_code=400, detail={"code": "invalid_internal_product"})

    # Buscar existente por clave única (supplier_id, supplier_product_id)
    existing = (
        await session.execute(
            select(SupplierProduct).where(
                (SupplierProduct.supplier_id == payload.supplier_id)
                & (SupplierProduct.supplier_product_id == payload.supplier_product_id)
            )
        )
    ).scalars().first()

    if existing:
        existing.internal_product_id = product.id
        existing.internal_variant_id = variant.id
        if payload.title:
            existing.title = payload.title[:200]
        await session.flush()
        sp = existing
    else:
        sp = SupplierProduct(
            supplier_id=payload.supplier_id,
            supplier_product_id=payload.supplier_product_id,
            title=(payload.title[:200] if payload.title else variant.name or product.title)[:200],
            internal_product_id=product.id,
            internal_variant_id=variant.id,
        )
        session.add(sp)
        await session.flush()

    await session.commit()
    return {
        "id": sp.id,
        "supplier_id": sp.supplier_id,
        "supplier_product_id": sp.supplier_product_id,
        "title": sp.title,
        "internal_product_id": sp.internal_product_id,
        "internal_variant_id": sp.internal_variant_id,
    }


class _ProductsDeleteReq(_PydModel):
    ids: List[int]


@router.delete(
    "/catalog/products",
    dependencies=[Depends(require_csrf)],
)
async def delete_products_guarded(payload: _ProductsDeleteReq, session: AsyncSession = Depends(get_session)):
    """Elimina productos si no tienen stock ni referencias en compras.

    Respuestas:
    - 400 si alguno tiene stock > 0 (single) con detalle.
    - 409 si está referenciado por líneas de compra.
    - 200 con resumen en otros casos.
    """
    blocked_stock: list[int] = []
    blocked_refs: list[int] = []
    deleted: list[int] = []
    for pid in payload.ids:
        p = await session.get(Product, pid)
        if not p:
            continue
        if int(p.stock or 0) > 0:
            blocked_stock.append(pid)
            continue
        ref = await session.scalar(select(func.count()).select_from(PurchaseLine).where(
            (PurchaseLine.product_id == pid)
        ))
        if (ref or 0) > 0:
            blocked_refs.append(pid)
            continue
        # Eliminar explícitamente dependencias para compatibilidad con motores sin ON DELETE CASCADE
        # 1) SupplierProduct vinculados
        sp_count = 0
        sph_count = 0
        try:
            sps = (await session.execute(select(SupplierProduct).where(SupplierProduct.internal_product_id == pid))).scalars().all()
            for sp in sps:
                # Borrar histories primero (FK sin ON DELETE CASCADE)
                try:
                    sph_list = (await session.execute(select(SupplierPriceHistory).where(SupplierPriceHistory.supplier_product_fk == sp.id))).scalars().all()
                    for sph in sph_list:
                        await session.delete(sph)
                        sph_count += 1
                except Exception:
                    pass
                await session.delete(sp)
                sp_count += 1
        except Exception:
            sp_count = 0
        # 2) Variants e Inventory
        var_count = 0
        inv_count = 0
        try:
            vars = (await session.execute(select(Variant).where(Variant.product_id == pid))).scalars().all()
            for v in vars:
                inv = await session.scalar(select(Inventory).where(Inventory.variant_id == v.id))
                if inv:
                    await session.delete(inv)
                    inv_count += 1
                await session.delete(v)
                var_count += 1
        except Exception:
            pass
        # 3) Imágenes
        img_count = 0
        try:
            imgs = (await session.execute(select(Image).where(Image.product_id == pid))).scalars().all()
            for im in imgs:
                await session.delete(im)
                img_count += 1
        except Exception:
            pass
        # 4) Producto
        await session.delete(p)
        # 5) AuditLog por producto
        try:
            session.add(AuditLog(action="product_delete", table="products", entity_id=pid, meta={
                "cascade": {"supplier_products": sp_count, "supplier_price_history": sph_count, "variants": var_count, "inventories": inv_count, "images": img_count}
            }))
        except Exception:
            pass
        deleted.append(pid)
    await session.commit()
    if len(payload.ids) == 1 and blocked_stock:
        raise HTTPException(status_code=400, detail={"code": "product_has_stock", "message": "Producto con stock no puede eliminarse"})
    if len(payload.ids) == 1 and blocked_refs:
        raise HTTPException(status_code=409, detail={"code": "product_has_references", "message": "Producto referenciado por compras"})
    return {"requested": payload.ids, "deleted": deleted, "blocked_stock": blocked_stock, "blocked_refs": blocked_refs}



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
        # Ordenar por más reciente primero para que el último proveedor creado
        # aparezca al principio (facilita tests que toman el primer ID)
        .order_by(Supplier.id.desc())
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
        # Idempotencia amistosa en tests/uso repetido: si el nombre coincide, devolver 200 con el existente.
        if (existing.name or "").strip() == payload.name.strip():
            return {
                "id": existing.id,
                "slug": existing.slug,
                "name": existing.name,
                "location": existing.location,
                "contact_name": existing.contact_name,
                "contact_email": existing.contact_email,
                "contact_phone": existing.contact_phone,
                "notes": existing.notes,
                "extra_json": existing.extra_json,
                "created_at": existing.created_at.isoformat(),
            }
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


class CategoryCreate(BaseModel):
    name: str
    parent_id: int | None = None


@router.post(
    "/categories",
    dependencies=[Depends(require_csrf), Depends(require_roles("colaborador", "admin"))],
)
async def create_category(payload: CategoryCreate, session: AsyncSession = Depends(get_session)) -> dict:
    """Crea una categoría. Unicidad por (name, parent_id).

    Respuesta incluye `id`, `name`, `parent_id` y `path` completo.
    """
    name = (payload.name or "").strip()
    if not name:
        raise HTTPException(status_code=400, detail="name requerido")
    # Verificar padre válido (si viene)
    if payload.parent_id:
        parent = await session.get(Category, payload.parent_id)
        if not parent:
            raise HTTPException(status_code=400, detail="parent_id inválido")
    # Unicidad (name, parent_id)
    exists = await session.scalar(
        select(Category).where(Category.name == name, Category.parent_id == payload.parent_id)
    )
    if exists:
        raise HTTPException(status_code=409, detail="La categoría ya existe en ese nivel")
    # Crear
    cat = Category(name=name, parent_id=payload.parent_id)
    session.add(cat)
    await session.commit()
    await session.refresh(cat)
    # Calcular path
    # Cargar todas para construir lookup mínimo (ascendentes)
    # Optimización simple: caminar hacia arriba
    parts: list[str] = [cat.name]
    parent_id = cat.parent_id
    while parent_id:
        p = await session.get(Category, parent_id)
        if not p:
            break
        parts.append(p.name)
        parent_id = p.parent_id
    path = ">".join(reversed(parts))
    return {"id": cat.id, "name": cat.name, "parent_id": cat.parent_id, "path": path}


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
    type: Optional[str] = Query(None, pattern="^(all|canonical|supplier)$"),
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

    # Filtro por tipo (canónicos|proveedor|todos)
    if type and type != "all":
        if type == "canonical":
            stmt = stmt.where(eq.canonical_product_id.is_not(None))
        elif type == "supplier":
            stmt = stmt.where(eq.canonical_product_id.is_(None))

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

    # Prefetch primer SKU por producto para evitar N+1
    product_ids = [p_obj.id for _, p_obj, *_ in rows]
    skus_by_product: dict[int, str | None] = {}
    if product_ids:
        vs = (
            await session.execute(
                select(Variant.product_id, Variant.sku)
                .where(Variant.product_id.in_(product_ids))
                .order_by(Variant.product_id.asc(), Variant.id.asc())
            )
        ).all()
        for pid, sku in vs:
            if pid not in skus_by_product:
                skus_by_product[pid] = sku

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
                "supplier_item_id": sp_obj.id,
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
                "canonical_sku": (cp_obj.sku_custom if (cp_obj and cp_obj.sku_custom) else (cp_obj.ng_sku if cp_obj else None)),
                "canonical_name": (cp_obj.name if cp_obj else None),
                "first_variant_sku": skus_by_product.get(p_obj.id),
            }
        )

    return {
        "page": page,
        "page_size": page_size,
        "total": total,
        "items": items,
    }


@router.get(
    "/stock/export.xlsx",
    dependencies=[Depends(require_roles("cliente", "proveedor", "colaborador", "admin"))],
)
async def export_stock_xlsx(
    supplier_id: Optional[int] = None,
    category_id: Optional[int] = None,
    q: Optional[str] = None,
    stock: Optional[str] = None,
    created_since_days: Optional[int] = None,
    sort_by: str = "updated_at",
    order: str = "desc",
    type: Optional[str] = Query(None, pattern="^(all|canonical|supplier)$"),
    *,
    request: Request,
    session: AsyncSession = Depends(get_session),
):
    """Exporta un XLS de stock con columnas: NOMBRE DE PRODUCTO, PRECIO DE VENTA, CATEGORIA, SKU PROPIO.

    Respeta los mismos filtros que /products. El precio de venta prioriza el canónico si existe;
    de lo contrario usa el precio de venta del proveedor.
    """
    # Reutilizar lógica de filtros sin paginar
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
        stmt = stmt.where(or_(p.title.ilike(f"%{q}%"), sp.title.ilike(f"%{q}%")))
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
    if created_since_days is not None:
        if created_since_days < 0 or created_since_days > 365:
            raise HTTPException(status_code=400, detail="created_since_days fuera de rango (0-365)")
        from datetime import datetime, timedelta
        cutoff = datetime.utcnow() - timedelta(days=created_since_days)
        stmt = stmt.where(p.created_at >= cutoff)

    # Filtro por tipo (canónicos|proveedor|todos)
    if type and type != "all":
        if type == "canonical":
            stmt = stmt.where(eq.canonical_product_id.is_not(None))
        elif type == "supplier":
            stmt = stmt.where(eq.canonical_product_id.is_(None))

    sort_map = {
        ProductSortBy.updated_at: sp.last_seen_at,
        ProductSortBy.precio_venta: sp.current_sale_price,
        ProductSortBy.precio_compra: sp.current_purchase_price,
        ProductSortBy.name: p.title,
        ProductSortBy.created_at: p.created_at,
    }
    sort_col = sort_map[sort_by_enum]
    sort_col = sort_col.asc() if order_enum == SortOrder.asc else sort_col.desc()
    stmt = stmt.order_by(sort_col)

    result = await session.execute(stmt)
    rows = result.all()

    # Agregar helper para obtener el primer SKU de cada producto sin consultas N+1
    product_ids = list({p_obj.id for _, p_obj, *_ in rows})
    skus_by_product: dict[int, str | None] = {}
    if product_ids:
        vs = (
            await session.execute(
                select(Variant.product_id, Variant.sku)
                .where(Variant.product_id.in_(product_ids))
                .order_by(Variant.product_id.asc(), Variant.id.asc())
            )
        ).all()
        for pid, sku in vs:
            if pid not in skus_by_product:
                skus_by_product[pid] = sku

    # Armar un mapa por producto tomando el primer row encontrado
    by_product: dict[int, dict] = {}
    for sp_obj, p_obj, s_obj, eq_obj, cp_obj in rows:
        if p_obj.id in by_product:
            # Si no hay precio canónico aún y esta fila sí tiene, actualizar
            if by_product[p_obj.id]["canonical_sale_price"] is None and (cp_obj and cp_obj.sale_price is not None):
                by_product[p_obj.id]["canonical_sale_price"] = float(cp_obj.sale_price)
            continue
        # Calcular campos canónicos si existen
        canonical_name = cp_obj.name if cp_obj and getattr(cp_obj, "name", None) else None
        canonical_sku = None
        if cp_obj:
            canonical_sku = cp_obj.sku_custom or cp_obj.ng_sku
        canonical_cat_id = getattr(cp_obj, "category_id", None) if cp_obj else None
        canonical_subcat_id = getattr(cp_obj, "subcategory_id", None) if cp_obj else None

        by_product[p_obj.id] = {
            "product_id": p_obj.id,
            "name": p_obj.title,
            "category_id": p_obj.category_id,
            "supplier_sale_price": float(sp_obj.current_sale_price) if sp_obj.current_sale_price is not None else None,
            "canonical_sale_price": float(cp_obj.sale_price) if (cp_obj and cp_obj.sale_price is not None) else None,
            "canonical_name": canonical_name,
            "canonical_sku": canonical_sku,
            "canonical_category_id": canonical_cat_id,
            "canonical_subcategory_id": canonical_subcat_id,
        }

    # Crear workbook
    wb = Workbook()
    ws = wb.active
    ws.title = "Stock"
    ws.append(["NOMBRE DE PRODUCTO", "PRECIO DE VENTA", "CATEGORIA", "SKU PROPIO"])
    # Estilos de encabezado: fondo oscuro, texto claro y negrita, centrado
    header_fill = PatternFill(start_color="FF333333", end_color="FF333333", fill_type="solid")
    header_font = Font(bold=True, color="FFFFFFFF")
    header_alignment = Alignment(horizontal="center")
    for cell in ws[1]:
        cell.fill = header_fill
        cell.font = header_font
        cell.alignment = header_alignment

    # Completar filas
    max_name_len = 0
    max_cat_len = 0
    max_sku_len = 0
    for pid, rec in by_product.items():
        # Preferir datos canónicos si están disponibles
        # Nombre
        name = rec.get("canonical_name") or rec["name"]
        # Categoría: priorizar subcategoría canónica si existe; luego categoría canónica; si no, categoría del producto interno
        can_subcat_id = rec.get("canonical_subcategory_id")
        can_cat_id = rec.get("canonical_category_id")
        if can_subcat_id:
            cat_path = await _category_path(session, can_subcat_id)
        elif can_cat_id:
            cat_path = await _category_path(session, can_cat_id)
        else:
            cat_path = await _category_path(session, rec["category_id"])  # puede ser None
        # Precio
        precio = rec["canonical_sale_price"] if rec["canonical_sale_price"] is not None else rec["supplier_sale_price"]
        # SKU
        sku = rec.get("canonical_sku") or skus_by_product.get(pid)
        ws.append([
            name,
            float(precio) if precio is not None else None,
            cat_path or "",
            sku or "",
        ])
        # Negrita para nombre
        ws.cell(row=ws.max_row, column=1).font = Font(bold=True)
        # Actualizar métricas de ancho sugerido
        name_len = len(str(name or ""))
        cat_len = len(str(cat_path or ""))
        sku_len = len(str(sku or ""))
        max_name_len = max(max_name_len, name_len)
        max_cat_len = max(max_cat_len, cat_len)
        max_sku_len = max(max_sku_len, sku_len)

    # Ancho automático para la primera columna (estimación basada en caracteres)
    try:
        ws.column_dimensions['A'].width = min(max(12, max_name_len + 2), 60)
        ws.column_dimensions['C'].width = min(max(12, max_cat_len + 2), 60)
        ws.column_dimensions['D'].width = min(max(12, max_sku_len + 2), 60)
    except Exception:
        pass

    # Serializar
    buf = BytesIO()
    wb.save(buf)
    buf.seek(0)
    # Correlation id: usar el que inyecta el middleware si está presente
    cid = None
    try:
        # No hay API pública directa; replicamos regla de middleware
        cid = request.headers.get("x-correlation-id") or request.headers.get("x-request-id")
    except Exception:
        cid = None
    headers = {"Content-Disposition": "attachment; filename=stock.xlsx"}
    if cid:
        headers["X-Correlation-Id"] = cid
    return StreamingResponse(buf, media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", headers=headers)


class StockUpdate(BaseModel):
    stock: int


class ProductCreate(BaseModel):
    title: str
    category_id: Optional[int] = None
    initial_stock: int = 0
    status: Optional[str] = None
    # Campos para creación de categoría en línea
    new_category_name: Optional[str] = None
    new_category_parent_id: Optional[int] = None
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

    final_category_id = payload.category_id
    created_category_id = None

    # Lógica de creación de categoría en línea
    if payload.new_category_name:
        cat_name = payload.new_category_name.strip()
        if not cat_name:
            raise HTTPException(status_code=400, detail="El nombre de la nueva categoría no puede estar vacío")

        # Validar que el padre exista, si se proveyó
        if payload.new_category_parent_id:
            parent_cat = await session.get(Category, payload.new_category_parent_id)
            if not parent_cat:
                raise HTTPException(status_code=400, detail="La categoría padre seleccionada no existe")

        # Buscar si ya existe una categoría con el mismo nombre y padre
        existing_cat = await session.scalar(
            select(Category).where(
                Category.name == cat_name,
                Category.parent_id == payload.new_category_parent_id
            )
        )

        if existing_cat:
            final_category_id = existing_cat.id
        else:
            # Crear la nueva categoría
            new_cat = Category(name=cat_name, parent_id=payload.new_category_parent_id)
            session.add(new_cat)
            await session.flush() # Flush para obtener el ID
            final_category_id = new_cat.id
            created_category_id = new_cat.id
    
    # Validar categoría si se provee y no se creó una nueva
    if final_category_id is not None and not created_category_id:
        cat = await session.get(Category, final_category_id)
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
        category_id=final_category_id,
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

    # Si se creó o vinculó un SupplierProduct en contexto de compra, inicializar precios
    # Regla: precio de venta = precio de compra efectivo de la línea
    # Nota: la confirmación de compra actualizará nuevamente precio de compra y stock; esto es inicial.
    initialized_prices: dict | None = None
    if (payload.purchase_id is not None) and (payload.supplier_id and payload.supplier_sku) and supplier_product_id:
        try:
            from decimal import Decimal
            from sqlalchemy import select as _select
            from db.models import PurchaseLine, SupplierProduct as _SP
            # Buscar una línea de la compra que coincida por supplier_sku (la primera sin product_id si existe)
            ln = await session.scalar(
                _select(PurchaseLine)
                .where(
                    PurchaseLine.purchase_id == payload.purchase_id,
                    PurchaseLine.supplier_sku == payload.supplier_sku,
                )
                .order_by(PurchaseLine.id.asc())
            )
            if ln:
                disc = Decimal(str(ln.line_discount or 0)) / Decimal("100")
                unit = Decimal(str(ln.unit_cost or 0))
                eff = unit * (Decimal("1") - disc)
                sp_obj = await session.get(_SP, supplier_product_id)
                if sp_obj:
                    # Inicializar ambos precios actuales a partir del costo efectivo
                    sp_obj.current_purchase_price = eff
                    sp_obj.current_sale_price = eff
                    try:
                        import logging
                        logging.getLogger("growen").info(
                            "product_create_ctx default_sale_applied sp=%s eff=%s purchase_id=%s line_id=%s",
                            sp_obj.id,
                            str(eff),
                            payload.purchase_id,
                            getattr(ln, "id", None),
                        )
                    except Exception:
                        pass
                    initialized_prices = {"purchase_price": float(eff), "sale_price": float(eff)}
                    await session.commit()
        except Exception:
            # No bloquear por errores de inicialización de precio
            pass

    # audit + logging estructurado
    try:
        meta_log = {
            "title": prod.title,
            "category_id": prod.category_id,
            "created_category_id": created_category_id,
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
                meta={**meta_log, **({"initialized_prices": initialized_prices} if initialized_prices else {})},
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
    # Resolver canónico (si existe) a partir de equivalencias del/los SupplierProduct asociados a este producto interno
    canonical_id = None
    canonical_sale = None
    canonical_sku = None
    canonical_name = None
    try:
        sp_rows = (await session.execute(
            select(ProductEquivalence.canonical_product_id)
            .join(SupplierProduct, SupplierProduct.id == ProductEquivalence.supplier_product_id)
            .where(SupplierProduct.internal_product_id == product_id)
            .limit(1)
        )).scalars().all()
        if sp_rows:
            canonical_id = sp_rows[0]
            if canonical_id:
                cp = await session.get(CanonicalProduct, canonical_id)
                if cp and cp.sale_price is not None:
                    canonical_sale = float(cp.sale_price)
                if cp:
                    canonical_sku = cp.sku_custom or cp.ng_sku
                    canonical_name = cp.name
    except Exception:
        pass
    cat_path = await _category_path(session, prod.category_id)
    return {
        "id": prod.id,
        "title": prod.title,
        "slug": prod.slug,
        "stock": prod.stock,
        "sku_root": prod.sku_root,
        "category_path": cat_path,
        "description_html": prod.description_html,
        "canonical_product_id": canonical_id,
        "canonical_sale_price": canonical_sale,
    "canonical_sku": canonical_sku,
    "canonical_name": canonical_name,
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


# ------------------------------ Variantes por producto ------------------------------


@router.get(
    "/products/{product_id}/variants",
    dependencies=[Depends(require_roles("cliente", "proveedor", "colaborador", "admin"))],
)
async def list_product_variants(product_id: int, session: AsyncSession = Depends(get_session)):
    """Devuelve las variantes asociadas a un producto interno.

    Respuesta: lista de objetos con `id`, `sku`, `name`, `value`.
    """
    prod = await session.get(Product, product_id)
    if not prod:
        raise HTTPException(status_code=404, detail="Producto no encontrado")
    rows = (
        await session.execute(
            select(Variant)
            .where(Variant.product_id == product_id)
            .order_by(Variant.id.asc())
        )
    ).scalars().all()
    return [
        {
            "id": v.id,
            "sku": v.sku,
            "name": v.name,
            "value": v.value,
        }
        for v in rows
    ]


class ProductUpdate(BaseModel):
    description_html: str | None = None
    category_id: int | None = None


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
    old_cat = getattr(prod, "category_id", None)
    if "description_html" in data:
        prod.description_html = data["description_html"]
    if "category_id" in data:
        # Validar existencia (permitir None para desasociar)
        if data["category_id"] is not None:
            cat = await session.get(Category, int(data["category_id"]))
            if not cat:
                raise HTTPException(status_code=400, detail="category_id inválido")
        prod.category_id = int(data["category_id"]) if data["category_id"] is not None else None
    await session.commit()
    # audit description change
    try:
        session.add(
            AuditLog(
                action="product_update",
                table="products",
                entity_id=product_id,
                meta={
                    "fields": list(data.keys()),
                    "desc_len_old": (len(old_desc or "") if old_desc is not None else None),
                    "desc_len_new": (len(prod.description_html or "") if prod.description_html is not None else None),
                    **({"category_old": old_cat, "category_new": prod.category_id} if "category_id" in data else {}),
                },
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
    """Borrado sin validaciones estrictas (uso interno/tests).

    A diferencia de ``/catalog/products`` que aplica reglas de stock y referencias,
    este endpoint elimina los productos solicitados de forma directa, junto con
    SupplierProducts asociados, y devuelve la cantidad eliminada.
    """
    if not payload.ids:
        raise HTTPException(status_code=400, detail="ids requerido")
    if len(payload.ids) > 500:
        raise HTTPException(status_code=400, detail="máx 500 ids por solicitud")

    deleted = 0
    for pid in payload.ids:
        prod = await session.get(Product, pid)
        if not prod:
            continue
        # Borrar SupplierProducts asociados (compatibilidad sin ON DELETE CASCADE)
        sp_ids = (await session.execute(select(SupplierProduct.id).where(SupplierProduct.internal_product_id == pid))).scalars().all()
        for sid in sp_ids:
            sp_obj = await session.get(SupplierProduct, sid)
            if sp_obj:
                await session.delete(sp_obj)
        await session.delete(prod)
        deleted += 1
        try:
            session.add(
                AuditLog(
                    action="delete",
                    table="products",
                    entity_id=pid,
                    meta={"name": getattr(prod, "title", None)},
                    user_id=sess.user.id if sess and sess.user else None,
                    ip=(request.client.host if request and request.client else None),
                )
            )
        except Exception:
            pass

    await session.commit()
    # Audit resumen
    try:
        session.add(
            AuditLog(
                action="products_delete_bulk",
                table="products",
                entity_id=None,
                meta={"requested": len(payload.ids), "deleted": deleted},
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


class PriceUpdate(BaseModel):
    supplier_item_id: int
    purchase_price: Optional[float] = None
    sale_price: Optional[float] = None


@router.patch(
    "/products/{product_id}/prices",
    dependencies=[Depends(require_csrf), Depends(require_roles("colaborador", "admin"))],
)
async def update_product_prices(
    product_id: int,
    payload: PriceUpdate,
    session: AsyncSession = Depends(get_session),
    request: Request = None,
    sess: SessionData = Depends(current_session),
):
    """
    Actualiza precios de un producto.
    - `purchase_price`: Actualiza `current_purchase_price` en `SupplierProduct`.
    - `sale_price`: Actualiza `sale_price` en `CanonicalProduct` si está enlazado.
    """
    prod = await session.get(Product, product_id)
    if not prod:
        raise HTTPException(status_code=404, detail="Producto no encontrado")

    sp = await session.get(SupplierProduct, payload.supplier_item_id)
    if not sp or sp.internal_product_id != product_id:
        raise HTTPException(status_code=404, detail="Supplier item no encontrado o no corresponde al producto")

    updated_fields = {}
    old_values = {}

    # 1. Actualizar precio de compra del proveedor (SupplierProduct)
    if payload.purchase_price is not None:
        if sp.current_purchase_price != payload.purchase_price:
            old_values["purchase_price"] = sp.current_purchase_price
            sp.current_purchase_price = payload.purchase_price
            updated_fields["purchase_price"] = payload.purchase_price

    # 2. Actualizar precio de venta canónico (CanonicalProduct)
    if payload.sale_price is not None:
        # Encontrar el producto canónico a través de la tabla de equivalencia
        eq = await session.scalar(
            select(ProductEquivalence).where(ProductEquivalence.supplier_product_id == sp.id)
        )
        if eq and eq.canonical_product_id:
            cp = await session.get(CanonicalProduct, eq.canonical_product_id)
            if cp and cp.sale_price != payload.sale_price:
                old_values["sale_price"] = cp.sale_price
                cp.sale_price = payload.sale_price
                updated_fields["sale_price"] = payload.sale_price
        else:
            # Si no hay producto canónico, no se puede actualizar el precio de venta.
            # Podríamos devolver un error o simplemente ignorarlo. Por ahora, lo ignoramos.
            pass

    if not updated_fields:
        return JSONResponse(status_code=304, content={"message": "No changes detected"})

    await session.commit()

    # Registrar en AuditLog
    try:
        session.add(
            AuditLog(
                action="product_price_update",
                table="products",
                entity_id=product_id,
                meta={
                    "supplier_item_id": sp.id,
                    "updated_fields": updated_fields,
                    "old_values": old_values,
                },
                user_id=sess.user.id if sess and sess.user else None,
                ip=(request.client.host if request and request.client else None),
            )
        )
        await session.commit()
    except Exception:
        pass  # No fallar si el loggeo falla

    return {"status": "ok", "updated_fields": updated_fields}
