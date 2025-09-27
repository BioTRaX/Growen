#!/usr/bin/env python
# NG-HEADER: Nombre de archivo: test_sales_metrics_and_limits.py
# NG-HEADER: Ubicación: tests/test_sales_metrics_and_limits.py
# NG-HEADER: Descripción: Pruebas métricas resumen y rate limiting creación ventas
# NG-HEADER: Lineamientos: Ver AGENTS.md
from __future__ import annotations

import asyncio
from decimal import Decimal
from fastapi import FastAPI
from fastapi.testclient import TestClient

from services.routers import sales as sales_router
from db.models import Product
from db.session import get_session

# Nota: Estas pruebas asumen un fixture global de DB en memoria o similar.
# Si el proyecto ya define fixtures reutilizables se podrían importar.
# Aquí se arma un app mínima para aislar.

app = FastAPI()
app.include_router(sales_router.router)

client = TestClient(app)

# Helpers (simples) ---------------------------------------------------------

def _auth_headers():
    # Simular roles y csrf; los deps reales deberían leer de sesión.
    return {
        "x-user-id": "1",
        "x-user-roles": "admin,colaborador",
        "x-csrf-token": "testtoken"
    }


def _create_product(session, title="Prod X", stock=50, price=10):
    p = Product(title=title, stock=stock, sku_root=title.lower().replace(" ", "-"))
    session.add(p)
    session.flush()
    # Simular variant mínima si el modelo real lo requiere, se omite si no es obligatorio.
    return p


# Tests --------------------------------------------------------------------

def test_rate_limit_sales_creation(monkeypatch):
    # Parchear bucket para no interferir con otras ejecuciones.
    from services.routers import sales as mod
    mod._RL_BUCKET.clear()

    # Necesitamos un producto para crear líneas (simplificado: omitimos persistencia real si la capa exige commit.)
    # Aquí simplemente se llama al endpoint repetidas veces sin items (aceptado por create_sale BORRADOR).
    for i in range(0, 30):
        r = client.post("/sales", json={"items": []}, headers=_auth_headers())
        assert r.status_code in (200, 201, 422) or r.status_code < 500  # tolerar validaciones menores
    r_fail = client.post("/sales", json={"items": []}, headers=_auth_headers())
    assert r_fail.status_code == 429, r_fail.text
    data = r_fail.json()
    assert data.get("detail", {}).get("code") == "rate_limited"


def test_metrics_summary_structure(monkeypatch):
    # Llamada vacía antes de crear ventas
    r = client.get("/sales/metrics/summary", headers=_auth_headers())
    assert r.status_code == 200
    data = r.json()
    assert "today" in data and "avg_confirm_ms" in data
    assert isinstance(data["today"].get("count"), int)
    assert isinstance(data["today"].get("net_total"), (int, float))
    assert "last7d" in data and len(data["last7d"]) == 7
    assert "top_products_today" in data


# TODO: pruebas adicionales (confirm bloquea SIN_VINCULAR, annul invalida cache, etc.)
