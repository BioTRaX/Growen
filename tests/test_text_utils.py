#!/usr/bin/env python
# NG-HEADER: Nombre de archivo: test_text_utils.py
# NG-HEADER: Ubicación: tests/test_text_utils.py
# NG-HEADER: Descripción: Tests unitarios para db/text_utils.py (estilización de nombres).
# NG-HEADER: Lineamientos: Ver AGENTS.md
"""Tests para la función stylize_product_name."""
import pytest
from db.text_utils import stylize_product_name


class TestStylizeProductName:
    """Tests para stylize_product_name."""

    def test_basic_title_case(self):
        """Convierte mayúsculas a Title Case."""
        assert stylize_product_name("FEEDING BIO GROW") == "Feeding Bio Grow"

    def test_preserves_units_in_parens(self):
        """Mantiene unidades de medida en mayúsculas dentro de paréntesis."""
        assert stylize_product_name("FEEDING BIO GROW (125 GR)") == "Feeding Bio Grow (125 GR)"
        assert stylize_product_name("FERTILIZANTE ORGANICO (1 L)") == "Fertilizante Organico (1 L)"

    def test_preserves_standalone_units(self):
        """Preserva unidades de medida en mayúsculas."""
        assert stylize_product_name("ACEITE DE NEEM 250 ML") == "Aceite de Neem 250 ML"
        assert stylize_product_name("SUSTRATO 50 L") == "Sustrato 50 L"

    def test_preserves_acronyms(self):
        """Preserva acrónimos comunes en mayúsculas."""
        # "600W" se preserva como está (número + letra se capitaliza)
        assert stylize_product_name("LUZ LED GROW 600W") == "Luz LED Grow 600W"
        assert stylize_product_name("MEDIDOR PH DIGITAL") == "Medidor PH Digital"
        assert stylize_product_name("FERTILIZANTE NPK") == "Fertilizante NPK"

    def test_lowercase_connectors(self):
        """Conectores en español van en minúsculas (excepto al inicio)."""
        assert stylize_product_name("ACEITE DE NEEM") == "Aceite de Neem"
        assert stylize_product_name("DE LA TIERRA") == "De la Tierra"

    def test_handles_none(self):
        """Retorna None si la entrada es None."""
        assert stylize_product_name(None) is None

    def test_handles_empty_string(self):
        """Retorna cadena vacía si la entrada es vacía."""
        assert stylize_product_name("") == ""

    def test_mixed_case_input(self):
        """Normaliza entrada con mayúsculas/minúsculas mezcladas."""
        assert stylize_product_name("feeding BIO grow") == "Feeding Bio Grow"

    def test_numbers_preserved(self):
        """Los números se preservan sin cambios."""
        assert stylize_product_name("TOP MAX 500ML") == "Top Max 500ML"
        assert stylize_product_name("BIO GROW 1L") == "Bio Grow 1L"

    def test_multiple_parens(self):
        """Maneja múltiples secciones entre paréntesis."""
        # Caso edge: solo la última sección entre paréntesis es procesada especialmente
        result = stylize_product_name("PRODUCTO (TIPO A) (500 GR)")
        assert "GR" in result  # La unidad debe estar en mayúsculas

    def test_weight_units(self):
        """Unidades de peso se preservan en mayúsculas."""
        assert "KG" in stylize_product_name("SUSTRATO 25 KG")
        assert "GR" in stylize_product_name("SEMILLAS (10 GR)")
        assert "MG" in stylize_product_name("SOLUCION 500 MG")

    def test_volume_units(self):
        """Unidades de volumen se preservan en mayúsculas."""
        assert "ML" in stylize_product_name("ACEITE 100 ML")
        assert "L" in stylize_product_name("FERTILIZANTE 5 L")
        assert "CC" in stylize_product_name("SOLUCION 250 CC")

