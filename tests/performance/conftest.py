#!/usr/bin/env python
# NG-HEADER: Nombre de archivo: conftest.py
# NG-HEADER: Ubicación: tests/performance/conftest.py
# NG-HEADER: Descripción: Fixtures específicas para tests de performance
# NG-HEADER: Lineamientos: Ver AGENTS.md

"""
Fixtures compartidas para tests de performance.
Usa pytest_asyncio.fixture para fixtures async.
"""

from __future__ import annotations

from decimal import Decimal
from typing import List

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession

from db.models import Category, Supplier


@pytest_asyncio.fixture
async def db(db_session: AsyncSession) -> AsyncSession:
    """
    Fixture que proporciona sesión de BD heredada de db_session (conftest raíz).
    Usa directamente la sesión del conftest principal.
    """
    return db_session


@pytest_asyncio.fixture
async def test_category(db: AsyncSession) -> Category:
    """Crea categoría de prueba para productos de performance."""
    category = Category(
        name="Categoría Test Performance"
    )
    db.add(category)
    await db.commit()
    await db.refresh(category)
    return category


@pytest_asyncio.fixture
async def test_supplier(db: AsyncSession) -> Supplier:
    """Crea proveedor de prueba para performance."""
    supplier = Supplier(
        name="Proveedor Test Performance",
        email="test.perf@example.com"
    )
    db.add(supplier)
    await db.commit()
    await db.refresh(supplier)
    return supplier
