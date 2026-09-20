#!/usr/bin/env python
# NG-HEADER: Nombre de archivo: test_enrichment_auditor.py
# NG-HEADER: Ubicación: tests/test_enrichment_auditor.py
# NG-HEADER: Descripción: Pruebas unitarias de auditoría y coherencia física para Enrich v2.
# NG-HEADER: Lineamientos: Ver AGENTS.md
from __future__ import annotations


from services.enrichment.auditor import (
    FLAG_BOILERPLATE,
    FLAG_DIMENSIONS_MISMATCH,
    FLAG_ENTITY_MISMATCH,
    FLAG_INVALID_DIMENSIONS,
    FLAG_MALFORMED_HTML,
    FLAG_PHYSICAL_DISCREPANCY,
    audit_enrichment_proposal,
    extract_volume_liters,
    extract_weight_kg_from_text,
)


def test_extract_volume_and_weight_from_text():
    assert extract_volume_liters("Top Crop Deeper Underground 250ml") == 0.25
    assert extract_volume_liters("Fertilizante Bio Bloom 1L") == 1.0
    assert extract_volume_liters("Sustrato GrowMix Multipropósito 80 Litros") == 80.0
    assert extract_volume_liters("Aceite Neem 100 cc") == 0.1
    assert extract_volume_liters("Producto sin volumen") is None

    assert extract_weight_kg_from_text("Tricodermas en polvo 50g") == 0.05
    assert extract_weight_kg_from_text("Sal de Epsom 1.5kg") == 1.5
    assert extract_weight_kg_from_text("Azúcar 2 kilos") == 2.0
    assert extract_weight_kg_from_text("Sin peso") is None


def test_valid_liquid_proposal_passes_with_high_score():
    proposal = {
        "description_html": "<p>Estimulador radicular de alta concentración formulado a base de ácidos húmicos y fúlvicos.</p>",
        "weight_kg": 0.32,
        "height_cm": 15.0,
        "width_cm": 6.0,
        "depth_cm": 6.0,
    }
    result = audit_enrichment_proposal(
        product_name="Deeper Underground 250ml",
        brand="Top Crop",
        proposal=proposal,
        original_name="TOP CROP DEEPER UNDERGROUND 250 ML",
    )
    assert result.passed is True
    assert result.score >= 90
    assert not result.flags
    assert not result.warnings


def test_substrate_weight_discrepancy_blocks_proposal():
    # 80L de sustrato con un peso propuesto absurdo de 0.25 kg
    proposal = {
        "description_html": "<p>Sustrato profesional para cultivo indoor y exterior.</p>",
        "weight_kg": 0.25,
        "height_cm": 80.0,
        "width_cm": 40.0,
        "depth_cm": 25.0,
    }
    result = audit_enrichment_proposal(
        product_name="Sustrato Growmix 80L",
        brand="Growmix",
        proposal=proposal,
    )
    assert result.passed is False
    assert FLAG_PHYSICAL_DISCREPANCY in result.flags
    assert any("inverosímil para un sustrato de 80 L" in w for w in result.warnings)
    assert "weight_kg" in result.field_issues


def test_liquid_weight_contradicts_volume():
    # Fertilizante de 1L con peso propuesto de 10 kg
    proposal = {
        "description_html": "<p>Fertilizante para fase de floración.</p>",
        "weight_kg": 10.0,
        "height_cm": 25.0,
        "width_cm": 8.0,
        "depth_cm": 8.0,
    }
    result = audit_enrichment_proposal(
        product_name="Top Bloom 1L",
        brand="Top Crop",
        proposal=proposal,
    )
    assert result.passed is False
    assert FLAG_PHYSICAL_DISCREPANCY in result.flags
    assert "weight_kg" in result.field_issues


def test_negative_or_zero_dimensions_fail():
    proposal = {
        "description_html": "<p>Maceta plástica soplada.</p>",
        "weight_kg": 0.15,
        "height_cm": -5.0,
        "width_cm": 0.0,
        "depth_cm": 15.0,
    }
    result = audit_enrichment_proposal(
        product_name="Maceta 10L",
        brand=None,
        proposal=proposal,
    )
    assert result.passed is False
    assert FLAG_INVALID_DIMENSIONS in result.flags
    assert "height_cm" in result.field_issues
    assert "width_cm" in result.field_issues


def test_box_volume_smaller_than_liquid_volume_fails():
    # 1 Litro de líquido necesita al menos ~1000 cm3 de volumen de caja envolvente.
    # Si las dimensiones son 5x5x5 cm = 125 cm3 = 0.125 L, es físicamente imposible.
    proposal = {
        "description_html": "<p>Fertilizante líquido.</p>",
        "weight_kg": 1.1,
        "height_cm": 5.0,
        "width_cm": 5.0,
        "depth_cm": 5.0,
    }
    result = audit_enrichment_proposal(
        product_name="Fertilizante 1L",
        brand="Generico",
        proposal=proposal,
    )
    assert result.passed is False
    assert FLAG_DIMENSIONS_MISMATCH in result.flags
    assert any("menor al volumen declarado" in w for w in result.warnings)


def test_boilerplate_metadiscourse_penalizes_score():
    proposal = {
        "description_html": "<p>Según la investigación realizada, este producto sirve para crecimiento.</p>",
        "weight_kg": 0.3,
        "height_cm": 15.0,
        "width_cm": 6.0,
        "depth_cm": 6.0,
    }
    result = audit_enrichment_proposal(
        product_name="Top Veg 250ml",
        brand="Top Crop",
        proposal=proposal,
    )
    assert FLAG_BOILERPLATE in result.flags
    assert any("metadiscurso" in w for w in result.warnings)
    assert result.score < 80


def test_unbalanced_html_penalizes_score():
    proposal = {
        "description_html": "<p>Párrafo abierto sin cierre",
        "weight_kg": 0.3,
        "height_cm": 15.0,
        "width_cm": 6.0,
        "depth_cm": 6.0,
    }
    result = audit_enrichment_proposal(
        product_name="Top Veg 250ml",
        brand="Top Crop",
        proposal=proposal,
    )
    assert FLAG_MALFORMED_HTML in result.flags
    assert any("no balanceadas" in w for w in result.warnings)


def test_brand_confusion_triggers_entity_mismatch():
    # Producto de Top Crop cuya descripción menciona a Biobizz sin nombrar Top Crop
    proposal = {
        "description_html": "<p>Excelente fertilizante de biobizz para tus plantas.</p>",
        "weight_kg": 0.3,
        "height_cm": 15.0,
        "width_cm": 6.0,
        "depth_cm": 6.0,
    }
    result = audit_enrichment_proposal(
        product_name="Deeper Underground 250ml",
        brand="Top Crop",
        proposal=proposal,
    )
    assert FLAG_ENTITY_MISMATCH in result.flags
    assert any("marca competidora" in w for w in result.warnings)
