#!/usr/bin/env python
# NG-HEADER: Nombre de archivo: repository.py
# NG-HEADER: Ubicación: services/catalog_audit/repository.py
# NG-HEADER: Descripción: Persistencia, deduplicación y consultas del auditor de catálogo.
# NG-HEADER: Lineamientos: Ver AGENTS.md
"""Operaciones transaccionales del auditor autónomo."""

from __future__ import annotations

from collections.abc import Iterable
from datetime import datetime
from decimal import Decimal

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from db.models import (
    CanonicalProduct,
    CatalogAuditFeedback,
    CatalogAuditItem,
    CatalogAuditRun,
    Product,
    ProductEquivalence,
    SupplierProduct,
)
from services.catalog_audit.fingerprint import build_input_hash
from services.catalog_audit.rules import classify_product


RULESET_VERSION = "catalog-audit-r1"
REUSABLE_STATUSES = {"clean", "auto_fixed", "needs_review", "quarantined"}


def canonical_content(product: CanonicalProduct) -> dict:
    return {
        "description_html": product.description_html,
        "weight_kg": product.weight_kg,
        "height_cm": product.height_cm,
        "width_cm": product.width_cm,
        "depth_cm": product.depth_cm,
        "technical_specs": product.technical_specs or {},
        "usage_instructions": product.usage_instructions or {},
        "content_revision": product.content_revision,
    }


def _json_snapshot_value(value):
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, dict):
        return {str(key): _json_snapshot_value(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_snapshot_value(item) for item in value]
    return value


def canonical_snapshot(product: CanonicalProduct) -> dict:
    """Devuelve una versión JSON-segura sin alterar la huella auditable."""
    return _json_snapshot_value(canonical_content(product))


def canonical_auditable_content(product: CanonicalProduct) -> dict:
    """Contenido efectivo; excluye metadatos de concurrencia del fingerprint."""
    return {
        key: value
        for key, value in canonical_content(product).items()
        if key != "content_revision"
    }


def canonical_taxonomy(product: CanonicalProduct) -> dict:
    return {"category_id": product.category_id, "subcategory_id": product.subcategory_id}


async def applicable_feedback_version(session: AsyncSession, product: CanonicalProduct) -> str:
    product_class = classify_product(
        product.name,
        canonical_taxonomy(product),
        canonical_auditable_content(product),
    ).value
    version = await session.scalar(
        select(func.max(CatalogAuditFeedback.version)).where(
            CatalogAuditFeedback.active.is_(True),
            or_(
                CatalogAuditFeedback.canonical_product_id == product.id,
                (
                    CatalogAuditFeedback.canonical_product_id.is_(None)
                    & or_(
                        CatalogAuditFeedback.product_class.is_(None),
                        CatalogAuditFeedback.product_class == product_class,
                    )
                ),
            ),
        )
    )
    return str(version or 0)


async def create_run_items(
    session: AsyncSession,
    run: CatalogAuditRun,
    products: Iterable[CanonicalProduct],
    *,
    include_orphans: bool,
    force: bool = False,
) -> list[CatalogAuditItem]:
    """Crea un ítem por identidad y reutiliza una auditoría completa idéntica."""
    items: list[CatalogAuditItem] = []
    for product in products:
        feedback_version = await applicable_feedback_version(session, product)
        input_hash = build_input_hash(
            name=product.name,
            brand=product.brand,
            taxonomy=canonical_taxonomy(product),
            content=canonical_auditable_content(product),
            rules_version=RULESET_VERSION,
            feedback_version=feedback_version,
        )
        previous = None if force else await session.scalar(
            select(CatalogAuditItem)
            .where(
                CatalogAuditItem.canonical_product_id == product.id,
                CatalogAuditItem.input_hash == input_hash,
                CatalogAuditItem.rules_version == RULESET_VERSION,
                CatalogAuditItem.feedback_version == feedback_version,
                CatalogAuditItem.status.in_(REUSABLE_STATUSES),
            )
            .order_by(CatalogAuditItem.id.desc())
            .limit(1)
        )
        reused_issue = previous and previous.status in {"needs_review", "quarantined"}
        item = CatalogAuditItem(
            run_id=run.id,
            canonical_product_id=product.id,
            target_key=f"canonical:{product.id}",
            input_hash=input_hash,
            rules_version=RULESET_VERSION,
            feedback_version=feedback_version,
            status=previous.status if reused_issue else ("skipped_unchanged" if previous else "pending"),
            reused_item_id=previous.id if previous else None,
            product_class=previous.product_class if reused_issue else None,
            score=previous.score if reused_issue else None,
            passed=previous.passed if reused_issue else None,
            findings_json=previous.findings_json if reused_issue else None,
            semantic_json=previous.semantic_json if reused_issue else None,
            corrections_json=previous.corrections_json if reused_issue else None,
            evidence_json=previous.evidence_json if reused_issue else None,
            error_code=previous.error_code if reused_issue else None,
            error_message=previous.error_message if reused_issue else None,
            completed_at=datetime.utcnow() if previous else None,
        )
        session.add(item)
        items.append(item)

    if include_orphans:
        linked_product_ids = (
            select(SupplierProduct.internal_product_id)
            .join(ProductEquivalence, ProductEquivalence.supplier_product_id == SupplierProduct.id)
            .where(SupplierProduct.internal_product_id.is_not(None))
        )
        orphan_rows = (await session.scalars(select(Product).where(Product.id.not_in(linked_product_ids)))).all()
        for product in orphan_rows:
            input_hash = build_input_hash(
                name=product.title,
                brand=str(product.brand_id or ""),
                taxonomy={"category_id": product.category_id, "subcategory_id": product.subcategory_id},
                content={"description_html": product.description_html, "technical_specs": product.technical_specs or {}},
                rules_version=RULESET_VERSION,
                feedback_version="0",
            )
            item = CatalogAuditItem(
                run_id=run.id,
                product_id=product.id,
                target_key=f"product:{product.id}",
                input_hash=input_hash,
                rules_version=RULESET_VERSION,
                status="canonical_required",
                completed_at=datetime.utcnow(),
            )
            session.add(item)
            items.append(item)

    run.total_items = len(items)
    await session.flush()
    return items
