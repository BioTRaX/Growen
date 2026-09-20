#!/usr/bin/env python
# NG-HEADER: Nombre de archivo: test_product_canonical_detail.py
# NG-HEADER: Ubicación: tests/test_product_canonical_detail.py
# NG-HEADER: Descripción: Agregación canónica del detalle conservando Product.id en la ruta.
# NG-HEADER: Lineamientos: Ver AGENTS.md
from __future__ import annotations

from decimal import Decimal

import pytest

from db.models import CanonicalProduct, Product, ProductEquivalence, Supplier, SupplierProduct
from services.routers.catalog import get_product


@pytest.mark.asyncio
async def test_equivalent_products_share_canonical_content_and_stock(db_session):
    canonical = CanonicalProduct(
        name="Producto Canónico",
        ng_sku="NG-900001",
        description_html="<p>Contenido común.</p>",
        weight_kg=Decimal("1.250"),
        technical_specs={"composición": "NPK"},
        content_revision=2,
    )
    supplier = Supplier(slug="proveedor-test", name="Proveedor Test")
    first = Product(sku_root="INT-1", title="Nombre original A", stock=Decimal("3"))
    second = Product(sku_root="INT-2", title="Nombre original B", stock=Decimal("4"))
    db_session.add_all([canonical, supplier, first, second])
    await db_session.flush()
    offers = [
        SupplierProduct(
            supplier_id=supplier.id,
            supplier_product_id=f"SUP-{product.id}",
            title=product.title,
            internal_product_id=product.id,
        )
        for product in (first, second)
    ]
    db_session.add_all(offers)
    await db_session.flush()
    db_session.add_all(
        [
            ProductEquivalence(
                supplier_id=supplier.id,
                supplier_product_id=offer.id,
                canonical_product_id=canonical.id,
                source="manual",
            )
            for offer in offers
        ]
    )
    await db_session.commit()

    detail_a = await get_product(first.id, db_session)
    detail_b = await get_product(second.id, db_session)

    assert detail_a["id"] == first.id
    assert detail_b["id"] == second.id
    assert detail_a["description_html"] == detail_b["description_html"] == "<p>Contenido común.</p>"
    assert detail_a["stock_total"] == detail_b["stock_total"] == 7.0
    assert [item["product_id"] for item in detail_a["linked_inventory"]] == [first.id, second.id]
    assert "market_price_reference" not in detail_a


@pytest.mark.asyncio
async def test_internal_product_without_canonical_is_read_only_basic_detail(db_session):
    product = Product(sku_root="SIN-CANON", title="Registro interno", stock=Decimal("1"))
    db_session.add(product)
    await db_session.commit()
    detail = await get_product(product.id, db_session)
    assert detail["canonical_status"] == "canonical_required"
    assert detail["stock_total"] == 1.0
