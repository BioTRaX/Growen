#!/usr/bin/env python
# NG-HEADER: Nombre de archivo: catalog_audits.py
# NG-HEADER: Ubicación: services/routers/catalog_audits.py
# NG-HEADER: Descripción: API persistente del auditor autónomo de catálogo.
# NG-HEADER: Lineamientos: Ver AGENTS.md
"""Creación, seguimiento, cancelación y tratamiento de auditorías."""

from __future__ import annotations

import asyncio
import os
from typing import Literal
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field, model_validator
from sqlalchemy import func, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from db.models import (
    CanonicalContentVersion,
    CanonicalProduct,
    CatalogAuditFeedback,
    CatalogAuditItem,
    CatalogAuditRun,
    ProductEquivalence,
    SupplierProduct,
)
from db.session import get_session
from services.auth import SessionData, require_csrf, require_roles
from services.catalog_audit.ollama_client import CatalogAuditOllamaClient
from services.catalog_audit.repository import canonical_snapshot, create_run_items
from services.jobs.catalog_audit_jobs import process_catalog_audit_run


router = APIRouter(prefix="/canonical-products/catalog-audits", tags=["catalog-audits"])
legacy_router = APIRouter(prefix="/canonical-products", tags=["catalog-audits"])


class CatalogAuditCreate(BaseModel):
    scope: Literal["all", "pending", "selected"] = "pending"
    canonical_product_ids: list[int] | None = Field(default=None, max_length=500)
    include_orphans: bool = True
    mode: Literal["full", "deterministic_only"] = "full"
    enrich_missing: bool = False
    auto_fix: bool = False

    @model_validator(mode="after")
    def selected_needs_ids(self):
        if self.scope == "selected" and not self.canonical_product_ids:
            raise ValueError("canonical_product_ids es obligatorio para scope selected")
        return self


class CatalogAuditResolution(BaseModel):
    action: Literal["reaudit", "accept_exception", "classification", "apply_correction", "restore_version", "release_quarantine"]
    note: str = Field(min_length=3, max_length=1000)
    product_class: Literal["liquid", "substrate", "container", "tent", "weight_product", "other"] | None = None
    corrections: dict | None = None
    expected_content_revision: int | None = Field(default=None, ge=0)
    version_id: int | None = Field(default=None, ge=1)


def _run_dict(run: CatalogAuditRun, *, include_items: bool = False) -> dict:
    payload = {
        "run_id": run.id, "scope": run.scope, "mode": run.mode, "status": run.status,
        "include_orphans": run.include_orphans, "enrich_missing": run.enrich_missing, "auto_fix": run.auto_fix,
        "total_items": run.total_items, "processed_items": run.processed_items,
        "clean_items": run.clean_items, "issue_items": run.issue_items,
        "cancel_requested": run.cancel_requested,
        "created_at": run.created_at.isoformat() if run.created_at else None,
        "started_at": run.started_at.isoformat() if run.started_at else None,
        "completed_at": run.completed_at.isoformat() if run.completed_at else None,
        "error": {"code": run.error_code, "message": run.error_message} if run.error_code else None,
    }
    if include_items:
        payload["items"] = [_item_dict(item) for item in run.items]
    return payload


def _item_dict(
    item: CatalogAuditItem,
    *,
    content_revision: int | None = None,
    content_versions: list[dict] | None = None,
    canonical_name: str | None = None,
    product_detail_id: int | None = None,
) -> dict:
    return {
        "item_id": item.id, "canonical_product_id": item.canonical_product_id, "product_id": item.product_id,
        "status": item.status, "input_hash": item.input_hash, "rules_version": item.rules_version,
        "feedback_version": item.feedback_version, "product_class": item.product_class,
        "score": item.score, "passed": item.passed, "findings": item.findings_json,
        "semantic": item.semantic_json, "corrections": item.corrections_json or [],
        "evidence": item.evidence_json or [], "enrichment_job_id": item.enrichment_job_id,
        "reused_item_id": item.reused_item_id, "resolution": item.resolution,
        "content_revision": content_revision, "content_versions": content_versions or [],
        "canonical_name": canonical_name, "product_detail_id": product_detail_id,
        "error": {"code": item.error_code, "message": item.error_message} if item.error_code else None,
    }


@router.post("", status_code=status.HTTP_202_ACCEPTED, dependencies=[Depends(require_csrf)])
async def create_catalog_audit(
    payload: CatalogAuditCreate,
    session: AsyncSession = Depends(get_session),
    user: SessionData = Depends(require_roles("colaborador", "admin")),
) -> dict:
    if payload.auto_fix and user.role != "admin":
        raise HTTPException(status_code=403, detail="Sólo admin puede habilitar autocorrección")
    preflight = await _catalog_audit_preflight()
    if not preflight["worker"]["ok"]:
        raise HTTPException(status_code=503, detail={"code": "catalog_audit_worker_unavailable"})
    if payload.mode == "full" and not preflight["ollama"]["ok"]:
        raise HTTPException(status_code=503, detail={"code": preflight["ollama"].get("code") or "ollama_unavailable"})
    if payload.enrich_missing and not preflight["enrichment_worker"]["ok"]:
        raise HTTPException(status_code=503, detail={"code": "enrichment_worker_unavailable"})
    stmt = select(CanonicalProduct).order_by(CanonicalProduct.id)
    selected_ids = sorted(set(payload.canonical_product_ids or []))
    if payload.scope == "selected":
        stmt = stmt.where(CanonicalProduct.id.in_(selected_ids))
    # ``pending`` también recorre los canónicos marcados como limpios: el hash
    # persistido decide si se reutilizan o si cambiaron desde la última auditoría.
    products = (await session.scalars(stmt)).all()
    if payload.scope == "selected" and len(products) != len(selected_ids):
        raise HTTPException(status_code=404, detail="Uno o más canónicos no existen")
    run = CatalogAuditRun(
        id=uuid4().hex, scope=payload.scope, mode=payload.mode, include_orphans=payload.include_orphans,
        enrich_missing=payload.enrich_missing, auto_fix=payload.auto_fix, status="queued", is_active_slot=True,
        requested_ids=selected_ids, requested_by_user_id=user.user.id if user.user else None,
    )
    session.add(run)
    try:
        await session.flush()
        await create_run_items(session, run, products, include_orphans=payload.include_orphans)
        await session.commit()
    except IntegrityError as exc:
        await session.rollback()
        raise HTTPException(status_code=409, detail={
            "code": "active_catalog_audit_exists", "message": "Ya existe una auditoría global activa",
        }) from exc
    process_catalog_audit_run.send(run.id)
    return {"run_id": run.id, "status": run.status, "status_url": f"/canonical-products/catalog-audits/{run.id}"}


@router.get("", dependencies=[Depends(require_roles("colaborador", "admin"))])
async def list_catalog_audits(session: AsyncSession = Depends(get_session), limit: int = 25) -> dict:
    runs = (await session.scalars(select(CatalogAuditRun).order_by(CatalogAuditRun.created_at.desc()).limit(min(max(limit, 1), 100)))).all()
    return {"items": [_run_dict(run) for run in runs]}


async def _catalog_audit_preflight() -> dict:
    ollama = await CatalogAuditOllamaClient().preflight()
    worker = {"ok": False, "code": "redis_unavailable"}
    enrichment_worker = {"ok": False, "code": "redis_unavailable"}
    try:
        import redis
        client = redis.from_url(os.getenv("REDIS_URL", "redis://127.0.0.1:6379/0"), socket_timeout=1)
        worker = {"ok": bool(client.get("growen:catalog_audit_worker:heartbeat")), "code": None}
        enrichment_worker = {"ok": bool(client.get("growen:enrichment_worker:heartbeat")), "code": None}
    except Exception:
        pass
    return {"ollama": ollama, "worker": worker, "enrichment_worker": enrichment_worker, "queue": "catalog_audit"}


def _catalog_audit_queue_status() -> dict:
    broker_ok = False
    ready = 0
    delayed = 0
    try:
        import redis

        client = redis.from_url(
            os.getenv("REDIS_URL", "redis://127.0.0.1:6379/0"),
            socket_timeout=1,
        )
        broker_ok = bool(client.ping())
        ready = int(client.llen("dramatiq:catalog_audit"))
        delayed = int(client.zcard("dramatiq:catalog_audit.DQ"))
    except Exception:
        pass
    return {"broker_ok": broker_ok, "ready": ready, "delayed": delayed}


def _catalog_audit_runtime_status() -> dict:
    from services.orchestrator import status_service

    status = status_service("catalog_audit_worker")
    return {
        "status": status.status,
        "ok": status.ok,
        "pid": status.pid,
        "detail": status.detail,
    }


@router.get("/preflight", dependencies=[Depends(require_roles("colaborador", "admin"))])
async def catalog_audit_preflight() -> dict:
    return await _catalog_audit_preflight()


@router.get("/summary", dependencies=[Depends(require_roles("colaborador", "admin"))])
async def catalog_audit_summary(session: AsyncSession = Depends(get_session)) -> dict:
    """Resume runtime, cola y trabajo persistido sin ejecutar el modelo semántico."""
    queue_status, runtime_status = await asyncio.gather(
        asyncio.to_thread(_catalog_audit_queue_status),
        asyncio.to_thread(_catalog_audit_runtime_status),
    )
    run_counts_result = await session.execute(
        select(CatalogAuditRun.status, func.count(CatalogAuditRun.id)).group_by(CatalogAuditRun.status)
    )
    run_counts = {str(status_name): int(count) for status_name, count in run_counts_result.all()}
    item_counts_result = await session.execute(
        select(CatalogAuditItem.status, func.count(CatalogAuditItem.id)).group_by(CatalogAuditItem.status)
    )
    item_counts = {str(status_name): int(count) for status_name, count in item_counts_result.all()}
    active_runs = await session.scalar(
        select(func.count(CatalogAuditRun.id)).where(CatalogAuditRun.is_active_slot.is_(True))
    ) or 0
    recent_runs = (await session.scalars(
        select(CatalogAuditRun).order_by(CatalogAuditRun.created_at.desc()).limit(10)
    )).all()
    total_canonical = await session.scalar(select(func.count(CanonicalProduct.id))) or 0
    audited_canonical = await session.scalar(
        select(func.count(CanonicalProduct.id)).where(CanonicalProduct.last_catalog_audit_item_id.is_not(None))
    ) or 0
    quarantined_canonical = await session.scalar(
        select(func.count(CanonicalProduct.id)).where(CanonicalProduct.catalog_audit_status == "quarantined")
    ) or 0
    return {
        "worker": {**runtime_status, **queue_status},
        "runs": {
            "total": sum(run_counts.values()),
            "active": int(active_runs),
            "by_status": run_counts,
            "recent": [_run_dict(run) for run in recent_runs],
        },
        "items": {"by_status": item_counts},
        "catalog_coverage": {
            "total_canonical": int(total_canonical),
            "audited": int(audited_canonical),
            "pending": max(0, int(total_canonical) - int(audited_canonical)),
            "quarantined": int(quarantined_canonical),
        },
    }


@router.get("/{run_id}", dependencies=[Depends(require_roles("colaborador", "admin"))])
async def get_catalog_audit(run_id: str, session: AsyncSession = Depends(get_session)) -> dict:
    run = await session.scalar(select(CatalogAuditRun).options(selectinload(CatalogAuditRun.items)).where(CatalogAuditRun.id == run_id))
    if not run:
        raise HTTPException(status_code=404, detail="Auditoría no encontrada")
    canonical_ids = {item.canonical_product_id for item in run.items if item.canonical_product_id}
    revisions: dict[int, int] = {}
    names: dict[int, str] = {}
    product_links: dict[int, int] = {}
    versions: dict[int, list[dict]] = {canonical_id: [] for canonical_id in canonical_ids}
    if canonical_ids:
        canonical_rows = (await session.execute(select(
            CanonicalProduct.id, CanonicalProduct.name, CanonicalProduct.content_revision,
        ).where(CanonicalProduct.id.in_(canonical_ids)))).all()
        names = {canonical_id: name for canonical_id, name, _revision in canonical_rows}
        revisions = {canonical_id: revision for canonical_id, _name, revision in canonical_rows}
        linked_rows = (await session.execute(
            select(
                ProductEquivalence.canonical_product_id,
                func.min(SupplierProduct.internal_product_id),
            )
            .join(SupplierProduct, SupplierProduct.id == ProductEquivalence.supplier_product_id)
            .where(
                ProductEquivalence.canonical_product_id.in_(canonical_ids),
                SupplierProduct.internal_product_id.is_not(None),
            )
            .group_by(ProductEquivalence.canonical_product_id)
        )).all()
        product_links = dict(linked_rows)
        stored_versions = (await session.scalars(select(CanonicalContentVersion).where(
            CanonicalContentVersion.canonical_product_id.in_(canonical_ids),
        ).order_by(CanonicalContentVersion.created_at.desc()))).all()
        for version in stored_versions:
            versions[version.canonical_product_id].append({
                "version_id": version.id,
                "revision": version.revision,
                "origin": version.origin,
                "created_at": version.created_at.isoformat() if version.created_at else None,
            })
    payload = _run_dict(run)
    payload["items"] = [
        _item_dict(
            item,
            content_revision=revisions.get(item.canonical_product_id),
            content_versions=versions.get(item.canonical_product_id, []),
            canonical_name=names.get(item.canonical_product_id),
            product_detail_id=product_links.get(item.canonical_product_id) or item.product_id,
        )
        for item in run.items
    ]
    return payload


@router.post("/{run_id}/cancel", dependencies=[Depends(require_csrf), Depends(require_roles("colaborador", "admin"))])
async def cancel_catalog_audit(run_id: str, session: AsyncSession = Depends(get_session)) -> dict:
    run = await session.get(CatalogAuditRun, run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Auditoría no encontrada")
    if not run.is_active_slot:
        raise HTTPException(status_code=409, detail="La auditoría ya terminó")
    run.cancel_requested = True
    await session.commit()
    process_catalog_audit_run.send(run.id)
    return {"run_id": run.id, "status": run.status, "cancel_requested": True}


@router.post("/{run_id}/retry", status_code=202, dependencies=[Depends(require_csrf), Depends(require_roles("colaborador", "admin"))])
async def retry_catalog_audit(run_id: str, session: AsyncSession = Depends(get_session)) -> dict:
    run = await session.scalar(select(CatalogAuditRun).options(selectinload(CatalogAuditRun.items)).where(CatalogAuditRun.id == run_id))
    if not run:
        raise HTTPException(status_code=404, detail="Auditoría no encontrada")
    if run.is_active_slot:
        raise HTTPException(status_code=409, detail="La auditoría sigue activa")
    run.status, run.is_active_slot, run.cancel_requested, run.completed_at = "queued", True, False, None
    run.error_code, run.error_message = None, None
    for item in run.items:
        if item.status in {"failed", "cancelled"}:
            item.status, item.error_code, item.error_message, item.completed_at = "pending", None, None, None
            item.enrichment_job_id = None
    terminal_statuses = {
        "skipped_unchanged", "canonical_required", "clean", "auto_fixed",
        "needs_review", "quarantined", "failed", "cancelled",
    }
    clean_statuses = {"clean", "auto_fixed", "skipped_unchanged"}
    run.processed_items = sum(item.status in terminal_statuses for item in run.items)
    run.clean_items = sum(item.status in clean_statuses for item in run.items)
    run.issue_items = run.processed_items - run.clean_items
    try:
        await session.commit()
    except IntegrityError as exc:
        await session.rollback()
        raise HTTPException(status_code=409, detail={"code": "active_catalog_audit_exists"}) from exc
    process_catalog_audit_run.send(run.id)
    return {"run_id": run.id, "status": run.status}


@router.post("/{run_id}/items/{item_id}/resolve", dependencies=[Depends(require_csrf)])
async def resolve_catalog_audit_item(
    run_id: str, item_id: int, payload: CatalogAuditResolution,
    session: AsyncSession = Depends(get_session), user: SessionData = Depends(require_roles("colaborador", "admin")),
) -> dict:
    item = await session.scalar(select(CatalogAuditItem).where(CatalogAuditItem.id == item_id, CatalogAuditItem.run_id == run_id))
    if not item:
        raise HTTPException(status_code=404, detail="Ítem no encontrado")
    if payload.action != "reaudit" and user.role != "admin":
        raise HTTPException(status_code=403, detail="La resolución solicitada requiere admin")
    product = await session.get(CanonicalProduct, item.canonical_product_id) if item.canonical_product_id else None
    needs_reaudit = payload.action in {"reaudit", "classification", "apply_correction", "restore_version"}
    item.resolution = payload.action
    item.resolution_note = payload.note
    item.resolved_by_user_id = user.user.id if user.user else None
    if payload.action != "reaudit":
        if payload.action == "classification" and not payload.product_class:
            raise HTTPException(status_code=422, detail="product_class es obligatorio")
        if payload.action == "apply_correction":
            allowed = {"description_html", "weight_kg", "height_cm", "width_cm", "depth_cm", "technical_specs", "usage_instructions"}
            if not product or not payload.corrections or payload.expected_content_revision is None:
                raise HTTPException(status_code=422, detail="corrections y expected_content_revision son obligatorios")
            if not set(payload.corrections) <= allowed:
                raise HTTPException(status_code=422, detail="La corrección contiene campos protegidos")
            before = canonical_snapshot(product)
            changes = {**payload.corrections, "content_revision": payload.expected_content_revision + 1}
            cas = await session.execute(update(CanonicalProduct).where(
                CanonicalProduct.id == product.id,
                CanonicalProduct.content_revision == payload.expected_content_revision,
            ).values(**changes))
            if cas.rowcount != 1:
                raise HTTPException(status_code=409, detail={"code": "content_revision_conflict"})
            session.add(CanonicalContentVersion(
                canonical_product_id=product.id, origin="catalog_audit_pre_fix",
                revision=payload.expected_content_revision, snapshot_json=before, is_applied=False,
                created_by_user_id=user.user.id if user.user else None,
            ))
            await session.refresh(product)
            session.add(CanonicalContentVersion(
                canonical_product_id=product.id, origin="catalog_audit_manual_fix",
                revision=product.content_revision, snapshot_json=canonical_snapshot(product), is_applied=True,
                created_by_user_id=user.user.id if user.user else None,
            ))
        if payload.action == "restore_version":
            if not product or payload.version_id is None or payload.expected_content_revision is None:
                raise HTTPException(status_code=422, detail="version_id y expected_content_revision son obligatorios")
            version = await session.scalar(select(CanonicalContentVersion).where(
                CanonicalContentVersion.id == payload.version_id,
                CanonicalContentVersion.canonical_product_id == product.id,
            ))
            if not version:
                raise HTTPException(status_code=404, detail="Versión no encontrada")
            allowed = {"description_html", "weight_kg", "height_cm", "width_cm", "depth_cm", "technical_specs", "usage_instructions"}
            before = canonical_snapshot(product)
            restored = {key: value for key, value in version.snapshot_json.items() if key in allowed}
            restored["content_revision"] = payload.expected_content_revision + 1
            cas = await session.execute(update(CanonicalProduct).where(
                CanonicalProduct.id == product.id,
                CanonicalProduct.content_revision == payload.expected_content_revision,
            ).values(**restored))
            if cas.rowcount != 1:
                raise HTTPException(status_code=409, detail={"code": "content_revision_conflict"})
            session.add(CanonicalContentVersion(
                canonical_product_id=product.id, origin="catalog_audit_pre_restore",
                revision=payload.expected_content_revision, snapshot_json=before, is_applied=False,
                created_by_user_id=user.user.id if user.user else None,
            ))
            await session.refresh(product)
            session.add(CanonicalContentVersion(
                canonical_product_id=product.id, origin="catalog_audit_restore",
                revision=product.content_revision, snapshot_json=canonical_snapshot(product), is_applied=True,
                created_by_user_id=user.user.id if user.user else None,
            ))
        feedback = CatalogAuditFeedback(
            canonical_product_id=item.canonical_product_id,
            product_class=payload.product_class or item.product_class,
            kind="classification" if payload.action == "classification" else ("correction" if payload.action in {"apply_correction", "restore_version"} else "exception"),
            version=int(item.feedback_version or "0") + 1,
            payload_json={"action": payload.action, "note": payload.note, "product_class": payload.product_class},
            created_by_user_id=user.user.id if user.user else None,
        )
        session.add(feedback)
        if payload.action == "release_quarantine" and product:
            product.catalog_audit_status = "needs_review"
            item.status = "needs_review"
        elif payload.action == "accept_exception":
            item.status = "clean"
            if product:
                product.catalog_audit_status = "clean"
    new_run_id = None
    if needs_reaudit:
        if not product:
            raise HTTPException(status_code=409, detail="El ítem no tiene canónico para reauditar")
        origin_run = await session.get(CatalogAuditRun, run_id)
        new_run = CatalogAuditRun(
            id=uuid4().hex, scope="selected", mode=origin_run.mode if origin_run else "full",
            include_orphans=False, enrich_missing=origin_run.enrich_missing if origin_run else False,
            auto_fix=False, status="queued", is_active_slot=True,
            requested_ids=[product.id], requested_by_user_id=user.user.id if user.user else None,
        )
        session.add(new_run)
        try:
            await session.flush()
            await create_run_items(session, new_run, [product], include_orphans=False, force=True)
        except IntegrityError as exc:
            await session.rollback()
            raise HTTPException(status_code=409, detail={"code": "active_catalog_audit_exists"}) from exc
        new_run_id = new_run.id
    try:
        await session.commit()
    except IntegrityError as exc:
        await session.rollback()
        raise HTTPException(status_code=409, detail={"code": "active_catalog_audit_exists"}) from exc
    if new_run_id:
        process_catalog_audit_run.send(new_run_id)
    return {
        "item": _item_dict(item, content_revision=product.content_revision if product else None),
        "new_run_id": new_run_id,
    }


@legacy_router.get("/catalog-audit-report", dependencies=[Depends(require_roles("colaborador", "admin"))])
async def legacy_catalog_audit_report(session: AsyncSession = Depends(get_session)) -> dict:
    run = await session.scalar(select(CatalogAuditRun).options(selectinload(CatalogAuditRun.items)).where(
        CatalogAuditRun.status.in_(("completed", "completed_with_issues"))
    ).order_by(CatalogAuditRun.completed_at.desc()).limit(1))
    if not run:
        return {"run_id": None, "total_audited": 0, "clean_count": 0, "issues_count": 0, "issues": []}
    issues = [_item_dict(item) for item in run.items if item.status not in {"clean", "auto_fixed", "skipped_unchanged"}]
    return {"run_id": run.id, "total_audited": run.processed_items, "clean_count": run.clean_items, "issues_count": len(issues), "issues": issues}
