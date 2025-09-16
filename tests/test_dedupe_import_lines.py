# NG-HEADER: Nombre de archivo: test_dedupe_import_lines.py
# NG-HEADER: Ubicación: tests/test_dedupe_import_lines.py
# NG-HEADER: Descripción: Pruebas unitarias del helper de anti-duplicados en importación de compras
# NG-HEADER: Lineamientos: Ver AGENTS.md

import os
os.environ.setdefault("DB_URL", "sqlite+aiosqlite:///:memory:")

from services.routers.purchases import _dedupe_lines, _normalize_title_for_dedupe  # type: ignore

def test_dedupe_by_sku_and_title():
    rows = [
        {"supplier_sku": "1234", "title": "Maceta Redonda 15cm"},
        {"supplier_sku": "1234", "title": "Maceta redonda 15 cm"},  # dup by SKU
        {"supplier_sku": "", "title": "Plántula de Tomate"},
        {"supplier_sku": None, "title": "Plantula  de  tomate  "},  # dup by normalized title
        {"supplier_sku": "5678", "title": "Sustrato Premium"},
    ]
    unique, dup_sku, dup_title = _dedupe_lines(rows)
    assert dup_sku == 1
    assert dup_title == 1
    assert len(unique) == 3


def test_normalize_title_removes_accents_and_spaces():
    t = _normalize_title_for_dedupe("  Plántula   Súper  ")
    assert t == "plantula super"
