#!/usr/bin/env python
# NG-HEADER: Nombre de archivo: test_canonical_sku_update.py
# NG-HEADER: Ubicación: tests/test_canonical_sku_update.py
# NG-HEADER: Descripción: Validación transaccional de la edición del SKU canónico.
# NG-HEADER: Lineamientos: Ver AGENTS.md
from __future__ import annotations

import pytest

from db.models import CanonicalProduct


@pytest.mark.asyncio
async def test_duplicate_canonical_sku_is_rejected_without_applying_change(client_collab, db_session):
    existing = CanonicalProduct(
        name="Existente",
        ng_sku="NG-910001",
        sku_custom="ABC_0001_DEF",
    )
    target = CanonicalProduct(
        name="A editar",
        ng_sku="NG-910002",
        sku_custom="XYZ_0002_GHI",
    )
    db_session.add_all([existing, target])
    await db_session.commit()

    response = await client_collab.patch(
        f"/canonical-products/{target.id}",
        json={"sku_custom": "abc_0001_def"},
    )

    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "duplicate_sku"
    await db_session.refresh(target)
    assert target.sku_custom == "XYZ_0002_GHI"


@pytest.mark.asyncio
async def test_canonical_sku_update_normalizes_and_validates_format(client_collab, db_session):
    target = CanonicalProduct(
        name="A editar",
        ng_sku="NG-920001",
        sku_custom="OLD_0001_SKU",
    )
    db_session.add(target)
    await db_session.commit()

    invalid = await client_collab.patch(
        f"/canonical-products/{target.id}",
        json={"sku_custom": "sin-formato"},
    )
    assert invalid.status_code == 422
    await db_session.refresh(target)
    assert target.sku_custom == "OLD_0001_SKU"

    updated = await client_collab.patch(
        f"/canonical-products/{target.id}",
        json={"sku_custom": "new_0042_a1b"},
    )
    assert updated.status_code == 200, updated.text
    assert updated.json()["sku_custom"] == "NEW_0042_A1B"
    await db_session.refresh(target)
    assert target.sku_custom == "NEW_0042_A1B"
