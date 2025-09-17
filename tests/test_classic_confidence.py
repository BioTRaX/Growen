#!/usr/bin/env python
# NG-HEADER: Nombre de archivo: test_classic_confidence.py
# NG-HEADER: Ubicación: tests/test_classic_confidence.py
# NG-HEADER: Descripción: Tests de heurística classic_confidence
# NG-HEADER: Lineamientos: Ver AGENTS.md
from services.importers.santaplanta_pipeline import ParsedLine, compute_classic_confidence


def test_confidence_zero_no_lines():
    assert compute_classic_confidence([]) == 0.0


def test_confidence_high():
    lines = [
        ParsedLine(supplier_sku="1001", title="Prod A", qty=1, unit_cost_bonif=10),
        ParsedLine(supplier_sku="1002", title="Prod B", qty=2, unit_cost_bonif=5),
        ParsedLine(supplier_sku="1003", title="Prod C", qty=3, unit_cost_bonif=7),
    ]
    score = compute_classic_confidence(lines)
    assert score > 0.85, score


def test_confidence_low_missing_data():
    lines = [
        ParsedLine(supplier_sku=None, title="X", qty=0, unit_cost_bonif=0),
        ParsedLine(supplier_sku=None, title="Y", qty=0, unit_cost_bonif=0),
        ParsedLine(supplier_sku=None, title="Z", qty=0, unit_cost_bonif=0),
    ]
    score = compute_classic_confidence(lines)
    assert score < 0.2, score
