#!/usr/bin/env python
# NG-HEADER: Nombre de archivo: test_canonical_helpers.py
# NG-HEADER: Ubicación: tests/test_canonical_helpers.py
# NG-HEADER: Descripción: Pruebas unitarias de helpers de SKU canónico.
# NG-HEADER: Lineamientos: Ver AGENTS.md
from services.routers.canonical_products import _slugify3, build_canonical_sku


def test_slugify3_removes_diacritics_and_pads():
    assert _slugify3("Fertílïzántés", "FAL")=="FER"
    assert _slugify3("x", "FAL") == "XXX"
    assert _slugify3(None, "SIN") == "SIN"


def test_build_canonical_sku_defaults_when_missing_names():
    sku = build_canonical_sku(None, None, 1)
    assert sku == "SIN_0001_GEN"
    sku2 = build_canonical_sku("Riego", "", 23)
    assert sku2.startswith("RIE_0023_")
