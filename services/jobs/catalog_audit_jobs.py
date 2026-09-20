#!/usr/bin/env python
# NG-HEADER: Nombre de archivo: catalog_audit_jobs.py
# NG-HEADER: Ubicación: services/jobs/catalog_audit_jobs.py
# NG-HEADER: Descripción: Worker persistente y reanudable del auditor autónomo de catálogo.
# NG-HEADER: Lineamientos: Ver AGENTS.md
"""Procesa un catálogo secuencialmente y libera el thread mientras espera Enrich."""

from __future__ import annotations

import asyncio
import json
import os
import sys
import threading
import time
from datetime import datetime, timezone
from urllib.parse import urlparse

import dramatiq
from sqlalchemy import func, select, update

if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

import services.jobs  # noqa: F401
from db.models import CanonicalContentVersion, CanonicalEnrichmentJob, CanonicalProduct, CatalogAuditFeedback, CatalogAuditItem, CatalogAuditRun
from db.session import SessionLocal
from services.catalog_audit.ollama_client import CatalogAuditOllamaClient, SemanticAuditError
from services.catalog_audit.repository import canonical_content, canonical_snapshot, canonical_taxonomy
from services.catalog_audit.rules import CRITICAL_FLAGS, audit_catalog_content
from services.enrichment.service import create_enrichment_job, dispatch_enrichment_job


TERMINAL_ITEM_STATUSES = {
    "skipped_unchanged", "canonical_required", "clean", "auto_fixed", "needs_review",
    "quarantined", "failed", "cancelled",
}
ENRICH_ACTIVE = {"queued", "running"}
ENRICH_USABLE = {"applied", "partially_applied", "review_required"}
PROTECTED_FIELDS = {
    "id", "name", "ng_sku", "sku", "sku_custom", "sale_price", "market_price_reference", "stock",
}
ALLOWED_AUTOFIX_FIELDS = {
    "description_html", "weight_kg", "height_cm", "width_cm", "depth_cm", "technical_specs", "usage_instructions",
}


def _event(event: str, **fields) -> None:
    print(json.dumps({
        "timestamp": datetime.now(timezone.utc).isoformat(), "service": "catalog_audit_worker",
        "event": event, **fields,
    }, ensure_ascii=False, default=str), flush=True)


def _heartbeat_loop() -> None:
    try:
        import redis
        client = redis.from_url(os.getenv("REDIS_URL", "redis://127.0.0.1:6379/0"))
    except Exception:
        return
    ttl = max(int(os.getenv("CATALOG_AUDIT_HEARTBEAT_TTL_SECONDS", "60")), 15)
    while True:
        try:
            client.setex("growen:catalog_audit_worker:heartbeat", ttl, json.dumps({
                "timestamp": datetime.now(timezone.utc).isoformat(), "queue": "catalog_audit", "version": "1",
            }))
        except Exception:
            pass
        time.sleep(max(5, ttl // 3))


def _has_useful_content(product: CanonicalProduct) -> bool:
    return bool(
        (product.description_html or "").strip()
        or product.technical_specs
        or product.usage_instructions
        or any(value is not None for value in (product.weight_kg, product.height_cm, product.width_cm, product.depth_cm))
    )


def _independent_sources(urls: list[str]) -> set[str]:
    return {urlparse(url).netloc.lower().removeprefix("www.") for url in urls if urlparse(url).netloc}


def _eligible_corrections(semantic: dict) -> list[dict]:
    eligible = []
    for correction in semantic.get("fields") or []:
        field = correction.get("field")
        sources = correction.get("sources") or []
        if (
            field in ALLOWED_AUTOFIX_FIELDS
            and field not in PROTECTED_FIELDS
            and float(correction.get("confidence") or 0) >= 0.95
            and len(_independent_sources(sources)) >= 2
            and "proposed_value" in correction
        ):
            eligible.append(correction)
    return eligible


async def _wait_for_enrich(run: CatalogAuditRun, item: CatalogAuditItem, product: CanonicalProduct, session) -> bool:
    job = await session.get(CanonicalEnrichmentJob, item.enrichment_job_id) if item.enrichment_job_id else None
    if not job:
        job = await session.scalar(select(CanonicalEnrichmentJob).where(
            CanonicalEnrichmentJob.canonical_product_id == product.id,
            CanonicalEnrichmentJob.status.in_(ENRICH_ACTIVE),
        ))
    if not job:
        previous_attempts = await session.scalar(select(func.count(CanonicalEnrichmentJob.id)).where(
            CanonicalEnrichmentJob.batch_id == run.id,
            CanonicalEnrichmentJob.canonical_product_id == product.id,
        )) or 0
        request_id = f"audit:{run.id[:16]}:{product.id}:{previous_attempts + 1}"[:64]
        job, created = await create_enrichment_job(
            session, canonical_id=product.id, requested_product_id=None, client_request_id=request_id,
            scope="full", requested_by_user_id=run.requested_by_user_id, batch_id=run.id,
        )
        if created:
            await dispatch_enrichment_job(job, session)
    item.enrichment_job_id = job.id
    if job.status in ENRICH_ACTIVE:
        item.status = "waiting_enrich"
        run.status = "waiting_enrich"
        await session.commit()
        return True
    if job.status in ENRICH_USABLE and not _has_useful_content(product):
        item.status = "needs_review"
        item.error_code = "enrich_review_required"
        item.error_message = "Enrich terminó sin campos aplicables; requiere revisión manual."
        item.completed_at = datetime.utcnow()
        product.catalog_audit_status = "needs_review"
        product.catalog_audited_at = datetime.utcnow()
        await session.flush()
        product.last_catalog_audit_item_id = item.id
        return False
    if job.status not in ENRICH_USABLE:
        item.status = "failed"
        item.error_code = "enrich_missing_content"
        item.error_message = "Enrich terminó sin contenido útil para auditar."
        item.completed_at = datetime.utcnow()
        return False
    item.status = "pending"
    return False


async def _audit_item(run: CatalogAuditRun, item: CatalogAuditItem, session) -> bool:
    product = await session.get(CanonicalProduct, item.canonical_product_id)
    if not product:
        item.status = "failed"
        item.error_code = "canonical_not_found"
        item.completed_at = datetime.utcnow()
        return False
    if not _has_useful_content(product) and run.enrich_missing:
        return await _wait_for_enrich(run, item, product, session)
    item.status = "auditing"
    item.started_at = item.started_at or datetime.utcnow()
    # Ollama puede demorar varios minutos. Persistir el estado antes de la
    # llamada permite que Dashboard y la vista del run muestren trabajo real.
    await session.commit()
    taxonomy = canonical_taxonomy(product)
    classification_feedback = await session.scalar(select(CatalogAuditFeedback).where(
        CatalogAuditFeedback.active.is_(True), CatalogAuditFeedback.kind == "classification",
        CatalogAuditFeedback.canonical_product_id == product.id,
    ).order_by(CatalogAuditFeedback.version.desc()).limit(1))
    if classification_feedback:
        taxonomy["audit_class"] = (classification_feedback.payload_json or {}).get("product_class")
    deterministic = audit_catalog_content(
        product_name=product.name, brand=product.brand, taxonomy=taxonomy, content=canonical_content(product)
    )
    item.product_class = deterministic.product_class.value
    item.score = deterministic.score
    item.passed = deterministic.passed
    item.findings_json = deterministic.to_dict()
    if run.mode == "deterministic_only":
        item.status = "needs_review"
        item.error_code = "semantic_audit_skipped"
        item.completed_at = datetime.utcnow()
        product.catalog_audit_status = "partial"
        return False
    try:
        semantic_client = CatalogAuditOllamaClient()
        semantic = await semantic_client.audit({
            "name": product.name, "brand": product.brand, "taxonomy": taxonomy,
            "content": canonical_content(product), "deterministic": deterministic.to_dict(),
        })
    except SemanticAuditError as exc:
        item.status = "failed"
        item.error_code = str(exc)
        item.error_message = "La evaluación semántica falló de forma cerrada."
        item.completed_at = datetime.utcnow()
        return False
    item.semantic_json = semantic
    item.evidence_json = sorted({url for field in semantic["fields"] for url in field.get("sources") or []})
    item.corrections_json = _eligible_corrections(semantic)
    critical = bool(set(deterministic.flags) & CRITICAL_FLAGS) or bool(semantic.get("critical"))
    if run.auto_fix and item.corrections_json and deterministic.passed and not critical and item.auto_fix_attempts == 0:
        expected_revision = product.content_revision
        before = canonical_snapshot(product)
        changes = {correction["field"]: correction["proposed_value"] for correction in item.corrections_json}
        changes["content_revision"] = expected_revision + 1
        cas = await session.execute(update(CanonicalProduct).where(
            CanonicalProduct.id == product.id,
            CanonicalProduct.content_revision == expected_revision,
        ).values(**changes))
        if cas.rowcount != 1:
            item.status = "needs_review"
            item.error_code = "content_revision_conflict"
        else:
            session.add(CanonicalContentVersion(
                canonical_product_id=product.id, origin="catalog_audit_pre_fix", revision=expected_revision,
                snapshot_json=before, is_applied=False, created_by_user_id=run.requested_by_user_id,
            ))
            await session.refresh(product)
            session.add(CanonicalContentVersion(
                canonical_product_id=product.id, origin="catalog_audit_auto_fix", revision=product.content_revision,
                snapshot_json=canonical_snapshot(product), is_applied=True, created_by_user_id=run.requested_by_user_id,
            ))
            item.auto_fix_attempts = 1
            rerun = audit_catalog_content(
                product_name=product.name, brand=product.brand, taxonomy=taxonomy,
                content=canonical_content(product),
            )
            item.findings_json = rerun.to_dict()
            item.score = rerun.score
            item.passed = rerun.passed
            critical = bool(set(rerun.flags) & CRITICAL_FLAGS)
            try:
                semantic_rerun = await semantic_client.audit({
                    "name": product.name, "brand": product.brand, "taxonomy": taxonomy,
                    "content": canonical_content(product), "deterministic": rerun.to_dict(),
                })
                semantic_rerun["_initial_result"] = semantic
                item.semantic_json = semantic_rerun
                item.evidence_json = sorted({
                    url for field in semantic_rerun["fields"] for url in field.get("sources") or []
                })
                still_failing = (
                    critical
                    or bool(semantic_rerun.get("critical"))
                    or int(semantic_rerun["score"]) < 75
                    or bool(semantic_rerun["fields"])
                )
                item.status = "quarantined" if still_failing else "auto_fixed"
            except SemanticAuditError as exc:
                item.status = "quarantined"
                item.error_code = f"semantic_reaudit_{exc}"
                item.error_message = "La autocorrección fue aplicada, pero su reauditoría semántica falló."
    elif critical:
        item.status = "quarantined"
    elif deterministic.passed and int(semantic["score"]) >= 75 and not semantic["fields"]:
        item.status = "clean"
    else:
        item.status = "needs_review"
    product.catalog_audit_status = item.status
    product.catalog_audited_at = datetime.utcnow()
    item.completed_at = datetime.utcnow()
    await session.flush()
    product.last_catalog_audit_item_id = item.id
    return False


async def _finish_run(run: CatalogAuditRun, session) -> None:
    counts = dict((await session.execute(
        select(CatalogAuditItem.status, func.count(CatalogAuditItem.id)).where(CatalogAuditItem.run_id == run.id).group_by(CatalogAuditItem.status)
    )).all())
    run.processed_items = sum(counts.get(status, 0) for status in TERMINAL_ITEM_STATUSES)
    run.clean_items = counts.get("clean", 0) + counts.get("auto_fixed", 0) + counts.get("skipped_unchanged", 0)
    run.issue_items = run.processed_items - run.clean_items
    if run.processed_items >= run.total_items:
        run.status = "completed_with_issues" if run.issue_items else "completed"
        run.is_active_slot = False
        run.completed_at = datetime.utcnow()


async def process_catalog_audit_run_async(run_id: str) -> None:
    async with SessionLocal() as session:
        run = await session.get(CatalogAuditRun, run_id)
        if not run or not run.is_active_slot:
            return
        run.status = "running"
        run.started_at = run.started_at or datetime.utcnow()
        await session.commit()
        items = (await session.scalars(
            select(CatalogAuditItem).where(CatalogAuditItem.run_id == run.id).order_by(CatalogAuditItem.id)
        )).all()
        for item in items:
            if item.status in TERMINAL_ITEM_STATUSES:
                continue
            if run.cancel_requested:
                item.status = "cancelled"
                item.completed_at = datetime.utcnow()
                continue
            waiting = await _audit_item(run, item, session)
            await session.commit()
            if waiting:
                process_catalog_audit_run.send_with_options(args=(run.id,), delay=15_000)
                _event("run_waiting_enrich", run_id=run.id, item_id=item.id)
                return
        if run.cancel_requested:
            run.status = "cancelled"
            run.is_active_slot = False
            run.completed_at = datetime.utcnow()
        else:
            await _finish_run(run, session)
        await session.commit()
        _event("run_completed", run_id=run.id, status=run.status)


async def _fail_run(run_id: str, exc: Exception) -> None:
    async with SessionLocal() as session:
        run = await session.get(CatalogAuditRun, run_id)
        if not run or not run.is_active_slot:
            return
        run.status = "failed"
        run.is_active_slot = False
        run.error_code = type(exc).__name__
        run.error_message = "El worker no pudo completar la ejecución; puede reanudarse."
        run.completed_at = datetime.utcnow()
        await session.commit()
        _event("run_failed", run_id=run.id, error_code=run.error_code)


async def _recover_active_runs_async() -> int:
    """Reencola runs persistidos que quedaron activos tras reiniciar el worker."""
    async with SessionLocal() as session:
        run_ids = (await session.scalars(
            select(CatalogAuditRun.id).where(
                CatalogAuditRun.is_active_slot.is_(True),
                CatalogAuditRun.status.in_(("queued", "running", "waiting_enrich")),
            ).order_by(CatalogAuditRun.created_at)
        )).all()
    for run_id in run_ids:
        process_catalog_audit_run.send(run_id)
    if run_ids:
        _event("active_runs_recovered", count=len(run_ids), run_ids=run_ids)
    return len(run_ids)


def _recover_active_runs_on_startup() -> None:
    try:
        asyncio.run(_recover_active_runs_async())
    except Exception as exc:
        _event("active_run_recovery_failed", error_code=type(exc).__name__)


@dramatiq.actor(queue_name="catalog_audit", max_retries=0, time_limit=900_000)
def process_catalog_audit_run(run_id: str) -> None:
    try:
        asyncio.run(process_catalog_audit_run_async(run_id))
    except Exception as exc:
        asyncio.run(_fail_run(run_id, exc))


if os.getenv("CATALOG_AUDIT_HEARTBEAT_ENABLED", "0") == "1":
    threading.Thread(target=_heartbeat_loop, daemon=True, name="catalog-audit-heartbeat").start()
    threading.Thread(target=_recover_active_runs_on_startup, daemon=True, name="catalog-audit-recovery").start()
