#!/usr/bin/env python
# NG-HEADER: Nombre de archivo: completion.py
# NG-HEADER: Ubicación: services/purchases/completion.py
# NG-HEADER: Descripción: Servicio de autocompletado y enriquecimiento de líneas de compra
# NG-HEADER: Lineamientos: Ver AGENTS.md
"""Servicio de autocompletado y enriquecimiento de líneas de compra.

Objetivos:
- Vincular líneas (supplier_sku -> SupplierProduct / Product) cuando sea posible.
- Completar unit_cost_bonif (aplicando descuentos) y subtotal.
- Detectar outliers de precio contra histórico reciente.
- Sugerir coincidencias fuzzy cuando no hay SKU (sólo título) y registrar advertencias.
- Preparado para ser invocado antes de persistir (PUT /purchases/{id}).

Nota: Implementación inicial no accede todavía a la DB real (se proveerán hooks).
"""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any, Iterable
from decimal import Decimal
import statistics
import re

# --- Dataclasses de intercambio ---
@dataclass
class LineDraft:
    index: int
    supplier_sku: Optional[str]
    title: str
    qty: Decimal
    unit_cost: Optional[Decimal] = None
    line_discount: Optional[Decimal] = None  # porcentaje 0-100
    unit_cost_bonif: Optional[Decimal] = None
    subtotal: Optional[Decimal] = None

@dataclass
class LineCompletionResult(LineDraft):
    warnings: List[str] = field(default_factory=list)
    suggestions: List[str] = field(default_factory=list)
    supplier_product_id: Optional[int] = None
    product_id: Optional[int] = None
    price_reference: Optional[Dict[str, Any]] = None
    outlier: bool = False

@dataclass
class CompletionStats:
    lines_total: int = 0
    linked: int = 0
    with_sku: int = 0
    with_outlier: int = 0
    fuzzy_suggestions: int = 0
    price_enriched: int = 0
    elapsed_ms: int = 0

@dataclass
class CompletionOutput:
    lines: List[LineCompletionResult]
    stats: CompletionStats
    warnings: List[str] = field(default_factory=list)

# --- Configuración (luego podría cargarse desde JSON externo) ---
class CompletionConfig:
    price_outlier_upper: float = 1.25
    price_outlier_lower: float = 0.70
    fuzzy_title_min_ratio: float = 0.84
    min_price_history: int = 2  # mínimo de observaciones para outlier

CONFIG = CompletionConfig()
ALGO_VERSION = "20250926_1"  # Incrementar si cambia lógica de enriquecimiento

# --- Utilidades internas ---

def _apply_discount(unit_cost: Optional[Decimal], pct: Optional[Decimal]) -> Optional[Decimal]:
    if unit_cost is None:
        return None
    if pct is None:
        return unit_cost
    try:
        if pct < 0:
            pct = Decimal(0)
        if pct > 100:
            pct = Decimal(100)
        return (unit_cost * (Decimal(100) - pct) / Decimal(100)).quantize(Decimal('0.01'))
    except Exception:
        return unit_cost

def _norm_title(s: str) -> str:
    return re.sub(r"\s+", " ", (s or '').strip()).lower()

# Placeholder fuzzy ratio simple (sin dependencias externas)

def _simple_fuzzy_ratio(a: str, b: str) -> float:
    if not a or not b:
        return 0.0
    a_set = set(a.split())
    b_set = set(b.split())
    if not a_set or not b_set:
        return 0.0
    inter = len(a_set & b_set)
    union = len(a_set | b_set)
    return inter / union if union else 0.0

# --- Interfaz para inyectar historial de precios / catálogo ---
class PriceHistoryProvider:
    def get_prices(self, supplier_id: int, supplier_sku: str) -> List[Decimal]:  # pragma: no cover - interface
        return []

class CatalogProvider:
    def batch_map_skus(self, supplier_id: int, skus: Iterable[str]) -> Dict[str, Dict[str, Any]]:  # sku -> {supplier_product_id, product_id, last_price}
        return {}
    def fuzzy_candidates(self, supplier_id: int) -> List[Dict[str, Any]]:
        return []  # cada item: { 'title_norm': str, 'supplier_product_id': int, 'product_id': int, 'sku': str }

# --- Núcleo ---

def complete_purchase_lines(
    supplier_id: int,
    line_drafts: List[LineDraft],
    price_provider: PriceHistoryProvider,
    catalog_provider: CatalogProvider,
    *,
    config: CompletionConfig = CONFIG,
) -> CompletionOutput:
    from time import perf_counter
    t0 = perf_counter()
    results: List[LineCompletionResult] = []
    stats = CompletionStats(lines_total=len(line_drafts))

    # 1. Vinculación directa por SKU
    skus = [ld.supplier_sku for ld in line_drafts if ld.supplier_sku]
    sku_map = {}
    if skus:
        try:
            sku_map = catalog_provider.batch_map_skus(supplier_id, skus)
        except Exception:
            sku_map = {}

    # 2. Preparar candidatos fuzzy (lazy)
    fuzzy_cache = None

    for ld in line_drafts:
        r = LineCompletionResult(**ld.__dict__)
        if ld.supplier_sku:
            stats.with_sku += 1
        # Vinculación directa
        if ld.supplier_sku and ld.supplier_sku in sku_map:
            meta = sku_map[ld.supplier_sku]
            r.supplier_product_id = meta.get('supplier_product_id')
            r.product_id = meta.get('product_id')
            if meta.get('last_price') is not None and r.unit_cost is None:
                try:
                    r.unit_cost = Decimal(str(meta['last_price']))
                    stats.price_enriched += 1
                    r.warnings.append('unit_cost_autofill_from_catalog')
                except Exception:
                    pass
            stats.linked += 1
        # Fuzzy suggestions si no vinculado
        if not r.supplier_product_id and not r.product_id:
            if fuzzy_cache is None:
                try:
                    fuzzy_cache = catalog_provider.fuzzy_candidates(supplier_id)
                except Exception:
                    fuzzy_cache = []
            title_norm = _norm_title(r.title)
            best = None
            best_ratio = 0.0
            for cand in fuzzy_cache:
                ratio = _simple_fuzzy_ratio(title_norm, cand['title_norm'])
                if ratio > best_ratio:
                    best_ratio = ratio
                    best = cand
            if best and best_ratio >= config.fuzzy_title_min_ratio:
                r.suggestions.append(f"candidate:{best.get('sku')} ratio={best_ratio:.2f}")
                stats.fuzzy_suggestions += 1
        # Descuento → unit_cost_bonif
        if r.unit_cost_bonif is None:
            r.unit_cost_bonif = _apply_discount(r.unit_cost, r.line_discount)
        # Subtotal
        if r.subtotal is None and r.qty is not None and r.unit_cost_bonif is not None:
            try:
                r.subtotal = (r.qty * r.unit_cost_bonif).quantize(Decimal('0.01'))
            except Exception:
                pass
        # Historial de precios para outlier
        if r.supplier_sku:
            try:
                prices = price_provider.get_prices(supplier_id, r.supplier_sku)[:20]
            except Exception:
                prices = []
            if len(prices) >= config.min_price_history and r.unit_cost_bonif:
                med = statistics.median(prices)
                if med > 0:
                    ratio = float(r.unit_cost_bonif / med)
                    ref = {
                        'median': float(med),
                        'ratio_vs_median': ratio,
                        'n': len(prices)
                    }
                    r.price_reference = ref
                    if ratio > config.price_outlier_upper or ratio < config.price_outlier_lower:
                        r.outlier = True
                        stats.with_outlier += 1
                        r.warnings.append('price_outlier')
        # Validaciones rápidas
        if (r.qty or Decimal(0)) < 0:
            r.warnings.append('qty_negative_clamped')
            r.qty = Decimal(0)
        if r.unit_cost and r.unit_cost < 0:
            r.warnings.append('unit_cost_negative_clamped')
            r.unit_cost = Decimal(0)
        results.append(r)

    t1 = perf_counter()
    stats.elapsed_ms = int((t1 - t0) * 1000)
    return CompletionOutput(lines=results, stats=stats)

__all__ = [
    'LineDraft', 'LineCompletionResult', 'CompletionOutput', 'complete_purchase_lines',
    'PriceHistoryProvider', 'CatalogProvider', 'CompletionConfig', 'ALGO_VERSION'
]
