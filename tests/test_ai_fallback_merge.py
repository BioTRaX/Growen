#!/usr/bin/env python
# NG-HEADER: Nombre de archivo: test_ai_fallback_merge.py
# NG-HEADER: Ubicación: tests/test_ai_fallback_merge.py
# NG-HEADER: Descripción: Test del merge IA con monkeypatch simulando respuesta
# NG-HEADER: Lineamientos: Ver AGENTS.md
"""Valida que merge_ai_lines agrega líneas no duplicadas y respeta min_conf.

Se simula un payload IA con dos líneas: una válida (> threshold) y una de baja confianza.
"""
from decimal import Decimal
from services.importers.santaplanta_pipeline import ParsedLine
from services.importers.ai_fallback import merge_ai_lines, RemitoAIPayload, RemitoAIItem


def test_merge_ai_lines_basic():
    classic = [ParsedLine(supplier_sku="1001", title="Prod A", qty=Decimal("1"), unit_cost_bonif=Decimal("10"))]
    ai_payload = RemitoAIPayload(lines=[
        RemitoAIItem(supplier_sku="1002", title="Prod B", qty=1, unit_cost_bonif=5, pct_bonif=0, confidence=0.9),
        RemitoAIItem(supplier_sku="1001", title="Dup Prod A", qty=2, unit_cost_bonif=11, pct_bonif=0, confidence=0.95),  # Duplicado SKU
        RemitoAIItem(supplier_sku="1003", title="Low C", qty=1, unit_cost_bonif=2, pct_bonif=0, confidence=0.3),  # Baja confianza
    ])
    merged, stats = merge_ai_lines(classic, ai_payload, min_conf=0.5)
    # Debe agregarse sólo 1002
    skus = [l.supplier_sku for l in merged if l.supplier_sku]
    assert "1001" in skus
    assert "1002" in skus
    assert "1003" not in skus
    assert stats["added"] == 1
    assert stats["ignored_low_conf"] == 1
