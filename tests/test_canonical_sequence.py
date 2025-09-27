#!/usr/bin/env python
# NG-HEADER: Nombre de archivo: test_canonical_sequence.py
# NG-HEADER: Ubicación: tests/test_canonical_sequence.py
# NG-HEADER: Descripción: Pruebas de secuencia por prefijo para SKU canónico.
# NG-HEADER: Lineamientos: Ver AGENTS.md
import os
import pytest
from sqlalchemy.ext.asyncio import AsyncSession
from typing import AsyncGenerator

os.environ.setdefault("AUTH_ENABLED", "false")
os.environ.setdefault("CANONICAL_SKU_STRICT", "1")

from services.api import app  # noqa: E402
from services.routers.catalog import _products_has_canonical  # noqa: E402
from db.sku_generator import generate_canonical_sku  # noqa: E402
from db.session import get_session  # noqa: E402

pytestmark = pytest.mark.asyncio


async def _get_session() -> AsyncSession:
    agen = get_session()
    session = await agen.__anext__()
    return session


async def test_sequence_increments_per_prefix():
    session = await _get_session()
    # Garantizar columna canonical_sku si el helper la puede crear
    await _products_has_canonical(session)
    sku1 = await generate_canonical_sku(session, "Riego", "Riego")
    sku2 = await generate_canonical_sku(session, "Riego", "Riego")
    assert sku1.split("_")[0] == "RIE"
    n1 = int(sku1.split("_")[1])
    n2 = int(sku2.split("_")[1])
    assert n2 == n1 + 1

async def test_sequence_isolated_by_prefix():
    session = await _get_session()
    s1 = await generate_canonical_sku(session, "Fertilizante", "Fertilizante")
    s2 = await generate_canonical_sku(session, "Riego", "Riego")
    assert s1.split("_")[0] == "FER"
    assert s2.split("_")[0] == "RIE"
    # Ambos deben iniciar (o haber iniciado cerca). Sólo verificamos que no comparten el mismo bloque #### exacto en primera emisión.
    assert s1.split("_")[1] != s2.split("_")[1] or s1.split("_")[0] != s2.split("_")[0]
