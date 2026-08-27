#!/usr/bin/env python
# NG-HEADER: Nombre de archivo: test_catalog_legacy_cleanup.py
# NG-HEADER: Ubicación: tests/test_catalog_legacy_cleanup.py
# NG-HEADER: Descripción: Verifica que los adaptadores de catálogo no conserven código inalcanzable.
# NG-HEADER: Lineamientos: Ver AGENTS.md

import ast
from pathlib import Path


def test_adaptadores_de_enrich_terminan_en_el_primer_return():
    source = Path("services/routers/catalog.py").read_text(encoding="utf-8")
    module = ast.parse(source)
    targets = {"enrich_multiple_products", "enrich_product", "delete_product_enrichment"}

    functions = {
        node.name: node
        for node in ast.walk(module)
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name in targets
    }

    assert set(functions) == targets
    for name, function in functions.items():
        first_return = next(
            (index for index, statement in enumerate(function.body) if isinstance(statement, ast.Return)),
            None,
        )
        assert first_return is not None, name
        assert first_return == len(function.body) - 1, name
