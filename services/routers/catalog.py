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
from datetime import datetime as _dt
from fastapi.responses import JSONResponse, StreamingResponse
from io import BytesIO
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment
from pydantic import BaseModel, ValidationError
from sqlalchemy import func, select, or_, update
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
from db.text_utils import stylize_product_name
from agent_core.config import settings
from ai.router import AIRouter
from ai.providers.openai_provider import OpenAIProvider
from ai.types import Task
from services.auth import require_csrf, require_roles, current_session, SessionData

router = APIRouter(tags=["catalog"])

# Tamaño de página por defecto para el historial de precios
DEFAULT_PRICE_HISTORY_PAGE_SIZE = int(os.getenv("PRICE_HISTORY_PAGE_SIZE", "20"))
# ------------------------------- Productos (mínimo para tests) -------------------------------
from pydantic import BaseModel as _PydModel


class _ProductCreate(_PydModel):
    title: str
    initial_stock: int = 0
    supplier_id: Optional[int] = None
    supplier_sku: Optional[str] = None
    sku: Optional[str] = None
    purchase_price: Optional[float] = None
    sale_price: Optional[float] = None
    # Nuevos campos para generación canónica automática
    category_name: Optional[str] = None
    subcategory_name: Optional[str] = None
    generate_canonical: bool = False


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
    desired_sku = (payload.sku or payload.supplier_sku or payload.title)[:50].strip() if payload.sku or payload.supplier_sku else (payload.title or "")[:50].strip()
    if not desired_sku:
        raise HTTPException(status_code=400, detail={"code": "invalid_sku", "message": "SKU inválido"})
    from db.sku_utils import is_canonical_sku, CANONICAL_SKU_PATTERN, CANONICAL_SKU_REGEX
    strict_flag = os.getenv("CANONICAL_SKU_STRICT", "1") == "1"  # ahora estricto por defecto
    force_gen_flag = os.getenv("FORCE_CANONICAL", "0") == "1"

    # Regla pseudo-canónica: si tiene exactamente dos '_' y no cumple regex => 422
    if desired_sku.count('_') == 2 and not is_canonical_sku(desired_sku):
        raise HTTPException(status_code=422, detail={
            "code": "invalid_canonical_sku",
            "message": f"Formato canónico inválido: esperado {CANONICAL_SKU_PATTERN}",
        })
    # Adicional: si parece canónico pero sin guiones bajos (AAA0000BBB), rechazar
    try:
        import re as _re
        if _re.match(r"^[A-Za-z]{3}\d{4}[A-Za-z]{3}$", desired_sku or "") and not is_canonical_sku(desired_sku):
            raise HTTPException(status_code=422, detail={
                "code": "invalid_canonical_sku",
                "message": f"Formato canónico inválido: esperado {CANONICAL_SKU_PATTERN}",
            })
    except HTTPException:
        raise

    sku_is_canonical = is_canonical_sku(desired_sku)

    # Si el SKU ya existe y es canónico, permitir vincular SupplierProduct en lugar de error (linking)
    if sku_is_canonical:
        existing_var = await session.scalar(select(Variant).where(func.lower(Variant.sku) == desired_sku.lower()))
        if existing_var:
            existing_prod = await session.get(Product, existing_var.product_id)
            if payload.supplier_id is not None:
                # Si ya existe un SupplierProduct con la misma pareja (supplier_id, supplier_sku),
                # consideramos que es un duplicado de SKU del flujo minimal y devolvemos 409 duplicate_sku
                if payload.supplier_sku:
                    sp_exist = await session.scalar(
                        select(SupplierProduct).where(
                            SupplierProduct.supplier_id == payload.supplier_id,
                            SupplierProduct.supplier_product_id == payload.supplier_sku,
                        )
                    )
                    if sp_exist:
                        raise HTTPException(status_code=409, detail={"code": "duplicate_sku", "message": "SKU ya existente"})
                # Crear/asegurar SupplierProduct vinculado al producto/variante existente
                sp = SupplierProduct(
                    supplier_id=payload.supplier_id,
                    supplier_product_id=(payload.supplier_sku or desired_sku),
                    title=payload.title[:200],
                    current_purchase_price=(payload.purchase_price if payload.purchase_price is not None else None),
                    current_sale_price=(payload.sale_price if payload.sale_price is not None else None),
                    internal_product_id=existing_prod.id if existing_prod else None,
                    internal_variant_id=existing_var.id,
                )
                session.add(sp)
                await session.flush()
                try:
                    await session.commit()
                except IntegrityError:
                    await session.rollback()
                    # Si ya existe SupplierProduct con ese supplier+sku, retornamos link sin crear
                response = {
                    "id": existing_prod.id if existing_prod else None,
                    "title": existing_prod.title if existing_prod else payload.title,
                    "sku_root": getattr(existing_prod, 'sku_root', desired_sku) if existing_prod else desired_sku,
                    "linked": True,
                    "created": False,
                    "idempotent": False,
                }
                try:
                    response["supplier_item_id"] = sp.id
                except Exception:
                    pass
                return response
            # Sin supplier, retornar referencia sin crear duplicados
            return {
                "id": existing_prod.id if existing_prod else None,
                "title": existing_prod.title if existing_prod else payload.title,
                "sku_root": getattr(existing_prod, 'sku_root', desired_sku) if existing_prod else desired_sku,
                "linked": True,
                "created": False,
                "idempotent": True,
            }

    # Generación automática si se solicita o es requerido en modo estricto sin sku válido
    if (payload.generate_canonical or (strict_flag and not sku_is_canonical)):
        # Requiere category_name y subcategory_name (subcat opcional, si falta se reutiliza category)
        if not payload.category_name:
            raise HTTPException(status_code=400, detail={"code": "missing_category_name", "message": "category_name requerido para generación canónica"})
        from db.sku_generator import generate_canonical_sku, CanonicalSkuGenerationError
        try:
            desired_sku = await generate_canonical_sku(session, payload.category_name, payload.subcategory_name or payload.category_name)
            sku_is_canonical = True
        except CanonicalSkuGenerationError as ge:
            raise HTTPException(status_code=500, detail={"code": "canonical_generation_error", "message": str(ge)})

    # En modo no estricto, aceptamos legacy y sólo seteamos canonical_sku si coincide el patrón.
    # Búsqueda case-insensitive para evitar conflictos por mayúsculas/minúsculas
    existing = await session.scalar(select(Variant).where(func.lower(Variant.sku) == desired_sku.lower()))
    if existing:
        raise HTTPException(status_code=409, detail={"code": "duplicate_sku", "message": "SKU ya existente"})

    try:
        # Asegurar (o crear en caliente en SQLite) la columna canonical_sku ANTES de instanciar Product
        has_canonical_col = await _products_has_canonical(session)
        import logging as _logging
        _logging.getLogger("growen").debug({"event": "create_product_minimal.start", "desired_sku": desired_sku, "strict": strict_flag})

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
        await session.rollback()
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
    """Búsqueda rápida para POS y chatbot.

    Busca productos con su información canónica vinculada.
    Devuelve SKU canónico (formato XXX_####_YYY) preferentemente sobre el interno.
    Prioriza productos con stock>0.
    """
    term = (q or "").strip()
    
    # Query base: productos con su info canónica vinculada
    base_query = (
        select(
            Product.id,
            Product.title,
            Product.stock,
            Product.description_html,
            CanonicalProduct.id.label("canonical_id"),
            CanonicalProduct.name.label("canonical_name"),
            CanonicalProduct.sku_custom.label("canonical_sku"),
            CanonicalProduct.ng_sku,
            CanonicalProduct.sale_price,
        )
        .join(SupplierProduct, SupplierProduct.internal_product_id == Product.id, isouter=True)
        .join(ProductEquivalence, ProductEquivalence.supplier_product_id == SupplierProduct.id, isouter=True)
        .join(CanonicalProduct, CanonicalProduct.id == ProductEquivalence.canonical_product_id, isouter=True)
    )
    
    if not term:
        # Top por stock (productos con stock)
        rows = (
            await session.execute(
                base_query
                .where((Product.stock != None) & (Product.stock > 0))
                .order_by(Product.stock.desc(), Product.title.asc())
                .limit(limit)
            )
        ).all()
    else:
        like = f"%{term}%"
        # Buscar en título del producto o nombre canónico o SKU canónico
        rows = (
            await session.execute(
                base_query
                .where(
                    or_(
                        Product.title.ilike(like),
                        CanonicalProduct.name.ilike(like),
                        CanonicalProduct.sku_custom.ilike(like),
                        CanonicalProduct.ng_sku.ilike(like),
                    )
                )
                .order_by(Product.stock.desc().nullslast(), Product.title.asc())
                .limit(limit * 2)  # Extra para deduplicar
            )
        ).all()
    
    # Deduplicar por product_id (puede haber múltiples filas si hay varios SupplierProducts)
    seen_ids: set[int] = set()
    items: list[dict] = []
    
    for row in rows:
        if row.id in seen_ids:
            continue
        seen_ids.add(row.id)
        
        # SKU preferido: canónico (formato XXX_####_YYY) sobre interno
        preferred_sku = row.canonical_sku or row.ng_sku
        # Nombre preferido: canónico sobre interno
        preferred_name = stylize_product_name(row.canonical_name or row.title) or row.title
        # Precio de venta desde canónico
        sale_price = float(row.sale_price) if row.sale_price else None
        
        items.append({
            "id": row.id,
            "title": preferred_name,
            "sku": preferred_sku,
            "stock": int(row.stock or 0),
            "price": sale_price,
            "has_description": bool(row.description_html),
        })
    
    # Orden: productos con stock primero; luego por nombre
    items.sort(key=lambda it: (0 if (it.get("stock") or 0) > 0 else 1, (it.get("title") or "")))
    
    return items[:limit]


# ------------------------------- Helper: Build Product Response -------------------------------
async def _build_product_response(session: AsyncSession, product: Product) -> dict:
    """Construye la respuesta completa de un producto con su info canónica.
    
    Devuelve SKU canónico (formato XXX_####_YYY) preferentemente.
    """
    # Calcular stock real
    stock = product.stock or 0
    try:
        inv_result = await session.execute(
            select(func.sum(Inventory.stock_qty))
            .join(Variant, Variant.id == Inventory.variant_id)
            .where(Variant.product_id == product.id)
        )
        inv_total = inv_result.scalar()
        if inv_total is not None:
            stock = int(inv_total)
    except Exception:
        pass

    # Obtener info canónica vinculada
    canonical_info = (
        await session.execute(
            select(CanonicalProduct)
            .join(ProductEquivalence, ProductEquivalence.canonical_product_id == CanonicalProduct.id)
            .join(SupplierProduct, SupplierProduct.id == ProductEquivalence.supplier_product_id)
            .where(SupplierProduct.internal_product_id == product.id)
            .limit(1)
        )
    ).scalars().first()

    # SKU preferido: canónico (formato XXX_####_YYY) sobre interno
    canonical_sku = None
    sale_price = None
    canonical_name = None
    
    if canonical_info:
        canonical_sku = canonical_info.sku_custom or canonical_info.ng_sku
        canonical_name = canonical_info.name
        if canonical_info.sale_price:
            sale_price = float(canonical_info.sale_price)

    # Si no hay precio canónico, intentar desde variante
    if sale_price is None:
        variant = (
            await session.execute(
                select(Variant).where(Variant.product_id == product.id).limit(1)
            )
        ).scalars().first()
        if variant and (variant.promo_price or variant.price):
            sale_price = float(variant.promo_price or variant.price)

    return {
        "product_id": product.id,
        "sku": canonical_sku,  # SKU canónico (puede ser None si no hay)
        "name": stylize_product_name(canonical_name or product.title) or "(sin nombre)",
        "sale_price": sale_price,
        "stock": stock,
        "description": getattr(product, 'description_html', None),
        "technical_specs": getattr(product, 'technical_specs', None),
        "usage_instructions": getattr(product, 'usage_instructions', None),
    }


# ------------------------------- Variants Lookup (para MCP Products) -------------------------------
@router.get(
    "/variants/lookup",
    dependencies=[Depends(require_roles("cliente", "proveedor", "colaborador", "admin"))],
)
async def variants_lookup(
    sku: str = Query(None, description="SKU del producto a buscar (canónico preferido)"),
    product_id: int = Query(None, description="ID del producto interno"),
    session: AsyncSession = Depends(get_session),
):
    """Busca un producto por SKU canónico o ID y devuelve información completa.

    Este endpoint es usado por el servidor MCP de productos para obtener
    información detallada de un producto específico.

    Parámetros (usar uno u otro):
      - sku: SKU canónico (formato XXX_####_YYY) o interno
      - product_id: ID interno del producto

    Búsqueda en orden:
      1. Por product_id si se proporciona
      2. Por SKU canónico (CanonicalProduct.sku_custom o ng_sku)
      3. Por SKU interno (Product.sku_root)

    Devuelve: sku (canónico), name, sale_price, stock, description, technical_specs, usage_instructions.
    """
    if not sku and not product_id:
        raise HTTPException(status_code=400, detail={"code": "missing_sku_or_product_id"})

    # 0. Buscar por product_id directamente
    if product_id:
        product = await session.get(Product, product_id)
        if product:
            return await _build_product_response(session, product)
        raise HTTPException(status_code=404, detail={"code": "product_not_found", "product_id": product_id})

    sku_lower = sku.strip().lower()
    if not sku_lower:
        raise HTTPException(status_code=400, detail={"code": "empty_sku"})

    # 1. PRIORIDAD: Buscar por SKU canónico (formato XXX_####_YYY)
    canonical = (
        await session.execute(
            select(CanonicalProduct).where(
                or_(
                    func.lower(CanonicalProduct.sku_custom) == sku_lower,
                    func.lower(CanonicalProduct.ng_sku) == sku_lower,
                )
            )
        )
    ).scalars().first()

    if canonical:
        # Encontrar el producto vinculado al canónico
        product_row = (
            await session.execute(
                select(Product)
                .join(SupplierProduct, SupplierProduct.internal_product_id == Product.id)
                .join(ProductEquivalence, ProductEquivalence.supplier_product_id == SupplierProduct.id)
                .where(ProductEquivalence.canonical_product_id == canonical.id)
                .limit(1)
            )
        ).scalars().first()
        
        if product_row:
            return await _build_product_response(session, product_row)
        
        # Si no hay producto vinculado, devolver info del canónico
        return {
            "product_id": None,
            "sku": canonical.sku_custom or canonical.ng_sku,
            "name": stylize_product_name(canonical.name) or "(sin nombre)",
            "sale_price": float(canonical.sale_price) if canonical.sale_price else None,
            "stock": 0,
            "description": None,
            "technical_specs": None,
            "usage_instructions": None,
        }

    # 2. Buscar por SKU interno (Product.sku_root) - fallback
    product = (
        await session.execute(
            select(Product).where(func.lower(Product.sku_root) == sku_lower)
        )
    ).scalars().first()

    if product:
        return await _build_product_response(session, product)

    # 3. Buscar en Variant por sku - último recurso
    variant = (
        await session.execute(
            select(Variant).where(func.lower(Variant.sku) == sku_lower)
        )
    ).scalars().first()

    if variant and variant.product_id:
        parent_product = await session.get(Product, variant.product_id)
        if parent_product:
            return await _build_product_response(session, parent_product)

    # No encontrado
    raise HTTPException(status_code=404, detail={"code": "product_not_found", "sku": sku})


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


@router.delete(
    "/suppliers",
    dependencies=[Depends(require_csrf), Depends(require_roles("admin"))],
)
async def bulk_delete_suppliers(
    request: Request,
    session: AsyncSession = Depends(get_session),
    sess: SessionData = Depends(current_session),
    force_cascade: bool = False,
):
    """Eliminación bulk de proveedores con validación de integridad referencial.
    
    Parámetros:
    - ids: Array de IDs de proveedores a eliminar
    - force_cascade: Si es true, elimina en cascada import_jobs y equivalencias (solo registros no críticos)
    
    Retorna:
    - requested: IDs solicitados
    - deleted: IDs eliminados exitosamente
    - blocked: Proveedores bloqueados con razones, conteos y detalles de registros bloqueantes
    - not_found: IDs no encontrados
    - cascade_deleted: Registros eliminados en cascada (si force_cascade=true)
    """
    if request.headers.get("content-type") != "application/json":
        raise HTTPException(status_code=415, detail="Content-Type debe ser application/json")
    
    try:
        body = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="JSON inválido")
    
    ids = body.get("ids")
    if not ids or not isinstance(ids, list):
        raise HTTPException(status_code=400, detail="ids requerido (array)")
    
    if len(ids) > 500:
        raise HTTPException(status_code=400, detail="máx 500 ids por solicitud")
    
    # Permitir force_cascade desde body también
    force_cascade = body.get("force_cascade", force_cascade)
    
    from db.models import Purchase, PurchaseLine, ImportJob, ProductEquivalence
    
    requested = list(ids)
    deleted = []
    blocked = []
    not_found = []
    cascade_deleted = {
        "import_jobs": [],
        "product_equivalences": []
    }
    
    for sid in requested:
        supplier = await session.get(Supplier, sid)
        if not supplier:
            not_found.append(sid)
            continue
        
        # Verificar referencias bloqueantes
        reasons = []
        counts = {}
        blocking_details = {}
        
        # Contar compras
        purchases_count = await session.scalar(
            select(func.count()).select_from(Purchase).where(Purchase.supplier_id == sid)
        )
        if purchases_count > 0:
            reasons.append("tiene_compras")
            counts["purchases"] = purchases_count
            # Obtener IDs de compras para referencia
            purchase_ids = (await session.execute(
                select(Purchase.id).where(Purchase.supplier_id == sid).limit(10)
            )).scalars().all()
            blocking_details["purchases"] = {
                "count": purchases_count,
                "sample_ids": list(purchase_ids),
                "action": "No se pueden eliminar automáticamente. Revisar módulo de compras."
            }
        
        # Contar archivos
        files_count = await session.scalar(
            select(func.count()).select_from(SupplierFile).where(SupplierFile.supplier_id == sid)
        )
        if files_count > 0:
            reasons.append("tiene_archivos")
            counts["files"] = files_count
            file_ids = (await session.execute(
                select(SupplierFile.id).where(SupplierFile.supplier_id == sid).limit(10)
            )).scalars().all()
            blocking_details["files"] = {
                "count": files_count,
                "sample_ids": list(file_ids),
                "action": "Se eliminarán automáticamente (CASCADE). Este bloqueo es informativo."
            }
        
        # Contar import jobs
        import_jobs_count = await session.scalar(
            select(func.count()).select_from(ImportJob).where(ImportJob.supplier_id == sid)
        )
        if import_jobs_count > 0:
            # Obtener detalles de los jobs
            jobs_info = (await session.execute(
                select(ImportJob.id, ImportJob.status).where(ImportJob.supplier_id == sid)
            )).all()
            
            if force_cascade:
                # Eliminar jobs en cascada
                for job_id, _ in jobs_info:
                    job = await session.get(ImportJob, job_id)
                    if job:
                        await session.delete(job)
                        cascade_deleted["import_jobs"].append(job_id)
            else:
                reasons.append("tiene_import_jobs")
                counts["import_jobs"] = import_jobs_count
                blocking_details["import_jobs"] = {
                    "count": import_jobs_count,
                    "jobs": [{"id": jid, "status": status} for jid, status in jobs_info],
                    "action": "Usar force_cascade=true para eliminar automáticamente, o ejecutar: DELETE FROM import_jobs WHERE supplier_id = {}".format(sid)
                }
        
        # Contar equivalencias
        equivalences_count = await session.scalar(
            select(func.count()).select_from(ProductEquivalence).where(ProductEquivalence.supplier_id == sid)
        )
        if equivalences_count > 0:
            equiv_ids = (await session.execute(
                select(ProductEquivalence.id).where(ProductEquivalence.supplier_id == sid)
            )).scalars().all()
            
            if force_cascade:
                # Eliminar equivalencias en cascada
                for eq_id in equiv_ids:
                    eq = await session.get(ProductEquivalence, eq_id)
                    if eq:
                        await session.delete(eq)
                        cascade_deleted["product_equivalences"].append(eq_id)
            else:
                reasons.append("tiene_equivalencias")
                counts["equivalences"] = equivalences_count
                blocking_details["equivalences"] = {
                    "count": equivalences_count,
                    "sample_ids": list(equiv_ids)[:10],
                    "action": "Usar force_cascade=true para eliminar automáticamente, o ejecutar: DELETE FROM product_equivalences WHERE supplier_id = {}".format(sid)
                }
        
        # Contar líneas de compra a través de supplier_products
        sp_ids = (await session.execute(
            select(SupplierProduct.id).where(SupplierProduct.supplier_id == sid)
        )).scalars().all()
        
        purchase_lines_count = 0
        if sp_ids:
            purchase_lines_count = await session.scalar(
                select(func.count()).select_from(PurchaseLine).where(
                    PurchaseLine.supplier_item_id.in_(sp_ids)
                )
            )
            if purchase_lines_count > 0:
                reasons.append("tiene_lineas_compra")
                counts["purchase_lines"] = purchase_lines_count
                pl_ids = (await session.execute(
                    select(PurchaseLine.id).where(PurchaseLine.supplier_item_id.in_(sp_ids)).limit(10)
                )).scalars().all()
                blocking_details["purchase_lines"] = {
                    "count": purchase_lines_count,
                    "sample_ids": list(pl_ids),
                    "action": "No se pueden eliminar automáticamente. Revisar líneas de compra asociadas."
                }
        
        if reasons:
            blocked.append({
                "id": sid,
                "name": supplier.name,
                "reasons": reasons,
                "counts": counts,
                "details": blocking_details
            })
        else:
            # Eliminar supplier_products asociados (si no tienen referencias)
            for sp_id in sp_ids:
                sp_obj = await session.get(SupplierProduct, sp_id)
                if sp_obj:
                    await session.delete(sp_obj)
            
            # Los SupplierFile tienen CASCADE, se eliminan automáticamente
            await session.delete(supplier)
            deleted.append(sid)
            
            # Audit log
            try:
                session.add(
                    AuditLog(
                        action="delete",
                        table="suppliers",
                        entity_id=sid,
                        meta={"name": supplier.name, "slug": supplier.slug},
                        user_id=sess.user.id if sess and sess.user else None,
                        ip=(request.client.host if request and request.client else None),
                    )
                )
            except Exception:
                pass
    
    await session.commit()
    
    # Audit log resumen
    try:
        session.add(
            AuditLog(
                action="suppliers_delete_bulk",
                table="suppliers",
                entity_id=None,
                meta={
                    "requested": len(requested),
                    "deleted": len(deleted),
                    "blocked": len(blocked),
                    "not_found": len(not_found)
                },
                user_id=sess.user.id if sess and sess.user else None,
                ip=(request.client.host if request and request.client else None),
            )
        )
        await session.commit()
    except Exception:
        pass
    
    return {
        "requested": requested,
        "deleted": deleted,
        "blocked": blocked,
        "not_found": not_found,
        "cascade_deleted": cascade_deleted if force_cascade else None,
        "help": {
            "force_cascade": "Agregar 'force_cascade': true al body para eliminar automáticamente import_jobs y product_equivalences",
            "manual_cleanup": "Para bloqueos críticos (compras, líneas), revisar detalles en 'blocked[].details'"
        }
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
        # Búsqueda por nombre interno, título del proveedor y también por nombre canónico
        stmt = stmt.where(
            or_(
                p.title.ilike(f"%{q}%"),
                sp.title.ilike(f"%{q}%"),
                cp.name.ilike(f"%{q}%"),
            )
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
        # Estilizar nombre: Title Case con unidades preservadas
        raw_name = cp_obj.name if (cp_obj and getattr(cp_obj, "name", None)) else p_obj.title
        preferred_name = stylize_product_name(raw_name)
        items.append(
            {
                "product_id": p_obj.id,
                "name": stylize_product_name(p_obj.title),
                "preferred_name": preferred_name,
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
                "canonical_name": stylize_product_name(cp_obj.name) if cp_obj else None,
                "first_variant_sku": skus_by_product.get(p_obj.id),
                # Etapa 1: Datos estructurados de enriquecimiento
                "technical_specs": getattr(p_obj, 'technical_specs', None),
                "usage_instructions": getattr(p_obj, 'usage_instructions', None),
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
        # Nombre: estilizado con Title Case
        name = stylize_product_name(rec.get("canonical_name") or rec["name"])
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


@router.get(
    "/stock/export-tiendanegocio.xlsx",
    dependencies=[Depends(require_roles("colaborador", "admin"))],
)
async def export_stock_tiendanegocio_xlsx(
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
    """Exporta un XLS con el formato de importación de TiendaNegocio.

    Columnas:
    - SKU (OBLIGATORIO)
    - Nombre del producto
    - Precio
    - Oferta
    - Stock
    - Visibilidad (Visible o Oculto)
    - Descripción
    - Peso en KG
    - Alto en CM
    - Ancho en CM
    - Profundidad en CM
    - Nombre de variante #1
    - Opción de variante #1
    - Nombre de variante #2
    - Opción de variante #2
    - Nombre de variante #3
    - Opción de variante #3
    - Categorías > Subcategorías > … > Subcategorías
    """
    # Reutilizar filtros y ordenamiento como en export_stock_xlsx (sin paginar)
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

    # Prefetch primer SKU por producto
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

    # Mapear por producto priorizando canónicos
    by_product: dict[int, dict] = {}
    for sp_obj, p_obj, s_obj, eq_obj, cp_obj in rows:
        rec = by_product.get(p_obj.id)
        if rec:
            # Completar precio canónico si aún no
            if rec.get("canonical_sale_price") is None and (cp_obj and cp_obj.sale_price is not None):
                rec["canonical_sale_price"] = float(cp_obj.sale_price)
            continue
        by_product[p_obj.id] = {
            "product_id": p_obj.id,
            "name": p_obj.title,
            "stock": p_obj.stock,
            "description_html": getattr(p_obj, "description_html", None),
            "weight_kg": float(p_obj.weight_kg) if p_obj.weight_kg is not None else None,
            "height_cm": float(p_obj.height_cm) if p_obj.height_cm is not None else None,
            "width_cm": float(p_obj.width_cm) if p_obj.width_cm is not None else None,
            "depth_cm": float(p_obj.depth_cm) if p_obj.depth_cm is not None else None,
            "category_id": p_obj.category_id,
            "supplier_sale_price": float(sp_obj.current_sale_price) if sp_obj.current_sale_price is not None else None,
            "canonical_sale_price": float(cp_obj.sale_price) if (cp_obj and cp_obj.sale_price is not None) else None,
            "canonical_name": (cp_obj.name if (cp_obj and getattr(cp_obj, "name", None)) else None),
            "canonical_sku": (cp_obj.sku_custom or cp_obj.ng_sku) if cp_obj else None,
            "canonical_category_id": getattr(cp_obj, "category_id", None) if cp_obj else None,
            "canonical_subcategory_id": getattr(cp_obj, "subcategory_id", None) if cp_obj else None,
        }

    # Construir workbook con cabecera TiendaNegocio
    wb = Workbook()
    ws = wb.active
    ws.title = "Productos"
    ws.append([
        "SKU (OBLIGATORIO)",
        "Nombre del producto",
        "Precio",
        "Oferta",
        "Stock",
        "Visibilidad (Visible o Oculto)",
        "Descripción",
        "Peso en KG",
        "Alto en CM",
        "Ancho en CM",
        "Profundidad en CM",
        "Nombre de variante #1",
        "Opción de variante #1",
        "Nombre de variante #2",
        "Opción de variante #2",
        "Nombre de variante #3",
        "Opción de variante #3",
        "Categorías > Subcategorías > … > Subcategorías",
    ])
    header_fill = PatternFill(start_color="FF333333", end_color="FF333333", fill_type="solid")
    header_font = Font(bold=True, color="FFFFFFFF")
    header_alignment = Alignment(horizontal="center")
    for cell in ws[1]:
        cell.fill = header_fill
        cell.font = header_font
        cell.alignment = header_alignment

    # Filas
    for pid, rec in by_product.items():
        # SKU obligatorio: canónico si existe, si no, primer SKU de variante
        sku = rec.get("canonical_sku") or skus_by_product.get(pid) or ""
        # Nombre preferido: estilizado con Title Case
        name = stylize_product_name(rec.get("canonical_name") or rec.get("name") or "")
        # Precio: priorizar canónico
        precio = rec.get("canonical_sale_price") if rec.get("canonical_sale_price") is not None else rec.get("supplier_sale_price")
        # Stock
        stock_val = rec.get("stock") or 0
        # Visibilidad: Visible por defecto
        vis = "Visible"
        # Descripción
        descripcion = rec.get("description_html") or ""
        # Medidas
        weight_kg = rec.get("weight_kg")
        height_cm = rec.get("height_cm")
        width_cm = rec.get("width_cm")
        depth_cm = rec.get("depth_cm")
        # Categoría jerárquica
        can_subcat_id = rec.get("canonical_subcategory_id")
        can_cat_id = rec.get("canonical_category_id")
        if can_subcat_id:
            cat_path = await _category_path(session, can_subcat_id)
        elif can_cat_id:
            cat_path = await _category_path(session, can_cat_id)
        else:
            cat_path = await _category_path(session, rec.get("category_id"))

        ws.append([
            sku,
            name,
            float(precio) if precio is not None else None,
            "",  # Oferta (vacío)
            int(stock_val),
            vis,
            descripcion,
            weight_kg if weight_kg is not None else None,
            height_cm if height_cm is not None else None,
            width_cm if width_cm is not None else None,
            depth_cm if depth_cm is not None else None,
            "", "",  # Variante #1
            "", "",  # Variante #2
            "", "",  # Variante #3
            cat_path or "",
        ])

    # Serializar
    buf = BytesIO()
    wb.save(buf)
    buf.seek(0)
    headers = {"Content-Disposition": "attachment; filename=productos_tiendanegocio.xlsx"}
    try:
        cid = request.headers.get("x-correlation-id") or request.headers.get("x-request-id")
        if cid:
            headers["X-Correlation-Id"] = cid
    except Exception:
        pass
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
    dependencies=[Depends(require_roles("guest", "cliente", "proveedor", "colaborador", "admin"))],
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
                    canonical_name = stylize_product_name(cp.name)
    except Exception:
        pass
    cat_path = await _category_path(session, prod.category_id)
    # Convertir numéricos Decimal -> float para JSON
    weight_kg = float(prod.weight_kg) if getattr(prod, "weight_kg", None) is not None else None
    height_cm = float(prod.height_cm) if getattr(prod, "height_cm", None) is not None else None
    width_cm = float(prod.width_cm) if getattr(prod, "width_cm", None) is not None else None
    depth_cm = float(prod.depth_cm) if getattr(prod, "depth_cm", None) is not None else None
    market_price_reference = (
        float(prod.market_price_reference) if getattr(prod, "market_price_reference", None) is not None else None
    )
    # Título preferido para UI: title_canonical (si existe) o canonical_name; si no, product.title
    # Aplicar estilización Title Case
    preferred_title = None
    try:
        preferred_title = stylize_product_name(getattr(prod, "title_canonical", None) or None)
    except Exception:
        preferred_title = None
    if not (preferred_title or "").strip():
        preferred_title = canonical_name or stylize_product_name(prod.title)

    # Obtener precio de venta del proveedor como fallback
    supplier_sale_price = None
    try:
        sp_row = (await session.execute(
            select(SupplierProduct.current_sale_price)
            .where(SupplierProduct.internal_product_id == product_id)
            .where(SupplierProduct.current_sale_price.is_not(None))
            .order_by(SupplierProduct.last_seen_at.desc().nulls_last())
            .limit(1)
        )).scalar_one_or_none()
        if sp_row is not None:
            supplier_sale_price = float(sp_row)
    except Exception:
        pass # No bloquear si falla

    # Precio de venta final: priorizar canónico, luego proveedor
    sale_price = canonical_sale if canonical_sale is not None else supplier_sale_price

    return {
        "id": prod.id,
        "title": stylize_product_name(prod.title),
        "preferred_title": preferred_title,
        "slug": prod.slug,
        "stock": prod.stock,
        "sku_root": prod.sku_root,
        "category_path": cat_path,
        "description_html": prod.description_html,
        "enrichment_sources_url": getattr(prod, "enrichment_sources_url", None),
        "last_enriched_at": (getattr(prod, "last_enriched_at", None).isoformat() if getattr(prod, "last_enriched_at", None) else None),
        "enriched_by": getattr(prod, "enriched_by", None),
        "weight_kg": weight_kg,
        "height_cm": height_cm,
        "width_cm": width_cm,
        "depth_cm": depth_cm,
        "market_price_reference": market_price_reference,
        "canonical_product_id": canonical_id,
        "canonical_sale_price": canonical_sale,
        "supplier_sale_price": supplier_sale_price,
        "sale_price": sale_price,
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
    weight_kg: float | None = None
    height_cm: float | None = None
    width_cm: float | None = None
    depth_cm: float | None = None
    market_price_reference: float | None = None


class ProductsDeleteRequest(BaseModel):
    ids: List[int]
    hard: bool = False  # futuro: permitir soft-delete si se agrega flag


class EnrichMultipleRequest(BaseModel):
    ids: List[int]
    force: bool | None = False


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
    # Validaciones y asignaciones de campos técnicos
    def _nonneg_or_none(val, name: str):
        if val is None:
            return None
        try:
            f = float(val)
        except Exception:
            raise HTTPException(status_code=400, detail=f"{name} debe ser numérico")
        if f < 0:
            raise HTTPException(status_code=400, detail=f"{name} no puede ser negativo")
        return f

    if "weight_kg" in data:
        v = _nonneg_or_none(data["weight_kg"], "weight_kg")
        prod.weight_kg = v
    if "height_cm" in data:
        v = _nonneg_or_none(data["height_cm"], "height_cm")
        prod.height_cm = v
    if "width_cm" in data:
        v = _nonneg_or_none(data["width_cm"], "width_cm")
        prod.width_cm = v
    if "depth_cm" in data:
        v = _nonneg_or_none(data["depth_cm"], "depth_cm")
        prod.depth_cm = v
    if "market_price_reference" in data:
        v = _nonneg_or_none(data["market_price_reference"], "market_price_reference")
        prod.market_price_reference = v
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


@router.post(
    "/products/enrich-multiple",
    dependencies=[Depends(require_csrf), Depends(require_roles("admin", "colaborador"))],
)
async def enrich_multiple_products(
    payload: EnrichMultipleRequest,
    session: AsyncSession = Depends(get_session),
    request: Request = None,
    sess: SessionData = Depends(current_session),
) -> dict:
    """Encola/ejecuta enriquecimiento para múltiples productos.

    Reglas:
    - Máximo 20 IDs por solicitud.
    - Se ignoran productos sin título.
    - Si `force` es False, se omiten productos ya enriquecidos (description o fuentes).
    - Reutiliza el flujo de `enrich_product` (ejecución inline para MVP).
    """
    ids = list(dict.fromkeys(payload.ids or []))
    if not ids:
        raise HTTPException(status_code=400, detail="ids requerido")
    if len(ids) > 20:
        raise HTTPException(status_code=400, detail="Máximo 20 productos por lote")

    enriched = 0
    skipped = 0
    errors: list[int] = []
    for pid in ids:
        prod = await session.get(Product, pid)
        if not prod:
            skipped += 1
            continue

        # Chequear si ya está en proceso de enriquecimiento
        if getattr(prod, 'is_enriching', False):
            errors.append(pid)
            continue

        title_ok = bool((prod.title or '').strip())
        if not title_ok:
            skipped += 1
            continue
        already = bool((prod.enrichment_sources_url or '').strip()) or bool((prod.description_html or '').strip())
        if already and not payload.force:
            skipped += 1
            continue
        try:
            # reusar la lógica existente
            await enrich_product(pid, session=session, request=request, sess=sess, force=bool(payload.force))
            enriched += 1
        except HTTPException as e:
            # Si el error es 409 (conflicto), significa que el bloqueo se activó entre el chequeo y la ejecución
            if e.status_code == 409:
                skipped += 1
            errors.append(pid)
            continue
        except Exception:
            errors.append(pid)
            # continuar con el siguiente sin abortar lote
            continue

    # Audit resumen de lote
    try:
        session.add(
            AuditLog(
                action="bulk_enrich",
                table="products",
                entity_id=None,
                meta={
                    "requested": len(ids),
                    "enriched": enriched,
                    "skipped": skipped,
                    "errors": errors,
                    "ids": ids,
                },
                user_id=sess.user.id if sess and sess.user else None,
                ip=(request.client.host if request and request.client else None),
            )
        )
        await session.commit()
    except Exception:
        pass

    return {"enriched": enriched, "skipped": skipped, "errors": errors}


@router.get(
    "/debug/enrich/{product_id}",
    dependencies=[Depends(require_roles("admin"))],
)
async def debug_enrich_product(
    product_id: int,
    session: AsyncSession = Depends(get_session),
    request: Request = None,
    sess: SessionData = Depends(current_session),
) -> dict:
    """Endpoint de diagnóstico para el flujo de enriquecimiento.

    No persiste cambios. Devuelve:
    - título elegido (incluye preferencia canónica si aplica)
    - proveedor IA seleccionado y flags relevantes
    - estado de salud del MCP web-search (si está habilitado)
    - prompt generado
    - vista previa de la respuesta de IA (sin parsear)
    """
    prod = await session.get(Product, product_id)
    if not prod:
        raise HTTPException(status_code=404, detail="Producto no encontrado")

    # Elegir título (preferir canónico): title_canonical -> CanonicalProduct.name por canonical_sku -> product.title
    title = (getattr(prod, "title_canonical", None) or "").strip()
    used_canonical_title = False
    if title:
        used_canonical_title = True
    else:
        try:
            if getattr(prod, "canonical_sku", None):
                cp = (
                    await session.execute(
                        select(CanonicalProduct).where(
                            or_(
                                CanonicalProduct.sku_custom == prod.canonical_sku,
                                CanonicalProduct.ng_sku == prod.canonical_sku,
                            )
                        )
                    )
                ).scalars().first()
                if cp and (cp.name or "").strip():
                    title = cp.name.strip()
                    used_canonical_title = True
        except Exception:
            pass
    if not title:
        title = (prod.title or "").strip()

    # Armar prompt base (mismo que enrich_product)
    schema_hint = (
        "{"
        "\"Título del Producto\": string, "
        "\"Descripción para Nice Grow\": string, "
        "\"Peso KG\": number|null, "
        "\"Alto CM\": number|null, "
        "\"Ancho CM\": number|null, "
        "\"Profundidad CM\": number|null, "
        "\"Valor de mercado estimado\": string|null, "
        "\"Fuentes\": object|null  "
        "}"
    )
    prompt = (
        "Eres GrowMaster, un asistente de marketing de productos para jardinería y growshops. "
        "Responde ÚNICAMENTE en JSON válido (sin texto extra, sin markdown, sin ```). "
        "Completa el siguiente esquema con la mejor información posible, usando tono claro y útil, español latino neutro.\n\n"
        f"Producto: {title}\n\n"
        f"Esquema: {schema_hint}\n\n"
        "Reglas: \n"
        "- Si no estás seguro de un valor numérico, usa null.\n"
        "- No inventes datos técnicos; prioriza precisión.\n"
        "- La 'Descripción para Nice Grow' debe ser breve (2-4 oraciones), clara y orientada a clientes.\n"
        "- Incluir un breve 'Análisis de Mercado (AR$)' resumido dentro de 'Valor de mercado estimado' cuando sea aplicable.\n"
        "- Si dispones de fuentes o referencias, incluye un objeto 'Fuentes' con claves descriptivas y valores URL (http/https)."
    )

    # Contexto MCP (productos) y salud de web-search
    extra_context = None
    web_health = "disabled"
    web_query = None
    web_hits = 0
    web_search_results = None
    try:
        fv = (
            await session.execute(
                select(Variant.sku).where(Variant.product_id == product_id).order_by(Variant.id.asc()).limit(1)
            )
        ).scalar_one_or_none()
        role = getattr(getattr(sess, 'user', None), 'role', 'colaborador') or 'colaborador'
        provider = OpenAIProvider()
        if fv:
            ctx = await provider.call_mcp_tool(tool_name="get_product_info", parameters={"sku": str(fv), "user_role": role})
            if isinstance(ctx, dict) and ctx:
                extra_context = ctx
                try:
                    import json as _json
                    prompt += "\n\nContexto interno (MCP):\n" + _json.dumps(extra_context, ensure_ascii=False)
                except Exception:
                    pass
        # Web-search si está habilitado
        import os as _os
        use_web = (_os.getenv("AI_USE_WEB_SEARCH", "0").lower() in {"1", "true", "yes"}) and settings.ai_allow_external
        if use_web:
            web_health = "unknown"
            try:
                import httpx as _httpx
                mcp_url = _os.getenv("MCP_WEB_SEARCH_URL", "http://mcp_web_search:8002/invoke_tool")
                health_url = mcp_url.replace("/invoke_tool", "/health")
                async with _httpx.AsyncClient(timeout=2.0) as _cli:
                    _h = await _cli.get(health_url)
                    web_health = "ok" if _h.status_code == 200 else f"bad_status_{_h.status_code}"
            except Exception:
                web_health = "unhealthy"
            if web_health == "ok":
                web_query = title
                try:
                    wres = await provider.call_mcp_web_tool(tool_name="search_web", parameters={"query": web_query, "user_role": role, "max_results": int(_os.getenv("AI_WEB_SEARCH_MAX_RESULTS", "3"))})
                    if isinstance(wres, dict) and wres:
                        items = wres.get("items") or []
                        if isinstance(items, list):
                            web_hits = len(items)
                        web_search_results = wres
                        try:
                            import json as _json
                            prompt += "\n\nBúsqueda web (MCP) - top resultados:\n" + _json.dumps(web_search_results, ensure_ascii=False)
                        except Exception:
                            pass
                except Exception:
                    web_search_results = {"error": "web_search_failed"}
    except Exception:
        pass

    # Provider seleccionado (sin ejecutar cambios)
    router_ai = AIRouter(settings)
    provider_obj = router_ai.get_provider(Task.REASONING.value)
    provider_name = getattr(provider_obj, "name", type(provider_obj).__name__)

    # Ejecutar una llamada de prueba (no persistente) y devolver texto crudo
    try:
        raw = router_ai.run(Task.REASONING.value, prompt)
    except Exception as _e:
        raw = f"<error: {type(_e).__name__}>"

    # Normalización previa de fences y prefijos para test de parseabilidad
    preview = (raw or "")
    norm = preview.strip()
    if norm.startswith("openai:") or norm.startswith("ollama:"):
        norm = norm.split(":", 1)[1].strip()
    if norm.startswith("```"):
        norm = norm.strip("`\n ")
        if norm.lower().startswith("json"):
            norm = norm[4:].strip()
    import json as _json
    will_parse = True
    try:
        _ = _json.loads(norm)
    except Exception:
        will_parse = False

    return {
        "product_id": product_id,
        "title": title,
        "title_used": title,  # alias explícito para claridad de UI/diagnóstico
        "used_canonical_title": used_canonical_title,
        "ai_allow_external": settings.ai_allow_external,
        "ai_provider_selected": provider_name,
        "web_search": {"enabled": bool(web_health != "disabled"), "health": web_health, "query": web_query, "hits": web_hits},
        "prompt": prompt,
        "raw_ai_preview": preview[:1200],
        "raw_ai_looks_json": will_parse,
    }


@router.post(
    "/products/{product_id}/enrich",
    dependencies=[Depends(require_csrf), Depends(require_roles("admin", "colaborador"))],
)
async def enrich_product(
    product_id: int,
    session: AsyncSession = Depends(get_session),
    request: Request = None,
    sess: SessionData = Depends(current_session),
    force: bool = Query(False),
) -> dict:
    """Enriquece un producto usando IA (OpenAI/Ollama vía AIRouter).

    - Requiere rol admin o colaborador.
    - Valida existencia del producto y título.
    - Construye un prompt que solicita JSON con claves conocidas.
    - Actualiza ``description_html`` si viene en la respuesta.
    - Registra ``AuditLog`` con acción ``enrich_ai``.
    """
    prod = await session.get(Product, product_id)
    if not prod:
        raise HTTPException(status_code=404, detail="Producto no encontrado")

    print(f"ENTERING ENRICH: {product_id}, is_enriching: {getattr(prod, 'is_enriching', 'NOT_FOUND')}") # DEBUG

    if getattr(prod, 'is_enriching', False):
        print(f"CONFLICT DETECTED: {product_id}") # DEBUG
        raise HTTPException(status_code=409, detail="El producto ya está siendo enriquecido. Intente de nuevo en unos momentos.")

    # --- Inicio: Lógica de selección de título para enriquecimiento ---
    # Prioridad:
    # 1. Título del producto canónico (buscado vía ProductEquivalence).
    # 2. Fallback: Título del producto de proveedor (`product.title`).
    title = ""
    used_canonical_title = False
    canonical_product_id = None
    import logging as _logging
    logger = _logging.getLogger("growen")

    try:
        # Buscar el ID del canónico a través de la tabla de equivalencia, como en get_product
        sp_equiv_rows = (await session.execute(
            select(ProductEquivalence.canonical_product_id)
            .join(SupplierProduct, SupplierProduct.id == ProductEquivalence.supplier_product_id)
            .where(SupplierProduct.internal_product_id == product_id)
            .limit(1)
        )).scalars().all()

        if sp_equiv_rows:
            canonical_product_id = sp_equiv_rows[0]
            if canonical_product_id:
                cp = await session.get(CanonicalProduct, canonical_product_id)
                if cp and (cp.name or "").strip():
                    title = cp.name.strip()
                    used_canonical_title = True
    except Exception as e:
        logger.warning({
            "event": "enrich.choose_title.error",
            "product_id": product_id,
            "reason": "Error al buscar producto canónico",
            "error": str(e),
        })

    # Fallback al título del producto si no se encontró un título canónico válido
    if not title:
        title = (prod.title or "").strip()

    logger.info({
        "event": "enrich.choose_title",
        "product_id": product_id,
        "title_selected": title,
        "used_canonical_title": used_canonical_title,
        "canonical_product_id_found": canonical_product_id,
        "fallback_to_product_title": not used_canonical_title,
    })
    # --- Fin: Lógica de selección de título ---

    if not title:
        raise HTTPException(status_code=400, detail="El producto no tiene título definido")

    # Adquirir el bloqueo de forma atómica a nivel DB para evitar carreras entre requests
    upd = (
        update(Product)
        .where(Product.id == product_id, Product.is_enriching == False)  # noqa: E712
        .values(is_enriching=True)
    )
    res = await session.execute(upd)
    await session.commit()
    if res.rowcount == 0:
        # Otro proceso ganó el lock
        raise HTTPException(status_code=409, detail="El producto ya está siendo enriquecido. Intente de nuevo en unos momentos.")

    generated_fields = []
    txt_url = None

    try:
        # Intento opcional de obtener datos internos vía MCP (SKU de la primera variante)
        extra_context = None
        web_search_results = None
        web_hits = 0
        web_query = None
        
        # Obtener datos internos del producto (no bloquea búsqueda web)
        try:
            fv = (await session.execute(select(Variant.sku).where(Variant.product_id == product_id).order_by(Variant.id.asc()).limit(1))).scalar_one_or_none()
            if fv:
                role = getattr(getattr(sess, 'user', None), 'role', 'colaborador') or 'colaborador'
                provider = OpenAIProvider()
                res = await provider.call_mcp_tool(tool_name="get_product_info", parameters={"sku": str(fv), "user_role": role})
                if isinstance(res, dict) and res:
                    extra_context = res
        except Exception as e:
            logger.warning({
                "event": "enrich.mcp_products.failed",
                "product_id": product_id,
                "error": str(e),
                "message": "Failed to fetch internal product context. Continuing with web search.",
            })
        
        # ========== BÚSQUEDA WEB OBLIGATORIA ==========
        # La búsqueda web es SIEMPRE necesaria según especificaciones del usuario
        import os as _os, json as _json
        use_web = (_os.getenv("AI_USE_WEB_SEARCH", "0").lower() in {"1", "true", "yes"}) and settings.ai_allow_external
        
        if not use_web:
            logger.error({
                "event": "enrich.web_search.disabled",
                "product_id": product_id,
                "AI_USE_WEB_SEARCH": _os.getenv("AI_USE_WEB_SEARCH", "0"),
                "AI_ALLOW_EXTERNAL": settings.ai_allow_external,
            })
            raise HTTPException(
                status_code=500,
                detail="La búsqueda web es obligatoria para el enriquecimiento pero está deshabilitada. Verificar AI_USE_WEB_SEARCH y AI_ALLOW_EXTERNAL."
            )
        
        logger.info({"event": "enrich.web_search.start", "product_id": product_id})
        
        # Health check del servicio MCP Web Search
        import httpx as _httpx
        mcp_url = _os.getenv("MCP_WEB_SEARCH_URL", "http://mcp_web_search:8002/invoke_tool")
        health_url = mcp_url.replace("/invoke_tool", "/health")
        web_health = "unknown"
        
        try:
            async with _httpx.AsyncClient(timeout=5.0) as _cli:
                _h = await _cli.get(health_url)
                if _h.status_code == 200:
                    web_health = "ok"
                else:
                    web_health = f"bad_status_{_h.status_code}"
        except Exception as e:
            web_health = "unhealthy"
            logger.error({
                "event": "enrich.web_search.health_check_failed",
                "product_id": product_id,
                "mcp_url": health_url,
                "error": str(e),
            })
        
        logger.info({
            "event": "enrich.web_search.health_check_result",
            "product_id": product_id,
            "status": web_health,
        })
        
        if web_health != "ok":
            raise HTTPException(
                status_code=502,
                detail=f"El servicio de búsqueda web no está disponible (status: {web_health}). No se puede enriquecer sin búsqueda web."
            )
        
        # Ejecutar búsqueda web OBLIGATORIA
        web_query = title
        role = getattr(getattr(sess, 'user', None), 'role', 'colaborador') or 'colaborador'
        provider = OpenAIProvider()
        
        try:
            wres = await provider.call_mcp_web_tool(
                tool_name="search_web",
                parameters={
                    "query": web_query,
                    "user_role": role,
                    "max_results": int(_os.getenv("AI_WEB_SEARCH_MAX_RESULTS", "5"))
                }
            )
            if isinstance(wres, dict) and wres:
                items = wres.get("items") or []
                if isinstance(items, list):
                    web_hits = len(items)
                web_search_results = wres
                logger.info({
                    "event": "enrich.web_search.success",
                    "product_id": product_id,
                    "query": web_query,
                    "hits": web_hits,
                    "with_sources": bool(items),
                })
            else:
                raise ValueError("Web search returned empty or invalid response")
        except Exception as e:
            logger.error({
                "event": "enrich.web_search.execution_failed",
                "product_id": product_id,
                "query": web_query,
                "error": str(e),
            })
            raise HTTPException(
                status_code=502,
                detail=f"Error al ejecutar búsqueda web: {str(e)}"
            )

        # Prompt de enriquecimiento con instrucciones detalladas del usuario
        schema_hint = (
            "{"
            "\"Título del Producto\": string, "
            "\"Descripción para Nice Grow\": string, "
            "\"Peso KG\": number|null, "
            "\"Alto CM\": number|null, "
            "\"Ancho CM\": number|null, "
            "\"Profundidad CM\": number|null, "
            "\"Valor de mercado estimado\": string|null, "
            "\"Fuentes\": object  "
            "}"
        )
        
        from datetime import datetime as _dt, timedelta as _td
        fecha_actual = _dt.now().strftime("%Y-%m-%d")
        fecha_limite_precios = (_dt.now() - _td(days=120)).strftime("%Y-%m-%d")
        
        prompt = (
            f"Eres GrowMaster, un experto asistente de marketing especializado en productos para jardinería y cultivo en Argentina.\n\n"
            f"FECHA ACTUAL: {fecha_actual}\n"
            f"PRODUCTO A ENRIQUECER: {title}\n\n"
            "========== INSTRUCCIONES OBLIGATORIAS ==========\n\n"
            "### Tarea 1: Investigación y Verificación de Datos\n\n"
            "Búsqueda Exhaustiva: Realiza una búsqueda en internet utilizando el título del producto proporcionado. "
            "Tu búsqueda debe centrarse en encontrar fuentes de Argentina.\n\n"
            "Jerarquía de Fuentes (Regla de Oro): Debes priorizar las fuentes de información en el siguiente orden estricto de veracidad:\n\n"
            "- Prioridad #1: El sitio web oficial del fabricante del producto.\n"
            "- Prioridad #2: Publicaciones en marketplaces importantes de Argentina (ej. Mercado Libre).\n"
            "- Prioridad #3: Páginas de otros grow shops o vendedores online de Argentina.\n\n"
            "Resolución de Conflictos: Si encuentras datos contradictorios entre diferentes fuentes (ej. dimensiones, composición), "
            "siempre deberás usar la información de la fuente con la prioridad más alta (el fabricante es la verdad absoluta). "
            "No menciones la existencia de la discrepancia, simplemente presenta el dato correcto.\n\n"
            "### Tarea 2: Generación de Contenido\n\n"
            "Basado en la información recopilada, genera:\n\n"
            "**Descripción del producto:**\n"
            "- Máximo 500 palabras.\n"
            "- Tono y Estilo: Utiliza un lenguaje amigable, informal y directo con \"voseo\" argentino. "
            "El objetivo es conectar con el cultivador. Inspírate en este ejemplo de tono: "
            "\"con este Fertilizante tus plantas van a ser la envidia de los claveles de tu vecina, rico en NPK en las siguientes proporciones 15-5-40, ideal para el estado vegetativo\".\n"
            "- Contenido: La descripción debe ser atractiva, resaltar los beneficios clave para el cultivador y explicar para qué sirve el producto de manera clara.\n"
            "- ESTRUCTURA OBLIGATORIA DE LA DESCRIPCIÓN:\n"
            "  1. Párrafo principal: Beneficios y características del producto (3-5 oraciones)\n"
            "  2. Párrafo secundario: Modo de uso, aplicación, recomendaciones (2-4 oraciones)\n"
            "  3. Cierre con 5 keywords: DEBES terminar la descripción con EXACTAMENTE 5 palabras clave separadas por comas.\n"
            "     - NO uses prefijos como 'Keywords:', 'Palabras clave:', 'SEO:', etc.\n"
            "     - Simplemente agrega un espacio después del último punto de tu texto y lista las 5 palabras separadas por comas.\n"
            "     - Ejemplo: '...ideal para cultivos en interior. fertilizante líquido, bloom estimulador, floración cannabis, top crop argentina, abono floración'\n\n"
            "**Datos Técnicos (Opcional):**\n"
            "Si encuentras esta información durante tu investigación, complétala. Si no la encuentras, usa null:\n"
            "- Peso KG: [Valor numérico o null]\n"
            "- Alto CM: [Valor numérico o null]\n"
            "- Ancho CM: [Valor numérico o null]\n"
            "- Profundidad CM: [Valor numérico o null]\n\n"
            "**Análisis de Mercado (AR$):**\n"
            "- Busca precios del producto en Pesos Argentinos (AR$) de fuentes argentinas.\n"
            f"- Filtro de Actualidad: Solo considera precios de fuentes con una antigüedad máxima de 4 meses (posteriores a {fecha_limite_precios}).\n"
            "- Presentación del Precio:\n"
            "  * Si encuentras un solo precio válido: \"Valor de mercado estimado: $[Precio] ARS\"\n"
            "  * Si encuentras múltiples precios válidos: \"Valor de mercado estimado: $[Precio Mínimo] a $[Precio Máximo] ARS\"\n"
            "  * Advertencia de Desactualización: Si la única fuente de precio disponible tiene más de 4 meses de antigüedad, "
            "debes incluirla pero con esta advertencia OBLIGATORIA: \"ADVERTENCIA: Precio con más de 4 meses de antigüedad, probablemente desactualizado.\"\n\n"
            "**Fuentes (OBLIGATORIO):**\n"
            "- Debes incluir TODAS las fuentes consultadas en un objeto donde:\n"
            "  * La clave es una descripción corta de la fuente (ej: \"Sitio oficial fabricante\", \"Mercado Libre\", \"Grow Shop ABC\")\n"
            "  * El valor es la URL completa (http/https)\n"
            "- Indica claramente cuáles son del fabricante (prioridad #1) vs marketplaces (prioridad #2) vs grow shops (prioridad #3)\n\n"
            "========== FORMATO DE RESPUESTA ==========\n\n"
            "Responde ÚNICAMENTE en JSON válido (sin texto extra, sin markdown, sin ```). "
            f"Completa el siguiente esquema:\n\n{schema_hint}\n\n"
            "RECORDATORIO CRÍTICO: La 'Descripción para Nice Grow' DEBE terminar con las 5 palabras clave separadas por comas (sin prefijos como 'Keywords:').\n"
            "El campo 'Fuentes' es OBLIGATORIO y debe contener al menos las URLs de donde obtuviste la información.\n"
        )
        
        if extra_context:
            try:
                import json as _json
                prompt += "\n\n========== CONTEXTO INTERNO (MCP Productos) ==========\n" + _json.dumps(extra_context, ensure_ascii=False, indent=2)
            except Exception:
                pass
        
        if web_search_results:
            try:
                import json as _json
                prompt += "\n\n========== RESULTADOS DE BÚSQUEDA WEB (MCP Web Search) ==========\n" + _json.dumps(web_search_results, ensure_ascii=False, indent=2)
            except Exception:
                pass

        router_ai = AIRouter(settings)
        raw = router_ai.run(Task.REASONING.value, prompt)
        
        # Normalizar respuesta posible con prefijo y/o fences
        text = raw.strip()
        
        # Log para debugging: ver primeros 300 caracteres de la respuesta cruda
        logger.debug({
            "event": "enrich.raw_response",
            "product_id": product_id,
            "preview": text[:300],
            "has_encoding_markers": any(char in text for char in ['├', '┬', '®', '¡'])
        })
        
        # Fix encoding issues: ensure UTF-8 correctness
        # Sometimes OpenAI returns text with encoding issues
        try:
            # Try to encode as latin-1 and decode as utf-8 if it looks corrupted
            if '├' in text or '┬' in text:
                text = text.encode('latin-1').decode('utf-8')
                logger.info({
                    "event": "enrich.encoding_fixed_pre_parse",
                    "product_id": product_id,
                    "message": "Applied latin-1 to UTF-8 conversion to raw response"
                })
        except Exception as e:
            logger.warning({
                "event": "enrich.encoding_fix_failed_pre_parse",
                "product_id": product_id,
                "error": str(e)
            })
        
        if text.startswith("openai:") or text.startswith("ollama:"):
            text = text.split(":", 1)[1].strip()
        if text.startswith("```"):
            text = text.strip("`\n ")
            if text.lower().startswith("json"):
                text = text[4:].strip()

        import json
        try:
            data = json.loads(text)
        except Exception:
            _logging.getLogger("growen").warning({
                "event": "enrich.error",
                "product_id": product_id,
                "reason": "invalid_json",
                "preview": text[:200],
            })
            raise HTTPException(status_code=502, detail="Respuesta de IA inválida (no JSON)")

        desc_key = "Descripción para Nice Grow"
        if desc_key not in data or not isinstance(data.get(desc_key), str) or not data.get(desc_key).strip():
            _logging.getLogger("growen").warning({
                "event": "enrich.error",
                "product_id": product_id,
                "reason": "missing_description",
            })
            raise HTTPException(status_code=502, detail="Respuesta de IA inválida (falta descripción)")
        
        # Validar que las Fuentes estén presentes (OBLIGATORIO según especificaciones)
        if "Fuentes" not in data or not isinstance(data.get("Fuentes"), dict) or not data.get("Fuentes"):
            _logging.getLogger("growen").warning({
                "event": "enrich.error",
                "product_id": product_id,
                "reason": "missing_sources",
                "response_keys": list(data.keys()),
            })
            raise HTTPException(status_code=502, detail="Respuesta de IA inválida (falta campo 'Fuentes' obligatorio)")

        old_desc = getattr(prod, "description_html", None) or ""
        had_enrichment = bool((prod.enrichment_sources_url or '').strip()) or bool((old_desc or '').strip())
        
        # Obtener descripción y corregir encoding UTF-8 si es necesario
        description = data.get(desc_key).strip()
        
        # Fix encoding issues: sometimes OpenAI returns text with latin-1 encoding interpreted as UTF-8
        try:
            if any(char in description for char in ['├', '┬', '®', '¡', '¢', '£', '▒', '│', '┤', '╡']):
                description = description.encode('latin-1').decode('utf-8')
        except Exception as e:
            # If conversion fails, keep original
            logger.warning({
                "event": "enrich.encoding_fix_failed",
                "product_id": product_id,
                "error": str(e),
            })
        
        prod.description_html = description

        # Mapear campos técnicos si vienen en la respuesta
        def _to_float_or_none(x):
            if x is None:
                return None
            if isinstance(x, (int, float)):
                return float(x)
            if isinstance(x, str):
                # extraer primer número en el string (e.g., "$ 12.345,67" o "12.3 cm")
                import re
                s = x.replace(".", "").replace(",", ".") if "," in x and x.count(",") == 1 and x.count(".") > 1 else x
                m = re.search(r"-?\d+(?:[\.,]\d+)?", s)
                if m:
                    try:
                        return float(m.group(0).replace(",", "."))
                    except Exception:
                        return None
            return None

        generated_fields = ["description_html"]
        # Claves del JSON de IA
        kg = _to_float_or_none(data.get("Peso KG"))
        alto = _to_float_or_none(data.get("Alto CM"))
        ancho = _to_float_or_none(data.get("Ancho CM"))
        prof = _to_float_or_none(data.get("Profundidad CM"))
        mref = _to_float_or_none(data.get("Valor de mercado estimado"))
        try:
            if kg is not None and kg >= 0:
                prod.weight_kg = kg
                generated_fields.append("weight_kg")
            if alto is not None and alto >= 0:
                prod.height_cm = alto
                generated_fields.append("height_cm")
            if ancho is not None and ancho >= 0:
                prod.width_cm = ancho
                generated_fields.append("width_cm")
            if prof is not None and prof >= 0:
                prod.depth_cm = prof
                generated_fields.append("depth_cm")
            if mref is not None and mref >= 0:
                prod.market_price_reference = mref
                generated_fields.append("market_price_reference")
        except Exception:
            pass

        # Manejar fuentes -> generar .txt en MEDIA_ROOT/enrichment_logs y asociar URL pública /media/...
        sources = None
        try:
            # aceptar 'Fuentes' como dict o list de strings
            if isinstance(data.get("Fuentes"), dict):
                sources = data.get("Fuentes")
            elif isinstance(data.get("Fuentes"), list):
                # convertir a dict numerado
                lst = [str(x) for x in data.get("Fuentes")]
                sources = {f"item_{i+1}": url for i, url in enumerate(lst)}
        except Exception:
            sources = None

        # Construcción de archivo si hay fuentes
        txt_url = None
        try:
            if sources:
                ROOT = Path(__file__).resolve().parents[2]  # services/routers -> services -> ROOT
                media_root = Path(os.getenv("MEDIA_ROOT", str(ROOT / "Devs" / "Imagenes")))
                # Si viene force y existe un archivo previo, eliminarlo
                if force and getattr(prod, "enrichment_sources_url", None):
                    prev_url = str(prod.enrichment_sources_url)
                    if prev_url.startswith("/media/"):
                        rel = prev_url[len("/media/"):]
                        prev_path = media_root / rel
                        try:
                            if prev_path.exists():
                                prev_path.unlink()
                        except Exception:
                            pass
                target_dir = media_root / "enrichment_logs"
                target_dir.mkdir(parents=True, exist_ok=True)
                from datetime import datetime as _dt
                ts = _dt.utcnow().strftime("%Y%m%dT%H%M%SZ")
                fname = f"product_{product_id}_enrichment_{ts}.txt"
                fpath = target_dir / fname
                lines = [
                    "FUENTES CONSULTADAS - Enriquecimiento IA",
                    "",
                    f"Producto: {title}",
                    f"Fecha: {ts}",
                    f"Responsable: {sess.user.id if (sess and sess.user) else 'automático'}",
                    "",
                ]
                for k, v in (sources or {}).items():
                    lines.append(f"--- {k}:")
                    lines.append(str(v))
                    lines.append("")
                fpath.write_text("\n".join(lines), encoding="utf-8")
                # URL pública
                txt_url = f"/media/enrichment_logs/{fname}"
                # Persistir en producto
                if hasattr(prod, "enrichment_sources_url"):
                    prod.enrichment_sources_url = txt_url
            # setear metadatos de trazabilidad de enriquecimiento
            try:
                if hasattr(prod, "last_enriched_at"):
                    prod.last_enriched_at = _dt.utcnow()
                if hasattr(prod, "enriched_by"):
                    prod.enriched_by = (sess.user.id if sess and getattr(sess, 'user', None) else None)
            except Exception:
                pass
        except Exception:
            # No bloquear si falla escritura
            pass

        # Audit (antes del commit final)
        prompt_hash = hashlib.sha256(prompt.encode("utf-8")).hexdigest()
        session.add(
            AuditLog(
                action=("reenrich" if (force or had_enrichment) else "enrich"),
                table="products",
                entity_id=product_id,
                meta={
                    "fields_generated": generated_fields,
                    "desc_len_old": len(old_desc or ""),
                    "desc_len_new": len(prod.description_html or ""),
                    "num_sources": (len(sources) if sources else 0),
                    "source_file": txt_url,
                    "prompt_hash": prompt_hash,
                    "web_search_query": web_query,
                    "web_search_hits": web_hits,
                    "used_canonical_title": used_canonical_title,
                },
                user_id=sess.user.id if sess and sess.user else None,
                ip=(request.client.host if request and request.client else None),
            )
        )

        # Logging final de resultado visible en consola
        _logging.getLogger("growen").info({
            "event": "enrich.done",
            "product_id": product_id,
            "used_canonical_title": used_canonical_title,
            "sources": bool(sources),
            "source_file": txt_url,
            "web_search_hits": web_hits,
        })
        
        # Commit principal con todos los datos y el log de auditoría
        await session.commit()

    finally:
        # Liberar el bloqueo
        prod_to_unlock = await session.get(Product, product_id)
        if prod_to_unlock:
            prod_to_unlock.is_enriching = False
            await session.commit()

    return {"status": "ok", "updated": True, "fields": generated_fields, "sources_url": txt_url}


@router.delete(
    "/products/{product_id}/enrichment",
    dependencies=[Depends(require_csrf), Depends(require_roles("admin", "colaborador"))],
)
async def delete_product_enrichment(
    product_id: int,
    session: AsyncSession = Depends(get_session),
    request: Request = None,
    sess: SessionData = Depends(current_session),
) -> dict:
    """Elimina los datos enriquecidos por IA para el producto.

    - Limpia description_html, campos técnicos y enrichment_sources_url.
    - Si existe el archivo .txt de fuentes en MEDIA_ROOT, lo borra.
    - Registra AuditLog con action "delete_enrichment".
    """
    prod = await session.get(Product, product_id)
    if not prod:
        raise HTTPException(status_code=404, detail="Producto no encontrado")

    # Borrar archivo de fuentes si existe
    file_deleted = False
    prev_url = getattr(prod, "enrichment_sources_url", None)
    try:
        if prev_url and isinstance(prev_url, str) and prev_url.startswith("/media/"):
            ROOT = Path(__file__).resolve().parents[2]
            media_root = Path(os.getenv("MEDIA_ROOT", str(ROOT / "Devs" / "Imagenes")))
            rel = prev_url[len("/media/"):]
            fpath = media_root / rel
            if fpath.exists():
                fpath.unlink()
                file_deleted = True
    except Exception:
        file_deleted = False

    # Limpiar campos enriquecidos
    cleared_fields = []
    if hasattr(prod, "description_html") and prod.description_html:
        prod.description_html = None
        cleared_fields.append("description_html")
    for fld in ["weight_kg", "height_cm", "width_cm", "depth_cm", "market_price_reference"]:
        if hasattr(prod, fld) and getattr(prod, fld) is not None:
            setattr(prod, fld, None)
            cleared_fields.append(fld)
    if hasattr(prod, "enrichment_sources_url") and prod.enrichment_sources_url:
        prod.enrichment_sources_url = None
        cleared_fields.append("enrichment_sources_url")
    # limpiar metadatos de enriquecimiento
    try:
        if hasattr(prod, "last_enriched_at") and getattr(prod, "last_enriched_at", None) is not None:
            prod.last_enriched_at = None
            cleared_fields.append("last_enriched_at")
        if hasattr(prod, "enriched_by") and getattr(prod, "enriched_by", None) is not None:
            prod.enriched_by = None
            cleared_fields.append("enriched_by")
    except Exception:
        pass

    await session.commit()

    # Audit
    try:
        session.add(
            AuditLog(
                action="delete_enrichment",
                table="products",
                entity_id=product_id,
                meta={
                    "product_title": getattr(prod, "title", None),
                    "file_deleted": file_deleted,
                    "prev_sources_url": prev_url,
                    "cleared_fields": cleared_fields,
                },
                user_id=sess.user.id if sess and sess.user else None,
                ip=(request.client.host if request and request.client else None),
            )
        )
        await session.commit()
    except Exception:
        pass

    return {"status": "ok", "deleted": True}


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
