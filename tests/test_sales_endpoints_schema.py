#!/usr/bin/env python
# NG-HEADER: Nombre de archivo: test_sales_endpoints_schema.py
# NG-HEADER: Ubicación: tests/test_sales_endpoints_schema.py
# NG-HEADER: Descripción: Smoke tests que validan presencia de endpoints de ventas en OpenAPI
# NG-HEADER: Lineamientos: Ver AGENTS.md
from __future__ import annotations

from fastapi import FastAPI
from services.routers import sales, catalog, reports

# Construimos una app mínima con sólo los routers necesarios para evitar
# dependencias transversales (chat, telegram, etc.) durante la importación.
app = FastAPI(title="Growen-min-openapi")
app.include_router(sales.router)
app.include_router(catalog.router)
app.include_router(reports.router)


def _has_path(paths: dict, path: str, method: str) -> bool:
    p = paths.get(path)
    if not p:
        return False
    return method.lower() in p


def test_sales_endpoints_present_in_openapi():
    schema = app.openapi()
    paths = schema.get("paths", {})

    # Ventas: listado y detalle
    assert _has_path(paths, "/sales", "get")
    assert _has_path(paths, "/sales/{sale_id}", "get")

    # Acciones sobre venta
    assert _has_path(paths, "/sales/{sale_id}/confirm", "post")
    assert _has_path(paths, "/sales/{sale_id}/deliver", "post")
    assert _has_path(paths, "/sales/{sale_id}/annul", "post")
    assert _has_path(paths, "/sales/{sale_id}/payments", "post")
    assert _has_path(paths, "/sales/{sale_id}/receipt", "get")
    # Nuevos endpoints de edición BORRADOR
    assert _has_path(paths, "/sales/{sale_id}/lines", "post")
    assert _has_path(paths, "/sales/{sale_id}", "patch")
    # Returns
    assert _has_path(paths, "/sales/{sale_id}/returns", "post")
    assert _has_path(paths, "/sales/{sale_id}/returns", "get")

    # Reportes
    assert _has_path(paths, "/reports/sales", "get")
    assert _has_path(paths, "/reports/sales/export.csv", "get")

    # Clientes: historial y soft delete
    assert _has_path(paths, "/sales/customers/{cid}/sales", "get")
    assert _has_path(paths, "/sales/customers/{cid}", "delete")


def test_catalog_search_present_in_openapi():
    schema = app.openapi()
    paths = schema.get("paths", {})
    assert _has_path(paths, "/catalog/search", "get")
