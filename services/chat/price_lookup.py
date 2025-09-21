# NG-HEADER: Nombre de archivo: price_lookup.py
# NG-HEADER: Ubicación: services/chat/price_lookup.py
# NG-HEADER: Descripción: Utilidades para responder precios desde el chatbot
# NG-HEADER: Lineamientos: Ver AGENTS.md
"""Resolucion de precios para el intent del chatbot."""

from __future__ import annotations

import re
from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_UP
from typing import Iterable, List, Optional, Sequence, Tuple

from sqlalchemy import Select, and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from db.models import (
    AuditLog,
    CanonicalProduct,
    Product,
    ProductEquivalence,
    Supplier,
    SupplierProduct,
)

try:  # rapidfuzz es opcional pero preferido para ranking
    from rapidfuzz import fuzz, process  # type: ignore
except Exception:  # pragma: no cover - fallback sin rapidfuzz
    fuzz = None
    process = None


@dataclass
class PriceEntry:
    """Representa una coincidencia de precio para responder al usuario."""

    name: str
    price: Decimal
    currency: str
    source: str
    sku: Optional[str] = None
    supplier_name: Optional[str] = None
    canonical_id: Optional[int] = None
    supplier_item_id: Optional[int] = None
    product_id: Optional[int] = None

    def identity(self) -> Tuple[str, Optional[int]]:
        if self.canonical_id:
            return ("canonical", self.canonical_id)
        if self.supplier_item_id:
            return ("supplier", self.supplier_item_id)
        return ("entry", hash((self.name.lower(), float(self.price))))


@dataclass
class PriceLookupResult:
    status: str
    query: str
    entries: List[PriceEntry]
    missing_titles: List[str]

    def primary_entry(self) -> Optional[PriceEntry]:
        return self.entries[0] if self.entries else None


_PRICE_REGEXES = [
    re.compile(r"(?i)precio\s+(del|de la|de los|de las|de)?\s*(?P<name>.+)")
]


def _clean_candidate(value: str) -> str:
    value = value.strip()
    value = re.sub(r"[?!]", "", value)
    value = re.sub(r"\s{2,}", " ", value)
    value = re.sub(r"(?i)^(de|del|de la|de los|de las|el|la|los|las)\s+", "", value)
    return value.strip()


def extract_price_query(text: str) -> Optional[str]:
    """Intenta extraer el nombre del producto de una consulta de precio."""

    raw = text.strip()
    if not raw:
        return None
    lowered = raw.lower()
    if not any(word in lowered for word in ("precio", "cuanto", "cuánto", "vale", "cuesta", "valor")):
        return None
    for regex in _PRICE_REGEXES:
        match = regex.search(raw)
        if match and match.group("name"):
            candidate = match.group("name")
            candidate = _clean_candidate(candidate)
            candidate = re.sub(r"(?i)\b(cuesta|vale|sale)\b", "", candidate).strip()
            candidate = _clean_candidate(candidate)
            return candidate.strip()
    tokens = lowered
    for prefix in ("cuanto cuesta", "cuanto vale", "cuánto cuesta", "cuánto vale", "cuanto sale", "cuánto sale"):
        if tokens.startswith(prefix):
            trimmed = raw[len(prefix) :].strip()
            trimmed = re.sub(r"^(el|la|los|las)\s+", "", trimmed, flags=re.IGNORECASE)
            return _clean_candidate(trimmed)
    if "precio" in lowered:
        idx = lowered.rfind("precio")
        candidate = raw[idx + len("precio") :].strip()
        candidate = re.sub(r"^(de|del|de la|de los|de las)\s+", "", candidate, flags=re.IGNORECASE)
        return _clean_candidate(candidate)
    return None


async def resolve_price(
    query: str,
    db: AsyncSession,
    limit: int = 5,
) -> PriceLookupResult:
    """Busca precios relevantes para la cadena consultada."""

    clean = query.strip()
    if not clean:
        return PriceLookupResult("invalid", query, [], [])
    lowered = clean.lower()
    entries: List[PriceEntry] = []
    missing: List[str] = []
    seen = set()

    # 1) Coincidencias exactas de canónico (ng_sku)
    if len(clean) >= 2:
        stmt = select(CanonicalProduct).where(func.lower(CanonicalProduct.ng_sku) == lowered)
        canonicals = (await db.execute(stmt)).scalars().all()
        for canonical in canonicals:
            entry = await _canonical_to_entry(canonical, db)
            if entry:
                _append_entry(entries, seen, entry)
            else:
                missing.append(canonical.name)

    # 2) Coincidencias exactas de SKU interno (Product.sku_root)
    stmt = (
        select(Product, SupplierProduct, Supplier)
        .join(SupplierProduct, SupplierProduct.internal_product_id == Product.id)
        .join(Supplier, Supplier.id == SupplierProduct.supplier_id)
        .where(func.lower(Product.sku_root) == lowered)
    )
    rows = (await db.execute(stmt)).all()
    for product, supplier_product, supplier in rows:
        entry = _supplier_entry(supplier_product, supplier)
        if entry:
            entry.name = product.title
            entry.product_id = product.id
            _append_entry(entries, seen, entry)
        else:
            missing.append(product.title)

    # 3) Coincidencias exactas de SKU proveedor
    stmt = (
        select(SupplierProduct, Supplier)
        .join(Supplier, Supplier.id == SupplierProduct.supplier_id)
        .where(func.lower(SupplierProduct.supplier_product_id) == lowered)
    )
    rows = (await db.execute(stmt)).all()
    for supplier_product, supplier in rows:
        entry = _supplier_entry(supplier_product, supplier)
        if entry:
            _append_entry(entries, seen, entry)
        else:
            missing.append(supplier_product.title)

    # 4) Coincidencias por nombre (canónico) con fuzzy
    entries.extend(
        await _fuzzy_canonical_matches(clean, db, seen, missing, limit=max(3, limit))
    )

    # 5) Coincidencias por nombre (supplier product) con fuzzy
    entries.extend(
        await _fuzzy_supplier_matches(clean, db, seen, missing, limit=max(3, limit))
    )

    # Limitar cantidad final
    entries = entries[:limit]

    if entries:
        status = "ok" if len(entries) == 1 else "ambiguous"
    elif missing:
        status = "missing_price"
    else:
        status = "no_match"
    return PriceLookupResult(status, query, entries, missing)


async def log_price_lookup(
    db: AsyncSession,
    *,
    user_id: Optional[int],
    ip: Optional[str],
    original_text: str,
    extracted_query: Optional[str],
    result: PriceLookupResult,
) -> None:
    """Registra en AuditLog el resultado de una consulta de precio."""

    meta = serialize_result(result)
    meta["query_raw"] = original_text
    meta["query_extracted"] = extracted_query
    db.add(
        AuditLog(
            action="chat.price_lookup",
            table="chat",
            entity_id=None,
            meta=meta,
            user_id=user_id,
            ip=ip,
        )
    )
    await db.commit()



def serialize_entry(entry: PriceEntry) -> dict:
    return {
        "name": entry.name,
        "price": float(entry.price),
        "currency": entry.currency,
        "formatted_price": _format_price(entry.price, entry.currency),
        "source": entry.source,
        "sku": entry.sku,
        "supplier_name": entry.supplier_name,
        "canonical_id": entry.canonical_id,
        "supplier_item_id": entry.supplier_item_id,
        "product_id": entry.product_id,
    }


def serialize_result(result: PriceLookupResult) -> dict:
    return {
        "status": result.status,
        "query": result.query,
        "entries": [serialize_entry(e) for e in result.entries],
        "needs_clarification": result.status == "ambiguous" and len(result.entries) >= 2,
        "missing": result.missing_titles,
    }

def render_price_response(result: PriceLookupResult) -> str:
    """Genera un mensaje de texto amigable a partir del resultado."""

    if result.status == "invalid":
        return "Necesito un nombre de producto para buscar su precio."
    if result.status == "no_match":
        return f"No encontre productos que coincidan con '{result.query}'."
    if result.status == "missing_price" and result.missing_titles:
        name = result.missing_titles[0]
        return f"Encontre '{name}' pero no tiene precio de venta cargado."
    if result.status == "ambiguous" and len(result.entries) >= 2:
        options = [e.name for e in result.entries[:5]]
        if not options:
            return "No pude determinar el precio solicitado."
        if len(options) == 2:
            options_text = " o ".join(options)
        else:
            options_text = ", ".join(options[:-1]) + " o " + options[-1]
        return (
            f"Encontre varias opciones que coinciden con '{result.query}': {options_text}. "
            "Decime cual queres asi te doy el precio exacto."
        )
    if not result.entries:
        return "No pude determinar el precio solicitado."

    entry = result.entries[0]
    formatted = _format_price(entry.price, entry.currency)
    base = f"El precio de {entry.name} es {formatted}."
    if entry.supplier_name:
        base += f" Proveedor: {entry.supplier_name}."
    if entry.sku:
        base += f" SKU: {entry.sku}."
    return base.strip()


async def _canonical_to_entry(
    canonical: CanonicalProduct,
    db: AsyncSession,
) -> Optional[PriceEntry]:
    price = _to_decimal(canonical.sale_price)
    supplier_name = None
    supplier_item_id = None
    sku = canonical.ng_sku
    if price is None:
        stmt = (
            select(SupplierProduct, Supplier)
            .join(
                ProductEquivalence,
                ProductEquivalence.supplier_product_id == SupplierProduct.id,
            )
            .join(Supplier, Supplier.id == SupplierProduct.supplier_id)
            .where(ProductEquivalence.canonical_product_id == canonical.id)
            .order_by(SupplierProduct.current_sale_price.is_(None), SupplierProduct.current_sale_price)
            .limit(1)
        )
        row = (await db.execute(stmt)).first()
        if row:
            supplier_product, supplier = row
            price = _to_decimal(supplier_product.current_sale_price)
            supplier_name = supplier.name
            supplier_item_id = supplier_product.id
            if supplier_product.supplier_product_id:
                sku = supplier_product.supplier_product_id
    if price is None:
        return None
    return PriceEntry(
        name=canonical.name,
        price=price,
        currency="ARS",
        source="canonical" if canonical.sale_price is not None else "supplier_fallback",
        sku=sku,
        supplier_name=supplier_name,
        canonical_id=canonical.id,
        supplier_item_id=supplier_item_id,
        product_id=None,
    )


async def _fuzzy_canonical_matches(
    query: str,
    db: AsyncSession,
    seen: set,
    missing: List[str],
    limit: int,
) -> List[PriceEntry]:
    stmt = select(CanonicalProduct).where(CanonicalProduct.name.ilike(f"%{query}%")).limit(50)
    canonicals = (await db.execute(stmt)).scalars().all()
    if not canonicals:
        return []
    ranked = _rank_by_fuzzy(query, canonicals, key=lambda c: c.name, limit=limit)
    out: List[PriceEntry] = []
    for canonical in ranked:
        entry = await _canonical_to_entry(canonical, db)
        if entry:
            if entry.identity() not in seen:
                seen.add(entry.identity())
                out.append(entry)
        else:
            missing.append(canonical.name)
    return out


async def _fuzzy_supplier_matches(
    query: str,
    db: AsyncSession,
    seen: set,
    missing: List[str],
    limit: int,
) -> List[PriceEntry]:
    pattern_terms = [t for t in re.split(r"\s+", query) if len(t) >= 3]
    if pattern_terms:
        conds = [SupplierProduct.title.ilike(f"%{t}%") for t in pattern_terms]
        where = or_(*conds)
    else:
        where = SupplierProduct.title.ilike(f"%{query}%")
    stmt = (
        select(SupplierProduct, Supplier)
        .join(Supplier, Supplier.id == SupplierProduct.supplier_id)
        .where(where)
        .limit(50)
    )
    rows = (await db.execute(stmt)).all()
    if not rows:
        return []
    supplier_products = [row[0] for row in rows]
    ranked = _rank_by_fuzzy(query, supplier_products, key=lambda sp: sp.title, limit=limit)
    out: List[PriceEntry] = []
    indexed = {sp.id: sp for sp in supplier_products}
    supplier_index = {row[0].id: row[1] for row in rows}
    for sp in ranked:
        supplier = supplier_index.get(sp.id)
        entry = _supplier_entry(sp, supplier)
        if entry:
            if entry.identity() not in seen:
                seen.add(entry.identity())
                out.append(entry)
        else:
            missing.append(sp.title)
    return out


def _supplier_entry(sp: SupplierProduct, supplier: Supplier | None) -> Optional[PriceEntry]:
    price = _to_decimal(sp.current_sale_price)
    if price is None:
        return None
    supplier_name = supplier.name if supplier else None
    return PriceEntry(
        name=sp.title,
        price=price,
        currency="ARS",
        source="supplier",
        sku=sp.supplier_product_id,
        supplier_name=supplier_name,
        canonical_id=None,
        supplier_item_id=sp.id,
        product_id=sp.internal_product_id,
    )


def _append_entry(entries: List[PriceEntry], seen: set, entry: PriceEntry) -> None:
    ident = entry.identity()
    if ident in seen:
        return
    seen.add(ident)
    entries.append(entry)


def _format_price(value: Decimal, currency: str) -> str:
    formatted = f"{value:,.2f}"
    formatted = formatted.replace(",", "_")
    formatted = formatted.replace(".", ",")
    formatted = formatted.replace("_", ".")
    return f"{currency} {formatted}"


def _to_decimal(value) -> Optional[Decimal]:
    if value is None:
        return None
    if isinstance(value, Decimal):
        dec = value
    else:
        dec = Decimal(str(value))
    return dec.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def _rank_by_fuzzy(query: str, items: Sequence, key, limit: int) -> List:
    if not items:
        return []
    if process and fuzz:
        choices = {idx: key(item) for idx, item in enumerate(items)}
        matches = process.extract(query, choices, scorer=fuzz.WRatio, limit=limit)
        ranked = [items[idx] for _, _, idx in matches if idx < len(items)]
        return ranked
    # Fallback simple: ordenar por coincidencia de substring
    lowered = query.lower()
    scored: List[Tuple[int, int]] = []
    for idx, item in enumerate(items):
        name = key(item).lower()
        pos = name.find(lowered)
        score = pos if pos >= 0 else len(name)
        scored.append((score, idx))
    scored.sort()
    return [items[idx] for _, idx in scored[:limit]]
