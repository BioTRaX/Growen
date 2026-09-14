#!/usr/bin/env python
# NG-HEADER: Nombre de archivo: test_catalog_audit_domain.py
# NG-HEADER: Ubicación: tests/test_catalog_audit_domain.py
# NG-HEADER: Descripción: Regresiones del dominio autónomo de auditoría de catálogo.
# NG-HEADER: Lineamientos: Ver AGENTS.md
from __future__ import annotations

from services.catalog_audit.fingerprint import build_input_hash
from services.catalog_audit.rules import (
    FLAG_PHYSICAL_DISCREPANCY,
    ProductClass,
    audit_catalog_content,
    classify_product,
)


def test_maceta_20_litros_es_contenedor_y_no_liquido() -> None:
    classification = classify_product("Maceta Soplada 20L", None, None)

    assert classification == ProductClass.CONTAINER

    result = audit_catalog_content(
        product_name="Maceta Soplada 20L",
        brand=None,
        taxonomy=None,
        content={"weight_kg": 0.35, "height_cm": 30, "width_cm": 30, "depth_cm": 30},
    )

    assert result.product_class == ProductClass.CONTAINER
    assert FLAG_PHYSICAL_DISCREPANCY not in result.flags


def test_fingerprint_es_estable_ante_orden_y_espacios() -> None:
    left = build_input_hash(
        name="  Sustrato Premium 20L ",
        brand="Grow Mix",
        taxonomy={"category": "Sustratos", "tags": ["Indoor", "Tierra"]},
        content={"technical_specs": {"ph": "6.0", "ec": 1.2}, "description_html": "<p>Uso general</p>"},
        rules_version="catalog-audit-r1",
        feedback_version="2",
    )
    right = build_input_hash(
        name="Sustrato Premium 20L",
        brand="grow mix",
        taxonomy={"tags": ["tierra", "indoor"], "category": "sustratos"},
        content={"description_html": "<p>Uso general</p>", "technical_specs": {"ec": 1.2, "ph": "6.0"}},
        rules_version="catalog-audit-r1",
        feedback_version="2",
    )

    assert left == right


def test_fingerprint_cambia_con_contenido_reglas_o_feedback() -> None:
    common = {
        "name": "Fertilizante 1L",
        "brand": "Marca",
        "taxonomy": {"category": "Fertilizantes"},
        "content": {"weight_kg": 1.1},
        "rules_version": "catalog-audit-r1",
        "feedback_version": "0",
    }
    baseline = build_input_hash(**common)

    assert build_input_hash(**{**common, "content": {"weight_kg": 1.2}}) != baseline
    assert build_input_hash(**{**common, "rules_version": "catalog-audit-r2"}) != baseline
    assert build_input_hash(**{**common, "feedback_version": "1"}) != baseline
