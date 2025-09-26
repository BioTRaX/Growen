
# NG-HEADER: Nombre de archivo: price_lookup.py
# NG-HEADER: Ubicacion: services/chat/price_lookup.py
# NG-HEADER: Descripcion: Utilidades para resolver precio y stock desde el chatbot
# NG-HEADER: Lineamientos: Ver AGENTS.md
"""Resolucion de precios y stock para el chatbot."""

from __future__ import annotations

import logging
import re
import time
import unicodedata
from dataclasses import dataclass, field
from decimal import Decimal, ROUND_HALF_UP
from typing import Dict, Iterable, List, Optional, Sequence, Set, Tuple, Union

from sqlalchemy import Select, and_, func, select
from sqlalchemy.exc import OperationalError
from sqlalchemy.ext.asyncio import AsyncSession

from db.models import (
    AuditLog,
    CanonicalProduct,
    Inventory,
    Product,
    ProductEquivalence,
    Supplier,
    SupplierProduct,
    Variant,
)

logger = logging.getLogger(__name__)

try:  # rapidfuzz es opcional pero preferido para ranking
    from rapidfuzz import fuzz  # type: ignore
except Exception:  # pragma: no cover - fallback sin rapidfuzz
    fuzz = None

PRICE_KEYWORDS = {
    "precio",
    "cuanto",
    "cuanto sale",
    "cuanto vale",
    "cuanto cuesta",
    "vale",
    "cuesta",
    "valor",
    "coste",
    "costar",
    "$",
}

STOCK_KEYWORDS = {
    "stock",
    "disponible",
    "disponibles",
    "disponibilidad",
    "tenes",
    "tenes?",
    "tienes",
    "tienes?",
    "hay",
    "hay?",
    "queda",
    "quedan",
    "queda?",
    "quedan?",
    "en stock",
    "sin stock",
    "agotado",
    "dispo",
}

COMMAND_ALIASES = {
    "precio": "price",
    "price": "price",
    "stock": "stock",
    "inventario": "stock",
}

STOPWORDS = {
    "de",
    "del",
    "la",
    "el",
    "los",
    "las",
    "un",
    "una",
    "y",
    "o",
    "por",
    "para",
    "con",
    "me",
    "dame",
    "quiero",
    "necesito",
    "hay",
    "tenes",
    "tenes?",
    "teneslo",
    "teneslo?",
    "tienes",
    "tienes?",
    "hay?",
    "queda",
    "quedan",
    "queda?",
    "quedan?",
    "cuanto",
    "cuanto?",
    "precio",
    "precio?",
    "stock",
    "en",
    "lo",
    "al",
    "que",
    "hola",
    "buenas",
    "buen",
    "tarde",
    "tardes",
    "dias",
    "dia",
    "buenos",
    "mostrar",
    "mostrame",
    "mostra",
    "podes",
    "podes?",
    "podrias",
    "podrias?",
    "decime",
    "decir",
    "dime",
    "dime?",
    "sabes",
    "sabes?",
    "sabe",
    "sin",
    "alguno",
    "alguna",
    "gracias",
    "porfa",
    "porfavor",
    "favor",
    "tengo",
    "otro",
    "otra",
    "mas",
    "cual",
    "cual?",
    "cuales",
    "cuales?",
    "es",
    "es?",
}

SKU_COMMAND_RE = re.compile(r"^[\s/]*(?P<command>[a-zA-Z]+)\s+(?P<body>.+)$")
SKU_TAG_RE = re.compile(r"\bsku[:#\s-]*([A-Za-z0-9._\-]{2,})\b", re.IGNORECASE)
ALNUM_TOKEN_RE = re.compile(r"[A-Za-z0-9._\-]+")
NUMERIC_TOKEN_RE = re.compile(r"\b\d{3,}\b")

LOW_STOCK_THRESHOLD = 2
FUZZY_THRESHOLD = 0.85
MAX_SUPPLIER_CANDIDATES = 40
MAX_CANONICAL_CANDIDATES = 40
@dataclass
class ProductQuery:
    raw_text: str
    normalized_text: str
    terms: List[str]
    sku_candidates: List[str]
    has_price: bool
    has_stock: bool
    intent: str
    command: Optional[str] = None
    explicit_price: bool = False
    explicit_stock: bool = False

    @property
    def search_text(self) -> str:
        if self.terms:
            return " ".join(self.terms)
        return self.normalized_text


@dataclass
class ProductEntry:
    name: str
    price: Optional[Decimal]
    currency: str
    source_detail: str
    stock_qty: int
    stock_status: str
    supplier_name: Optional[str] = None
    canonical_id: Optional[int] = None
    supplier_item_id: Optional[int] = None
    product_id: Optional[int] = None
    sku: Optional[str] = None
    variant_skus: List[str] = field(default_factory=list)
    score: float = 0.0
    match_reason: Optional[str] = None

    def identity(self) -> Tuple[str, Optional[int]]:
        if self.canonical_id:
            return ("canonical", self.canonical_id)
        if self.supplier_item_id:
            return ("supplier", self.supplier_item_id)
        if self.product_id:
            return ("product", self.product_id)
        return ("sku", hash((self.name.lower(), self.sku)))


@dataclass
class ProductLookupResult:
    query: ProductQuery
    status: str
    entries: List[ProductEntry]
    missing: List[str] = field(default_factory=list)
    took_ms: Optional[int] = None
    intent: str = "price"
    errors: List[str] = field(default_factory=list)

    def primary_entry(self) -> Optional[ProductEntry]:
        return self.entries[0] if self.entries else None


@dataclass
class CanonicalInfo:
    canonical_id: int
    sale_price: Optional[Decimal]
    sku: Optional[str]
    name: Optional[str]


@dataclass
class CanonicalBundle:
    stock_qty: int
    variant_skus: List[str]
    primary_supplier: Optional[Supplier]
    primary_supplier_product: Optional[SupplierProduct]
    first_product: Optional[Product]


# ---------------------------- utilidades de texto ----------------------------

def _strip_accents(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value or "")
    return "".join(ch for ch in normalized if not unicodedata.combining(ch))


def _normalize_text(value: str) -> str:
    value = _strip_accents(value)
    value = value.replace("\u00a0", " ")
    value = re.sub(r"\s+", " ", value)
    return value.strip()


def _unique_preserve(items: Iterable[str]) -> List[str]:
    seen: Set[str] = set()
    result: List[str] = []
    for item in items:
        key = item.lower()
        if key in seen:
            continue
        seen.add(key)
        result.append(item)
    return result


def _tokenize(normalized_text: str) -> List[str]:
    terms: List[str] = []
    for token in ALNUM_TOKEN_RE.findall(normalized_text.lower()):
        if token in STOPWORDS or len(token) <= 1:
            continue
        terms.append(token)
    return terms


def _extract_sku_candidates(raw: str, normalized: str) -> List[str]:
    candidates: List[str] = []
    for match in SKU_TAG_RE.finditer(raw):
        candidate = match.group(1).strip()
        if candidate:
            candidates.append(candidate)
    for token in NUMERIC_TOKEN_RE.findall(normalized):
        candidates.append(token)
    for token in ALNUM_TOKEN_RE.findall(normalized):
        if any(ch.isdigit() for ch in token) and len(token) >= 3:
            candidates.append(token)
    return candidates
# ------------------------------- utilidades de ranking -------------------------------

def _score_fuzzy(query_text: str, target_text: str) -> float:
    if not query_text or not target_text:
        return 0.0
    if fuzz:
        try:
            return float(fuzz.WRatio(query_text, target_text)) / 100.0
        except Exception:  # pragma: no cover
            return 0.0
    query_lower = query_text.lower()
    target_lower = target_text.lower()
    if query_lower == target_lower:
        return 1.0
    if query_lower in target_lower:
        return len(query_lower) / max(len(target_lower), 1)
    if target_lower in query_lower:
        return len(target_lower) / max(len(query_lower), 1)
    return 0.0


def _stock_status(stock_qty: Optional[int]) -> str:
    qty = int(stock_qty or 0)
    if qty <= 0:
        return "out"
    if qty <= LOW_STOCK_THRESHOLD:
        return "low"
    return "ok"


def _to_decimal(value) -> Optional[Decimal]:
    if value is None:
        return None
    if isinstance(value, Decimal):
        dec = value
    else:
        try:
            dec = Decimal(str(value))
        except Exception:
            return None
    return dec.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def _format_price(value: Decimal, currency: str) -> str:
    formatted = f"{value:,.2f}"
    formatted = formatted.replace(",", "_").replace(".", ",").replace("_", ".")
    return f"{currency} {formatted}"


def _add_entry(entries: List[ProductEntry], seen: Set[Tuple[str, Optional[int]]], entry: ProductEntry) -> None:
    ident = entry.identity()
    if ident in seen:
        return
    seen.add(ident)
    entries.append(entry)


# ------------------------------ consultas auxiliares ------------------------------

def _intent_from_flags(has_price: bool, has_stock: bool) -> str:
    if has_price and has_stock:
        return "mixed"
    if has_stock:
        return "stock"
    return "price"
async def _stock_for_product(
    session: AsyncSession,
    product: Product,
    stock_cache: Dict[int, int],
) -> int:
    if product.id in stock_cache:
        return stock_cache[product.id]
    qty = int(product.stock or 0)
    try:
        inv_result = await session.execute(
            select(func.sum(Inventory.stock_qty))
            .join(Variant, Variant.id == Inventory.variant_id)
            .where(Variant.product_id == product.id)
        )
        inv_total = inv_result.scalar()
    except OperationalError:
        inv_total = None
    if inv_total is not None:
        qty = int(inv_total)
    stock_cache[product.id] = max(qty, 0)
    return stock_cache[product.id]


async def _variant_skus_for_product(
    session: AsyncSession,
    product: Product,
    variant_cache: Dict[int, List[str]],
) -> List[str]:
    if product.id in variant_cache:
        return variant_cache[product.id]
    try:
        result = await session.execute(
            select(Variant.sku).where(Variant.product_id == product.id)
        )
        rows = result.scalars().all()
    except OperationalError:
        rows = []
    skus = [sku for sku in rows if sku]
    if not skus and product.sku_root:
        skus = [product.sku_root]
    variant_cache[product.id] = skus
    return skus


async def _get_canonical_info(
    session: AsyncSession,
    supplier_product_id: int,
    cache: Dict[int, Optional[CanonicalInfo]],
    errors: List[str],
) -> Optional[CanonicalInfo]:
    if supplier_product_id in cache:
        return cache[supplier_product_id]
    try:
        row = (
            await session.execute(
                select(
                    ProductEquivalence.canonical_product_id,
                    CanonicalProduct.sale_price,
                    CanonicalProduct.ng_sku,
                    CanonicalProduct.sku_custom,
                    CanonicalProduct.name,
                )
                .join(
                    CanonicalProduct,
                    CanonicalProduct.id == ProductEquivalence.canonical_product_id,
                    isouter=True,
                )
                .where(ProductEquivalence.supplier_product_id == supplier_product_id)
            )
        ).first()
    except OperationalError:
        logger.warning("price_lookup: canonical info query failed", exc_info=True)
        errors.append("canonical_lookup_failed")
        cache[supplier_product_id] = None
        return None
    if not row:
        cache[supplier_product_id] = None
        return None
    canonical_id, sale_price, ng_sku, sku_custom, canonical_name = row
    if canonical_id is None:
        cache[supplier_product_id] = None
        return None
    info = CanonicalInfo(
        canonical_id=canonical_id,
        sale_price=_to_decimal(sale_price),
        sku=(ng_sku or sku_custom),
        name=canonical_name,
    )
    cache[supplier_product_id] = info
    return info


async def _get_canonical_bundle(
    session: AsyncSession,
    canonical_id: int,
    *,
    stock_cache: Dict[int, int],
    variant_cache: Dict[int, List[str]],
    bundle_cache: Dict[int, CanonicalBundle],
    errors: List[str],
) -> CanonicalBundle:
    if canonical_id in bundle_cache:
        return bundle_cache[canonical_id]
    try:
        rows = (
            await session.execute(
                select(SupplierProduct, Supplier, Product)
                .join(
                    ProductEquivalence,
                    ProductEquivalence.supplier_product_id == SupplierProduct.id,
                )
                .outerjoin(Supplier, Supplier.id == SupplierProduct.supplier_id)
                .outerjoin(Product, Product.id == SupplierProduct.internal_product_id)
                .where(ProductEquivalence.canonical_product_id == canonical_id)
            )
        ).all()
    except OperationalError:
        logger.warning("price_lookup: canonical bundle query failed", exc_info=True)
        errors.append("canonical_bundle_failed")
        rows = []
    products: Dict[int, Product] = {}
    primary_supplier: Optional[Supplier] = None
    primary_supplier_product: Optional[SupplierProduct] = None
    for sp, supplier, product in rows:
        if primary_supplier_product is None:
            primary_supplier_product = sp
        if primary_supplier is None and supplier:
            primary_supplier = supplier
        if product and product.id not in products:
            products[product.id] = product
    variant_skus: Set[str] = set()
    total_stock = 0
    for product in products.values():
        total_stock += await _stock_for_product(session, product, stock_cache)
        variant_skus.update(await _variant_skus_for_product(session, product, variant_cache))
    first_product = next(iter(products.values()), None)
    bundle = CanonicalBundle(
        stock_qty=total_stock,
        variant_skus=sorted(variant_skus),
        primary_supplier=primary_supplier,
        primary_supplier_product=primary_supplier_product,
        first_product=first_product,
    )
    bundle_cache[canonical_id] = bundle
    return bundle

async def _build_supplier_entry(
    sp: SupplierProduct,
    supplier: Optional[Supplier],
    product: Optional[Product],
    session: AsyncSession,
    *,
    stock_cache: Dict[int, int],
    variant_cache: Dict[int, List[str]],
    supplier_canonical_cache: Dict[int, Optional[CanonicalInfo]],
    canonical_bundle_cache: Dict[int, CanonicalBundle],
    errors: List[str],
    score: float,
    match_reason: str,
) -> Optional[ProductEntry]:
    price = _to_decimal(sp.current_sale_price)
    canonical_info = await _get_canonical_info(
        session, sp.id, supplier_canonical_cache, errors
    )
    source_detail = "supplier"
    sku = sp.supplier_product_id or None
    name = sp.title
    stock_qty = 0
    variant_skus: List[str] = []
    product_id: Optional[int] = None
    if product:
        product_id = product.id
        stock_qty = await _stock_for_product(session, product, stock_cache)
        variant_skus = await _variant_skus_for_product(session, product, variant_cache)
    elif canonical_info:
        bundle = await _get_canonical_bundle(
            session,
            canonical_info.canonical_id,
            stock_cache=stock_cache,
            variant_cache=variant_cache,
            bundle_cache=canonical_bundle_cache,
            errors=errors,
        )
        stock_qty = bundle.stock_qty
        variant_skus = bundle.variant_skus
        if bundle.first_product:
            product_id = bundle.first_product.id
        if bundle.primary_supplier and not supplier:
            supplier = bundle.primary_supplier
        if bundle.primary_supplier_product and not sku:
            sku = bundle.primary_supplier_product.supplier_product_id
    if canonical_info:
        name = canonical_info.name or name
        if price is None and canonical_info.sale_price is not None:
            price = canonical_info.sale_price
            source_detail = "canonical"
        if canonical_info.sku:
            sku = canonical_info.sku
    if price is None and not canonical_info:
        errors.append(f"missing_price:{sp.id}")
    stock_status = _stock_status(stock_qty)
    return ProductEntry(
        name=name,
        price=price,
        currency="ARS",
        source_detail=source_detail,
        stock_qty=stock_qty,
        stock_status=stock_status,
        supplier_name=supplier.name if supplier else None,
        canonical_id=canonical_info.canonical_id if canonical_info else None,
        supplier_item_id=sp.id,
        product_id=product_id,
        sku=sku,
        variant_skus=variant_skus,
        score=score,
        match_reason=match_reason,
    )


async def _build_canonical_entry(
    canonical: CanonicalProduct,
    session: AsyncSession,
    *,
    stock_cache: Dict[int, int],
    variant_cache: Dict[int, List[str]],
    bundle_cache: Dict[int, CanonicalBundle],
    supplier_canonical_cache: Dict[int, Optional[CanonicalInfo]],
    errors: List[str],
    score: float,
    match_reason: str,
) -> Optional[ProductEntry]:
    price = _to_decimal(canonical.sale_price)
    sku = canonical.ng_sku or canonical.sku_custom
    bundle = await _get_canonical_bundle(
        session,
        canonical.id,
        stock_cache=stock_cache,
        variant_cache=variant_cache,
        bundle_cache=bundle_cache,
        errors=errors,
    )
    supplier = bundle.primary_supplier
    supplier_item = bundle.primary_supplier_product
    if price is None and supplier_item:
        price = _to_decimal(supplier_item.current_sale_price)
    if sku is None and supplier_item:
        sku = supplier_item.supplier_product_id
    product_id = bundle.first_product.id if bundle.first_product else None
    stock_qty = bundle.stock_qty
    stock_status = _stock_status(stock_qty)
    if price is None:
        errors.append(f"missing_price_canonical:{canonical.id}")
    return ProductEntry(
        name=canonical.name,
        price=price,
        currency="ARS",
        source_detail="canonical" if canonical.sale_price is not None else "canonical_supplier",
        stock_qty=stock_qty,
        stock_status=stock_status,
        supplier_name=supplier.name if supplier else None,
        canonical_id=canonical.id,
        supplier_item_id=supplier_item.id if supplier_item else None,
        product_id=product_id,
        sku=sku,
        variant_skus=bundle.variant_skus,
        score=score,
        match_reason=match_reason,
    )


async def _fallback_entry_from_product(
    product: Product,
    session: AsyncSession,
    *,
    stock_cache: Dict[int, int],
    variant_cache: Dict[int, List[str]],
    supplier_canonical_cache: Dict[int, Optional[CanonicalInfo]],
    canonical_bundle_cache: Dict[int, CanonicalBundle],
    errors: List[str],
    score: float,
    match_reason: str,
) -> Optional[ProductEntry]:
    stock_qty = await _stock_for_product(session, product, stock_cache)
    variant_skus = await _variant_skus_for_product(session, product, variant_cache)
    supplier_row = None
    try:
        supplier_row = (
            await session.execute(
                select(SupplierProduct, Supplier)
                .join(Supplier, Supplier.id == SupplierProduct.supplier_id)
                .where(SupplierProduct.internal_product_id == product.id)
                .order_by(
                    SupplierProduct.current_sale_price.is_(None),
                    SupplierProduct.current_sale_price,
                )
                .limit(1)
            )
        ).first()
    except OperationalError:
        logger.warning("price_lookup: product fallback supplier query failed", exc_info=True)
        errors.append("product_fallback_supplier_failed")
    if supplier_row:
        sp, supplier = supplier_row
        return await _build_supplier_entry(
            sp,
            supplier,
            product,
            session,
            stock_cache=stock_cache,
            variant_cache=variant_cache,
            supplier_canonical_cache=supplier_canonical_cache,
            canonical_bundle_cache=canonical_bundle_cache,
            errors=errors,
            score=score,
            match_reason=match_reason,
        )
    stock_status = _stock_status(stock_qty)
    return ProductEntry(
        name=product.title,
        price=None,
        currency="ARS",
        source_detail="product",
        stock_qty=stock_qty,
        stock_status=stock_status,
        supplier_name=None,
        canonical_id=None,
        supplier_item_id=None,
        product_id=product.id,
        sku=product.sku_root,
        variant_skus=variant_skus,
        score=score,
        match_reason=match_reason,
    )

async def _collect_supplier_exact_by_sku(
    query: ProductQuery,
    session: AsyncSession,
    *,
    seen: Set[Tuple[str, Optional[int]]],
    stock_cache: Dict[int, int],
    variant_cache: Dict[int, List[str]],
    supplier_canonical_cache: Dict[int, Optional[CanonicalInfo]],
    canonical_bundle_cache: Dict[int, CanonicalBundle],
    errors: List[str],
) -> List[ProductEntry]:
    out: List[ProductEntry] = []
    for sku in query.sku_candidates:
        candidate = sku.strip().lower()
        if not candidate:
            continue
        stmt = (
            select(SupplierProduct, Supplier, Product)
            .join(Supplier, Supplier.id == SupplierProduct.supplier_id)
            .outerjoin(Product, Product.id == SupplierProduct.internal_product_id)
            .where(func.lower(SupplierProduct.supplier_product_id) == candidate)
        )
        rows = (await session.execute(stmt)).all()
        for sp, supplier, product in rows:
            entry = await _build_supplier_entry(
                sp,
                supplier,
                product,
                session,
                stock_cache=stock_cache,
                variant_cache=variant_cache,
                supplier_canonical_cache=supplier_canonical_cache,
                canonical_bundle_cache=canonical_bundle_cache,
                errors=errors,
                score=1.5,
                match_reason="supplier_sku",
            )
            if entry:
                _add_entry(out, seen, entry)
    return out


async def _collect_internal_sku_matches(
    query: ProductQuery,
    session: AsyncSession,
    *,
    seen: Set[Tuple[str, Optional[int]]],
    stock_cache: Dict[int, int],
    variant_cache: Dict[int, List[str]],
    supplier_canonical_cache: Dict[int, Optional[CanonicalInfo]],
    canonical_bundle_cache: Dict[int, CanonicalBundle],
    errors: List[str],
) -> List[ProductEntry]:
    out: List[ProductEntry] = []
    if not query.sku_candidates:
        return out
    for sku in query.sku_candidates:
        candidate = sku.strip().lower()
        if not candidate:
            continue
        stmt = (
            select(Product, SupplierProduct, Supplier)
            .outerjoin(SupplierProduct, SupplierProduct.internal_product_id == Product.id)
            .outerjoin(Supplier, Supplier.id == SupplierProduct.supplier_id)
            .where(func.lower(Product.sku_root) == candidate)
        )
        rows = (await session.execute(stmt)).all()
        for product, supplier_product, supplier in rows:
            if supplier_product:
                entry = await _build_supplier_entry(
                    supplier_product,
                    supplier,
                    product,
                    session,
                    stock_cache=stock_cache,
                    variant_cache=variant_cache,
                    supplier_canonical_cache=supplier_canonical_cache,
                    canonical_bundle_cache=canonical_bundle_cache,
                    errors=errors,
                    score=1.3,
                    match_reason="internal_sku",
                )
            else:
                entry = await _fallback_entry_from_product(
                    product,
                    session,
                    stock_cache=stock_cache,
                    variant_cache=variant_cache,
                    supplier_canonical_cache=supplier_canonical_cache,
                    canonical_bundle_cache=canonical_bundle_cache,
                    errors=errors,
                    score=1.0,
                    match_reason="internal_sku",
                )
            if entry:
                _add_entry(out, seen, entry)
    return out


async def _collect_canonical_exact(
    query: ProductQuery,
    session: AsyncSession,
    *,
    seen: Set[Tuple[str, Optional[int]]],
    stock_cache: Dict[int, int],
    variant_cache: Dict[int, List[str]],
    supplier_canonical_cache: Dict[int, Optional[CanonicalInfo]],
    canonical_bundle_cache: Dict[int, CanonicalBundle],
    errors: List[str],
) -> List[ProductEntry]:
    out: List[ProductEntry] = []
    if not query.sku_candidates:
        return out
    for sku in query.sku_candidates:
        lowered = sku.strip().lower()
        if not lowered:
            continue
        canonical: Optional[CanonicalProduct] = None
        for field in (CanonicalProduct.ng_sku, CanonicalProduct.sku_custom):
            try:
                stmt = select(CanonicalProduct).where(func.lower(field) == lowered)
                canonical = (await session.execute(stmt)).scalar_one_or_none()
            except OperationalError:
                logger.warning("price_lookup: canonical exact query failed", exc_info=True)
                errors.append("canonical_exact_failed")
                canonical = None
                break
            if canonical:
                break
        if canonical:
            entry = await _build_canonical_entry(
                canonical,
                session,
                stock_cache=stock_cache,
                variant_cache=variant_cache,
                bundle_cache=canonical_bundle_cache,
                supplier_canonical_cache=supplier_canonical_cache,
                errors=errors,
                score=1.4,
                match_reason="canonical_sku",
            )
            if entry:
                _add_entry(out, seen, entry)
    return out


async def _collect_supplier_fuzzy(
    query: ProductQuery,
    session: AsyncSession,
    *,
    seen: Set[Tuple[str, Optional[int]]],
    stock_cache: Dict[int, int],
    variant_cache: Dict[int, List[str]],
    supplier_canonical_cache: Dict[int, Optional[CanonicalInfo]],
    canonical_bundle_cache: Dict[int, CanonicalBundle],
    errors: List[str],
) -> List[ProductEntry]:
    out: List[ProductEntry] = []
    search_text = query.search_text
    if not search_text:
        return out
    stmt = (
        select(SupplierProduct, Supplier, Product)
        .join(Supplier, Supplier.id == SupplierProduct.supplier_id)
        .outerjoin(Product, Product.id == SupplierProduct.internal_product_id)
    )
    conditions = [SupplierProduct.title.ilike(f"%{term}%") for term in query.terms]
    if conditions:
        stmt = stmt.where(and_(*conditions))
    else:
        stmt = stmt.where(SupplierProduct.title.ilike(f"%{query.normalized_text}%"))
    stmt = stmt.limit(MAX_SUPPLIER_CANDIDATES)
    rows = (await session.execute(stmt)).all()
    for sp, supplier, product in rows:
        candidate_text = _normalize_text(sp.title)
        score = _score_fuzzy(search_text, candidate_text)
        if score < FUZZY_THRESHOLD and not query.sku_candidates:
            continue
        entry = await _build_supplier_entry(
            sp,
            supplier,
            product,
            session,
            stock_cache=stock_cache,
            variant_cache=variant_cache,
            supplier_canonical_cache=supplier_canonical_cache,
            canonical_bundle_cache=canonical_bundle_cache,
            errors=errors,
            score=score,
            match_reason="supplier_fuzzy",
        )
        if entry:
            entry.score = max(entry.score, score)
            _add_entry(out, seen, entry)
    return out


async def _collect_canonical_fuzzy(
    query: ProductQuery,
    session: AsyncSession,
    *,
    seen: Set[Tuple[str, Optional[int]]],
    stock_cache: Dict[int, int],
    variant_cache: Dict[int, List[str]],
    supplier_canonical_cache: Dict[int, Optional[CanonicalInfo]],
    canonical_bundle_cache: Dict[int, CanonicalBundle],
    errors: List[str],
) -> List[ProductEntry]:
    out: List[ProductEntry] = []
    search_text = query.search_text
    if not search_text:
        return out
    stmt = select(CanonicalProduct)
    conditions = [CanonicalProduct.name.ilike(f"%{term}%") for term in query.terms]
    if conditions:
        stmt = stmt.where(and_(*conditions))
    else:
        stmt = stmt.where(CanonicalProduct.name.ilike(f"%{query.normalized_text}%"))
    stmt = stmt.limit(MAX_CANONICAL_CANDIDATES)
    try:
        canonicals = (await session.execute(stmt)).scalars().all()
    except OperationalError:
        logger.warning("price_lookup: canonical fuzzy query failed", exc_info=True)
        errors.append("canonical_fuzzy_failed")
        return out
    for canonical in canonicals:
        candidate_text = _normalize_text(canonical.name)
        score = _score_fuzzy(search_text, candidate_text)
        if score < FUZZY_THRESHOLD:
            continue
        entry = await _build_canonical_entry(
            canonical,
            session,
            stock_cache=stock_cache,
            variant_cache=variant_cache,
            bundle_cache=canonical_bundle_cache,
            supplier_canonical_cache=supplier_canonical_cache,
            errors=errors,
            score=score,
            match_reason="canonical_fuzzy",
        )
        if entry:
            entry.score = max(entry.score, score)
            _add_entry(out, seen, entry)
    return out


async def _collect_product_fallback(
    query: ProductQuery,
    session: AsyncSession,
    *,
    seen: Set[Tuple[str, Optional[int]]],
    stock_cache: Dict[int, int],
    variant_cache: Dict[int, List[str]],
    supplier_canonical_cache: Dict[int, Optional[CanonicalInfo]],
    canonical_bundle_cache: Dict[int, CanonicalBundle],
    errors: List[str],
) -> List[ProductEntry]:
    out: List[ProductEntry] = []
    if not query.terms:
        return out
    stmt = select(Product)
    conditions = [Product.title.ilike(f"%{term}%") for term in query.terms]
    if conditions:
        stmt = stmt.where(and_(*conditions))
    else:
        stmt = stmt.where(Product.title.ilike(f"%{query.normalized_text}%"))
    stmt = stmt.limit(10)
    rows = (await session.execute(stmt)).scalars().all()
    for product in rows:
        entry = await _fallback_entry_from_product(
            product,
            session,
            stock_cache=stock_cache,
            variant_cache=variant_cache,
            supplier_canonical_cache=supplier_canonical_cache,
            canonical_bundle_cache=canonical_bundle_cache,
            errors=errors,
            score=0.8,
            match_reason="product_fallback",
        )
        if entry:
            _add_entry(out, seen, entry)
    return out


def _rank_entries(entries: List[ProductEntry]) -> List[ProductEntry]:
    stock_priority = {"ok": 0, "low": 1, "out": 2}
    return sorted(
        entries,
        key=lambda e: (
            stock_priority.get(e.stock_status, 3),
            -float(e.score or 0.0),
            (e.name or "").lower(),
        ),
    )
# ---------------------------------- API publica ----------------------------------

def extract_product_query(text: str) -> Optional[ProductQuery]:
    if not text:
        return None
    raw = text.strip()
    if not raw:
        return None
    command = None
    body = raw
    match = SKU_COMMAND_RE.match(raw)
    if match:
        candidate_command = match.group("command").lower()
        if candidate_command in COMMAND_ALIASES:
            command = COMMAND_ALIASES[candidate_command]
            body = match.group("body") or ""
    normalized = _normalize_text(body)
    lowered = normalized.lower()
    has_price = any(keyword in lowered for keyword in PRICE_KEYWORDS)
    has_stock = any(keyword in lowered for keyword in STOCK_KEYWORDS)
    if "$" in raw:
        has_price = True
    if command == "price":
        has_price = True
    if command == "stock":
        has_stock = True
    sku_candidates = _extract_sku_candidates(raw, normalized)
    terms = _tokenize(normalized)
    if not terms and not sku_candidates:
        return None
    explicit_price = has_price
    explicit_stock = has_stock
    if not has_price and not has_stock:
        has_price = True
    intent = _intent_from_flags(has_price, has_stock)
    return ProductQuery(
        raw_text=raw,
        normalized_text=normalized,
        terms=terms,
        sku_candidates=_unique_preserve(sku_candidates),
        has_price=has_price,
        has_stock=has_stock,
        intent=intent,
        command=command,
        explicit_price=explicit_price,
        explicit_stock=explicit_stock,
    )


def extract_price_query(text: str) -> Optional[str]:
    product_query = extract_product_query(text)
    if not product_query:
        return None
    if product_query.terms:
        return " ".join(product_query.terms)
    if product_query.sku_candidates:
        return product_query.sku_candidates[0]
    return product_query.normalized_text or None


async def resolve_product_info(
    query: ProductQuery,
    session: AsyncSession,
    limit: int = 5,
) -> ProductLookupResult:
    start = time.perf_counter()
    if not query.terms and not query.sku_candidates:
        took = int((time.perf_counter() - start) * 1000)
        return ProductLookupResult(
            query=query,
            status="invalid",
            entries=[],
            missing=[],
            took_ms=took,
            intent=query.intent,
            errors=["empty_query"],
        )

    seen: Set[Tuple[str, Optional[int]]] = set()
    entries: List[ProductEntry] = []
    missing: List[str] = []
    errors: List[str] = []
    stock_cache: Dict[int, int] = {}
    variant_cache: Dict[int, List[str]] = {}
    supplier_canonical_cache: Dict[int, Optional[CanonicalInfo]] = {}
    canonical_bundle_cache: Dict[int, CanonicalBundle] = {}

    entries.extend(
        await _collect_supplier_exact_by_sku(
            query,
            session,
            seen=seen,
            stock_cache=stock_cache,
            variant_cache=variant_cache,
            supplier_canonical_cache=supplier_canonical_cache,
            canonical_bundle_cache=canonical_bundle_cache,
            errors=errors,
        )
    )
    entries.extend(
        await _collect_internal_sku_matches(
            query,
            session,
            seen=seen,
            stock_cache=stock_cache,
            variant_cache=variant_cache,
            supplier_canonical_cache=supplier_canonical_cache,
            canonical_bundle_cache=canonical_bundle_cache,
            errors=errors,
        )
    )
    entries.extend(
        await _collect_canonical_exact(
            query,
            session,
            seen=seen,
            stock_cache=stock_cache,
            variant_cache=variant_cache,
            supplier_canonical_cache=supplier_canonical_cache,
            canonical_bundle_cache=canonical_bundle_cache,
            errors=errors,
        )
    )
    entries.extend(
        await _collect_supplier_fuzzy(
            query,
            session,
            seen=seen,
            stock_cache=stock_cache,
            variant_cache=variant_cache,
            supplier_canonical_cache=supplier_canonical_cache,
            canonical_bundle_cache=canonical_bundle_cache,
            errors=errors,
        )
    )
    entries.extend(
        await _collect_canonical_fuzzy(
            query,
            session,
            seen=seen,
            stock_cache=stock_cache,
            variant_cache=variant_cache,
            supplier_canonical_cache=supplier_canonical_cache,
            canonical_bundle_cache=canonical_bundle_cache,
            errors=errors,
        )
    )
    if not entries:
        entries.extend(
            await _collect_product_fallback(
                query,
                session,
                seen=seen,
                stock_cache=stock_cache,
                variant_cache=variant_cache,
                supplier_canonical_cache=supplier_canonical_cache,
                canonical_bundle_cache=canonical_bundle_cache,
                errors=errors,
            )
        )

    for entry in entries:
        if entry.price is None:
            missing.append(entry.name)

    ranked = _rank_entries(entries)
    limited = ranked[:limit]
    if ranked and limit:
        has_out = any(entry.stock_status == "out" for entry in limited)
        if not has_out:
            out_entry = next((entry for entry in ranked if entry.stock_status == "out"), None)
            if out_entry:
                if limited:
                    limited = limited[:-1] + [out_entry]
                else:
                    limited = [out_entry]
    status = "no_match"
    if limited:
        status = "ok" if len(limited) == 1 else "ambiguous"
    took = int((time.perf_counter() - start) * 1000)
    return ProductLookupResult(
        query=query,
        status=status,
        entries=limited,
        missing=_unique_preserve(missing),
        took_ms=took,
        intent=query.intent,
        errors=_unique_preserve(errors),
    )


async def resolve_price(
    query: str,
    session: AsyncSession,
    limit: int = 5,
) -> ProductLookupResult:
    extracted = extract_product_query(query)
    if not extracted:
        normalized = _normalize_text(query)
        extracted = ProductQuery(
            raw_text=query,
            normalized_text=normalized,
            terms=_tokenize(normalized),
            sku_candidates=[],
            has_price=True,
            has_stock=False,
            intent="price",
        )
    return await resolve_product_info(extracted, session, limit=limit)


def serialize_entry(entry: ProductEntry) -> dict:
    formatted = _format_price(entry.price, entry.currency) if entry.price is not None else None
    return {
        "name": entry.name,
        "price": float(entry.price) if entry.price is not None else None,
        "currency": entry.currency,
        "formatted_price": formatted,
        "source_detail": entry.source_detail,
        "sku": entry.sku,
        "supplier_name": entry.supplier_name,
        "canonical_id": entry.canonical_id,
        "supplier_item_id": entry.supplier_item_id,
        "product_id": entry.product_id,
        "stock_qty": entry.stock_qty,
        "stock_status": entry.stock_status,
        "variant_skus": entry.variant_skus,
        "score": entry.score,
        "match_reason": entry.match_reason,
    }


def serialize_result(result: ProductLookupResult) -> dict:
    return {
        "status": result.status,
        "query": result.query.raw_text,
        "intent": result.intent,
        "normalized_query": result.query.normalized_text,
        "terms": result.query.terms,
        "sku_candidates": result.query.sku_candidates,
        "results": [serialize_entry(entry) for entry in result.entries],
        "missing": result.missing,
        "took_ms": result.took_ms,
        "errors": result.errors,
    }


def render_product_response(result: ProductLookupResult) -> str:
    if result.status == "invalid":
        return "Necesito un nombre o codigo para buscar el producto."
    if result.status == "no_match":
        return f"No encontre productos que coincidan con '{result.query.raw_text}'."
    if not result.entries:
        return "No pude determinar el producto solicitado."
    if result.status == "ambiguous" and len(result.entries) > 1:
        options: List[str] = []
        for entry in result.entries[:3]:
            desc = entry.name
            if entry.stock_status == "ok":
                desc += f" (en stock {entry.stock_qty})"
            elif entry.stock_status == "low":
                desc += f" (pocas unidades: {entry.stock_qty})"
            elif entry.stock_status == "out":
                desc += " (sin stock)"
            options.append(desc)
        more = ""
        if len(result.entries) > 3:
            more = " y otras opciones"
        message = (
            "Tambien encontre varias opciones que coinciden con tu busqueda: "
            + "; ".join(options)
            + f"{more}. "
        )
        if any(entry.price is None for entry in result.entries):
            message += "Hay opciones sin precio de venta cargado. "
        message += "Decime cual te interesa y te doy el detalle."
        return message
    entry = result.entries[0]
    parts: List[str] = []
    if entry.price is None:
        parts.append(f"{entry.name} esta sin precio de venta cargado.")
    else:
        parts.append(f"El precio de {entry.name} es {_format_price(entry.price, entry.currency)}.")
    if entry.stock_status == "ok":
        parts.append(f"En stock: {entry.stock_qty} unidades disponibles.")
    elif entry.stock_status == "low":
        parts.append(f"Pocas unidades: quedan {entry.stock_qty}.")
    else:
        parts.append("Por ahora sin stock, puedo avisarte cuando vuelva a entrar.")
    if entry.sku:
        parts.append(f"SKU: {entry.sku}.")
    if entry.supplier_name:
        parts.append(f"Proveedor: {entry.supplier_name}.")
    return " ".join(parts).strip()


def render_price_response(result: ProductLookupResult) -> str:
    return render_product_response(result)


async def log_product_lookup(
    session: AsyncSession,
    *,
    user_id: Optional[int],
    ip: Optional[str],
    original_text: str,
    product_query: Optional[Union[ProductQuery, str]],
    result: ProductLookupResult,
) -> None:
    if isinstance(product_query, ProductQuery):
        query_data = product_query
    elif isinstance(product_query, str):
        query_data = extract_product_query(product_query)
    else:
        query_data = None
    payload = serialize_result(result)
    payload["query_raw"] = original_text
    payload["query_intent"] = query_data.intent if query_data else None
    payload["has_price_intent"] = query_data.has_price if query_data else None
    payload["has_stock_intent"] = query_data.has_stock if query_data else None
    payload["terms_extracted"] = query_data.terms if query_data else []
    payload["sku_extracted"] = query_data.sku_candidates if query_data else []
    session.add(
        AuditLog(
            action="chat.product_lookup",
            table="chat",
            entity_id=None,
            meta=payload,
            user_id=user_id,
            ip=ip,
        )
    )
    try:
        await session.commit()
    except Exception:  # pragma: no cover
        logger.exception("price_lookup: failed to persist audit log")


async def log_price_lookup(
    session: AsyncSession,
    *,
    user_id: Optional[int],
    ip: Optional[str],
    original_text: str,
    extracted_query: Optional[Union[ProductQuery, str]],
    result: ProductLookupResult,
) -> None:
    await log_product_lookup(
        session,
        user_id=user_id,
        ip=ip,
        original_text=original_text,
        product_query=extracted_query,
        result=result,
    )


