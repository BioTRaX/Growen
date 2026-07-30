#!/usr/bin/env python
# NG-HEADER: Nombre de archivo: enrichment_jobs.py
# NG-HEADER: Ubicación: services/jobs/enrichment_jobs.py
# NG-HEADER: Descripción: Worker dedicado de investigación y contenido canónico Enrich v2.
# NG-HEADER: Lineamientos: Ver AGENTS.md
"""Pipeline persistente Enrich v2, sin responsabilidades monetarias."""

from __future__ import annotations

import asyncio
import html
import json
import logging
import os
import sys
import threading
import time
from datetime import datetime, timezone
from urllib.parse import urlparse

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import selectinload

if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

try:
    import services.jobs  # noqa: F401
    import dramatiq  # type: ignore
except Exception:  # pragma: no cover
    class _StubModule:
        @staticmethod
        def actor(*_args, **_kwargs):
            def decorate(function):
                return function
            return decorate

    dramatiq = _StubModule()  # type: ignore

from agent_core.mcp_client import mcp_client_manager
from ai.providers.ollama_provider import OllamaProvider
from ai.providers.openai_provider import OpenAIProvider
from db.models import (
    CanonicalContentVersion,
    CanonicalEnrichmentJob,
    CanonicalEnrichmentSource,
    CanonicalKnowledgeAsset,
    CanonicalKnowledgeVersion,
    CanonicalProduct,
)
from db.session import SessionLocal
from services.knowledge.service import register_discovered_asset
from services.routers.enrichment import CONTENT_FIELDS, canonical_snapshot


logger = logging.getLogger(__name__)
TECHNICAL_FIELDS = {
    "weight_kg",
    "height_cm",
    "width_cm",
    "depth_cm",
    "technical_specs",
    "usage_instructions",
}


def _heartbeat_loop() -> None:
    try:
        import redis

        client = redis.from_url(os.getenv("REDIS_URL", "redis://127.0.0.1:6379/0"))
    except Exception:
        return
    ttl = max(_integer("ENRICHMENT_HEARTBEAT_TTL_SECONDS", 60), 15)
    while True:
        try:
            client.setex(
                "growen:enrichment_worker:heartbeat",
                ttl,
                json.dumps(
                    {
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                        "queue": "enrichment",
                        "version": "2",
                    }
                ),
            )
        except Exception as exc:
            logger.warning("No se pudo publicar heartbeat Enrich v2: %s", type(exc).__name__)
        time.sleep(max(5, ttl // 3))


def _event(event: str, **fields) -> None:
    payload = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "service": "enrichment_worker",
        "event": event,
        **fields,
    }
    print(json.dumps(payload, ensure_ascii=False, default=str), flush=True)


def _number(name: str, default: float) -> float:
    try:
        return float(os.getenv(name, str(default)))
    except ValueError:
        return default


def _integer(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, str(default)))
    except ValueError:
        return default


if os.getenv("ENRICHMENT_HEARTBEAT_ENABLED", "1") == "1":
    threading.Thread(target=_heartbeat_loop, name="enrichment-heartbeat", daemon=True).start()


def _parse_json_response(raw: str, prompt: str) -> dict:
    value = (raw or "").strip()
    if not value or value == prompt or value.startswith(("openai:", "ollama:")):
        raise RuntimeError("El proveedor IA no produjo una respuesta válida")
    if value.startswith("```"):
        value = value.removeprefix("```json").removeprefix("```").removesuffix("```").strip()
    try:
        parsed = json.loads(value)
    except json.JSONDecodeError as exc:
        raise RuntimeError("La respuesta IA no cumple el esquema JSON") from exc
    if not isinstance(parsed, dict):
        raise RuntimeError("La respuesta IA debe ser un objeto JSON")
    description = parsed.get("description_text")
    if description is not None and not isinstance(description, str):
        raise RuntimeError("description_text debe ser texto")
    technical = parsed.get("technical") or {}
    if not isinstance(technical, dict):
        raise RuntimeError("technical debe ser un objeto")
    return parsed


async def _generate_with_provider(prompt: str) -> tuple[dict, str, str]:
    mode = os.getenv("ENRICH_AI_MODE", "auto").strip().lower()
    if mode not in {"auto", "openai", "ollama"}:
        raise RuntimeError("ENRICH_AI_MODE inválido")
    errors: list[str] = []
    candidates = ["openai", "ollama"] if mode == "auto" else [mode]
    for name in candidates:
        try:
            if name == "openai":
                provider = OpenAIProvider()
                provider.model = os.getenv("ENRICH_OPENAI_MODEL", "gpt-4.1-mini")
                if not provider.api_key:
                    raise RuntimeError("OPENAI_API_KEY no configurada")
                raw = await provider.generate_async(prompt, user_context={"role": "admin", "channel": "web"})
            else:
                if not os.getenv("OLLAMA_HOST"):
                    raise RuntimeError("OLLAMA_HOST no configurado")
                provider = OllamaProvider()
                provider.model = os.getenv("ENRICH_OLLAMA_MODEL", "llama3.1")
                raw = "".join(await asyncio.to_thread(lambda: list(provider.generate(prompt))))
            return _parse_json_response(raw, prompt), name, provider.model
        except Exception as exc:
            errors.append(f"{name}:{type(exc).__name__}")
            if mode != "auto":
                break
    raise RuntimeError(f"No hay proveedor IA válido ({', '.join(errors)})")


def _render_description(text: str | None) -> str | None:
    if not text:
        return None
    paragraphs = [part.strip() for part in text.replace("\r", "").split("\n") if part.strip()]
    return "".join(f"<p>{html.escape(part)}</p>" for part in paragraphs)


def _source_domain(url: str) -> str:
    return (urlparse(url).hostname or "").lower().removeprefix("www.")


def _official_source(source: dict, brand: str | None) -> bool:
    domain = _source_domain(source.get("url") or "")
    brand_key = "".join(character for character in (brand or "").lower() if character.isalnum())
    domain_key = "".join(character for character in domain if character.isalnum())
    return bool(brand_key and brand_key in domain_key) or source.get("source_type") in {
        "manufacturer",
        "official_manual",
    }


def _classify_discovered_source(item: dict, fetched: dict, product: CanonicalProduct) -> tuple[set[str], float]:
    """Clasificación conservadora: sólo confirma señales deterministas fuertes."""
    url = fetched.get("url") or item.get("url") or ""
    domain = _source_domain(url)
    brand_key = "".join(character for character in (product.brand or "").lower() if character.isalnum())
    domain_key = "".join(character for character in domain if character.isalnum())
    title = str(item.get("title") or "").lower()
    mime_type = str(fetched.get("mime_type") or "").lower()
    labels: set[str] = set()
    confidence = 0.0
    if brand_key and brand_key in domain_key:
        labels.update({"manufacturer", "official"})
        confidence = 0.95
    if ("manual" in title or "manual" in url.lower() or mime_type == "application/pdf") and confidence >= 0.90:
        labels.add("manual")
        confidence = max(confidence, 0.92)
    return labels, confidence


async def _research(product: CanonicalProduct, db) -> list[dict]:
    max_results = min(max(_integer("ENRICH_MAX_SEARCH_RESULTS", 8), 1), 8)
    max_sources = min(max(_integer("ENRICH_MAX_FETCH_SOURCES", 5), 1), 5)
    sources: list[dict] = []
    seen_urls: set[str] = set()

    assets = list(
        (
            await db.scalars(
                select(CanonicalKnowledgeAsset)
                .options(
                    selectinload(CanonicalKnowledgeAsset.locations),
                    selectinload(CanonicalKnowledgeAsset.labels),
                    selectinload(CanonicalKnowledgeAsset.capabilities),
                    selectinload(CanonicalKnowledgeAsset.versions),
                )
                .where(
                    CanonicalKnowledgeAsset.canonical_product_id == product.id,
                    CanonicalKnowledgeAsset.status == "confirmed",
                    CanonicalKnowledgeAsset.exclude_from_enrichment.is_(False),
                )
                .order_by(CanonicalKnowledgeAsset.trust_score.desc(), CanonicalKnowledgeAsset.id)
            )
        ).unique()
    )
    for asset in assets:
        capabilities = {
            item.capability_code for item in asset.capabilities
            if item.enabled and item.capability_code != "price"
        }
        if not capabilities:
            continue
        for location in sorted(asset.locations, key=lambda item: (not item.is_primary, item.id)):
            if len(sources) >= max_sources:
                break
            if not location.url or location.url in seen_urls:
                continue
            version = next(
                (
                    item for item in sorted(asset.versions, key=lambda value: value.version, reverse=True)
                    if item.location_id == location.id and item.extracted_text
                ),
                None,
            )
            if version:
                text_value = str(version.extracted_text)
                mime_type = location.mime_type
                content_hash = version.content_hash
            else:
                fetched = await mcp_client_manager.call_tool(
                    "fetch_web_document",
                    {"url": location.url},
                    role="admin",
                    server_name="web_search",
                )
                if fetched.get("error") or not fetched.get("text"):
                    continue
                text_value = str(fetched.get("text"))
                mime_type = fetched.get("mime_type")
                content_hash = fetched.get("content_hash")
            seen_urls.add(location.url)
            sources.append({
                "url": location.url,
                "title": asset.title,
                "snippet": None,
                "mime_type": mime_type,
                "content_hash": content_hash,
                "text": text_value[:12_000],
                "source_type": next((item.label for item in asset.labels if item.label in {"manufacturer", "supplier", "market"}), "knowledge"),
                "knowledge_asset_id": asset.id,
                "knowledge_version_id": version.id if version else None,
            })
        if len(sources) >= max_sources:
            break

    if len(sources) >= max_sources:
        return sources

    identity = " ".join(filter(None, [product.brand, product.name, product.sku_custom or product.ng_sku]))
    queries = [
        f'{identity} ficha técnica manual fabricante',
        f'{identity} technical specifications official manual',
    ]
    results: list[dict] = []
    for query in queries:
        response = await mcp_client_manager.call_tool(
            "search_web",
            {"query": query, "max_results": max_results},
            role="admin",
            server_name="web_search",
        )
        for item in response.get("items") or []:
            url = item.get("url")
            if url and url not in seen_urls:
                seen_urls.add(url)
                results.append(item)
            if len(results) >= max_results:
                break
        if len(results) >= max_results:
            break
    for item in results:
        if len(sources) >= max_sources:
            break
        fetched = await mcp_client_manager.call_tool(
            "fetch_web_document",
            {"url": item["url"]},
            role="admin",
            server_name="web_search",
        )
        if fetched.get("error") or not fetched.get("text"):
            continue
        labels, classification_confidence = _classify_discovered_source(item, fetched, product)
        discovered = await register_discovered_asset(
            db,
            canonical_product_id=product.id,
            title=item.get("title") or item["url"],
            url=fetched.get("url") or item["url"],
            labels=labels,
            classification_confidence=classification_confidence,
        )
        sources.append({
                "url": fetched.get("url") or item["url"],
                "title": item.get("title"),
                "snippet": item.get("snippet"),
                "mime_type": fetched.get("mime_type"),
                "content_hash": fetched.get("content_hash"),
                "text": str(fetched.get("text"))[:12_000],
                "source_type": (
                    "manufacturer"
                    if "manufacturer" in labels
                    else "official_manual"
                    if "manual" in labels
                    else "web"
                ),
                "knowledge_asset_id": discovered.id,
                "knowledge_version_id": None,
        })
    if os.getenv("ENRICH_WEB_REQUIRED", "1") == "1" and not sources:
        raise RuntimeError("No se obtuvieron fuentes web válidas")
    return sources


def _compose_prompt(product: CanonicalProduct, sources: list[dict], scope: str) -> str:
    evidence = [
        {
            "url": source["url"],
            "title": source.get("title"),
            "text": source.get("text"),
        }
        for source in sources
    ]
    return (
        "Eres un investigador de catálogo. Devuelve exclusivamente JSON válido; "
        "no incluyas HTML ni precios, valores de mercado o estimaciones monetarias. "
        "No inventes especificaciones numéricas. Cada dato técnico requiere source_url.\n\n"
        f"Producto canónico: {json.dumps({'name': product.name, 'brand': product.brand, 'sku': product.sku_custom or product.ng_sku}, ensure_ascii=False)}\n"
        f"Alcance: {scope}\n"
        f"Fuentes: {json.dumps(evidence, ensure_ascii=False)}\n"
        "Esquema de salida EXACTO: "
        '{"description_text":string|null,"description_confidence":number,'
        '"technical":{"weight_kg":{"value":number|null,"confidence":number,"source_url":string|null},'
        '"height_cm":{"value":number|null,"confidence":number,"source_url":string|null},'
        '"width_cm":{"value":number|null,"confidence":number,"source_url":string|null},'
        '"depth_cm":{"value":number|null,"confidence":number,"source_url":string|null},'
        '"technical_specs":{"value":object,"confidence":number,"source_url":string|null},'
        '"usage_instructions":{"value":object,"confidence":number,"source_url":string|null}}}'
    )


def _build_result(
    product: CanonicalProduct,
    generated: dict,
    sources: list[dict],
    scope: str,
) -> tuple[dict, list[str]]:
    proposal: dict = {}
    confidence: dict = {}
    field_sources: dict[str, list[str]] = {}
    source_urls = {source["url"] for source in sources}
    independent_domains = {_source_domain(url) for url in source_urls}
    official = any(_official_source(source, product.brand) for source in sources)
    auto_fields: list[str] = []
    minimum = _number("ENRICH_AUTO_APPLY_MIN_CONFIDENCE", 0.90)
    technical_minimum = _number("ENRICH_TECHNICAL_MIN_CONFIDENCE", 0.90)
    min_domains = _integer("ENRICH_MIN_INDEPENDENT_SOURCES", 2)
    auto_enabled = os.getenv("ENRICH_AUTO_APPLY_ENABLED", "1") == "1"
    if scope in {"full", "description"}:
        description_html = _render_description(generated.get("description_text"))
        description_confidence = float(generated.get("description_confidence") or 0)
        if description_html:
            proposal["description_html"] = description_html
            confidence["description_html"] = description_confidence
            field_sources["description_html"] = sorted(source_urls)
            if auto_enabled and description_confidence >= minimum and (
                official or len(independent_domains) >= min_domains
            ):
                auto_fields.append("description_html")
    if scope in {"full", "technical"}:
        for field, candidate in (generated.get("technical") or {}).items():
            if field not in TECHNICAL_FIELDS or not isinstance(candidate, dict):
                continue
            value = candidate.get("value")
            source_url = candidate.get("source_url")
            field_confidence = float(candidate.get("confidence") or 0)
            if value is None or source_url not in source_urls:
                continue
            proposal[field] = value
            confidence[field] = field_confidence
            field_sources[field] = [source_url]
            if auto_enabled and field_confidence >= technical_minimum:
                auto_fields.append(field)
    return {
        "proposal": proposal,
        "confidence": confidence,
        "field_sources": field_sources,
    }, auto_fields


async def _apply_automatic_fields(
    product: CanonicalProduct,
    job: CanonicalEnrichmentJob,
    result: dict,
    fields: list[str],
    db,
) -> None:
    for field in fields:
        setattr(product, field, result["proposal"][field])
    if fields:
        product.content_revision += 1
        product.last_enriched_at = datetime.utcnow()
        product.enriched_by = job.requested_by_user_id
        job.applied_fields = sorted(fields)
        db.add(
            CanonicalContentVersion(
                canonical_product_id=product.id,
                origin="enrichment_auto",
                job_id=job.id,
                revision=product.content_revision,
                snapshot_json=canonical_snapshot(product),
                is_applied=True,
                created_by_user_id=job.requested_by_user_id,
            )
        )
    remaining = set(result["proposal"]) - set(fields)
    job.status = (
        "applied"
        if fields and not remaining
        else "partially_applied"
        if fields
        else "review_required"
    )
    job.completed_at = datetime.utcnow()


async def _persist_sources(
    job: CanonicalEnrichmentJob,
    sources: list[dict],
    db,
) -> None:
    """Persiste evidencia de forma idempotente entre retries del mismo job."""
    existing_urls = set(
        (
            await db.scalars(
                select(CanonicalEnrichmentSource.url).where(
                    CanonicalEnrichmentSource.job_id == job.id
                )
            )
        ).all()
    )
    remaining = max(0, _integer("ENRICH_MAX_FETCH_SOURCES", 5) - len(existing_urls))
    for source in sources:
        if remaining <= 0:
            break
        url = source["url"]
        if url in existing_urls:
            continue
        existing_urls.add(url)
        remaining -= 1
        db.add(
            CanonicalEnrichmentSource(
                job_id=job.id,
                knowledge_asset_id=source.get("knowledge_asset_id"),
                knowledge_version_id=source.get("knowledge_version_id"),
                url=url,
                title=source.get("title"),
                source_type=source.get("source_type"),
                mime_type=source.get("mime_type"),
                content_hash=source.get("content_hash"),
                evidence_json={
                    "snippet": (source.get("snippet") or "")[:800],
                    "excerpt": (source.get("text") or "")[:1_500],
                },
                accessed_at=datetime.utcnow(),
            )
        )
    await db.flush()


def _safe_error_message(exc: Exception) -> str:
    if isinstance(exc, IntegrityError):
        return "Error de integridad al persistir el job"
    return str(exc)[:500]


async def process_canonical_enrichment_async(job_id: str) -> None:
    async with SessionLocal() as db:
        job = await db.get(CanonicalEnrichmentJob, job_id)
        if not job or job.status not in {"queued", "running"}:
            return
        job.status = "running"
        job.stage = "research"
        job.attempts += 1
        job.started_at = job.started_at or datetime.utcnow()
        await db.commit()
        _event("job_started", job_id=job.id, canonical_product_id=job.canonical_product_id)
        try:
            product = await db.get(CanonicalProduct, job.canonical_product_id)
            if not product:
                raise RuntimeError("Producto canónico inexistente")
            sources = await _research(product, db)
            job.stage = "fetch"
            await _persist_sources(job, sources, db)
            job.stage = "compose"
            await db.commit()
            generated, provider, model = await _generate_with_provider(
                _compose_prompt(product, sources, job.scope)
            )
            job.provider = provider
            job.model = model
            job.stage = "validate"
            result, auto_fields = _build_result(product, generated, sources, job.scope)
            if not result["proposal"]:
                raise RuntimeError("La propuesta no contiene campos respaldados")
            job.result_json = result
            job.stage = "apply"
            await _apply_automatic_fields(product, job, result, auto_fields, db)
            await db.commit()
            _event("job_completed", job_id=job.id, status=job.status, applied_fields=job.applied_fields or [])
        except Exception as exc:
            await db.rollback()
            job = await db.get(CanonicalEnrichmentJob, job_id)
            if not job:
                raise
            max_retries = _integer("ENRICH_JOB_MAX_RETRIES", 2)
            job.error_code = type(exc).__name__
            job.error_message = _safe_error_message(exc)
            job.stage = None
            if job.attempts <= max_retries:
                job.status = "queued"
            else:
                job.status = "failed"
                job.completed_at = datetime.utcnow()
            await db.commit()
            _event("job_failed", job_id=job.id, status=job.status, error_code=job.error_code)
            raise


@dramatiq.actor(
    queue_name="enrichment",
    max_retries=_integer("ENRICH_JOB_MAX_RETRIES", 2),
    time_limit=_integer("ENRICH_JOB_TIME_LIMIT_MS", 300000),
)
def process_canonical_enrichment(job_id: str) -> None:
    asyncio.run(process_canonical_enrichment_async(job_id))
