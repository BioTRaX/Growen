#!/usr/bin/env python
# NG-HEADER: Nombre de archivo: knowledge_jobs.py
# NG-HEADER: Ubicación: services/jobs/knowledge_jobs.py
# NG-HEADER: Descripción: Worker multiformato de la Base de Conocimiento Canónica.
# NG-HEADER: Lineamientos: Ver AGENTS.md
"""Ingestión, versionado, extracción de claims y resolución de hechos."""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import os
import subprocess
import tempfile
import threading
import time
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import selectinload

try:
    import services.jobs  # noqa: F401
    import dramatiq  # type: ignore
except Exception:  # pragma: no cover
    class _Stub:
        @staticmethod
        def actor(*_args, **_kwargs):
            return lambda function: function
    dramatiq = _Stub()  # type: ignore

from agent_core.mcp_client import mcp_client_manager
from ai.providers.openai_provider import OpenAIProvider
from agent_core.secrets import read_secret
from db.models import (
    CanonicalKnowledgeAsset,
    CanonicalKnowledgeClaim,
    CanonicalKnowledgeEvent,
    CanonicalKnowledgeFact,
    CanonicalKnowledgeJob,
    CanonicalKnowledgeVersion,
)
from db.session import SessionLocal
from services.knowledge.service import apply_ai_adjustment, deterministic_trust
from services.media import get_media_root


logger = logging.getLogger(__name__)
CAPABILITY_KEYS = {
    "description",
    "technical_specs",
    "compatibility",
    "images",
    "manuals",
    "price",
    "availability",
    "offers",
    "seo",
    "video",
    "warranty",
    "certifications",
}


def _integer(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, str(default)))
    except ValueError:
        return default


def _heartbeat() -> None:
    try:
        import redis
        client = redis.from_url(os.getenv("REDIS_URL", "redis://127.0.0.1:6379/0"))
    except Exception:
        return
    ttl = max(_integer("KNOWLEDGE_HEARTBEAT_TTL_SECONDS", 60), 15)
    while True:
        try:
            client.setex(
                "growen:knowledge_worker:heartbeat",
                ttl,
                json.dumps({
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "queue": "canonical_knowledge",
                    "version": "1",
                }),
            )
        except Exception:
            logger.warning("No se pudo publicar heartbeat de conocimiento", exc_info=True)
        time.sleep(max(5, ttl // 3))


if os.getenv("KNOWLEDGE_HEARTBEAT_ENABLED", "1") == "1":
    threading.Thread(target=_heartbeat, name="knowledge-heartbeat", daemon=True).start()


def _event(name: str, **values) -> None:
    print(json.dumps({
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "service": "knowledge_worker",
        "event": name,
        **values,
    }, ensure_ascii=False, default=str), flush=True)


def _local_extract(path: Path, mime: str | None) -> tuple[str, dict, str]:
    data = path.read_bytes()
    digest = hashlib.sha256(data).hexdigest()
    metadata: dict = {"bytes": len(data)}
    text = ""
    if mime == "application/pdf" or path.suffix.lower() == ".pdf":
        from pypdf import PdfReader
        reader = PdfReader(path)
        max_pages = _integer("KNOWLEDGE_MAX_PDF_PAGES", 200)
        text = "\n".join((page.extract_text() or "") for page in reader.pages[:max_pages])
        metadata.update({"pages": min(len(reader.pages), max_pages), "kind": "pdf"})
    elif (mime or "").startswith("image/"):
        from PIL import Image
        with Image.open(path) as image:
            metadata.update({"width": image.width, "height": image.height, "format": image.format, "kind": "image"})
            try:
                import pytesseract
                text = pytesseract.image_to_string(image, lang=os.getenv("KNOWLEDGE_OCR_LANG", "spa+eng"))
                metadata["ocr"] = True
            except Exception:
                metadata["ocr"] = False
    elif (mime or "").startswith("video/"):
        metadata["kind"] = "video"
        duration = 0.0
        try:
            completed = subprocess.run(
                ["ffprobe", "-v", "error", "-show_entries", "format=duration:stream=codec_name,width,height", "-of", "json", str(path)],
                capture_output=True,
                text=True,
                timeout=_integer("KNOWLEDGE_VIDEO_PROBE_TIMEOUT_SECONDS", 20),
                check=True,
            )
            probe = json.loads(completed.stdout or "{}")
            metadata.update(probe)
            duration = float((probe.get("format") or {}).get("duration") or 0)
        except Exception as exc:
            metadata["probe_error"] = type(exc).__name__
        max_duration = _integer("KNOWLEDGE_MAX_VIDEO_DURATION_SECONDS", 1800)
        if duration > max_duration:
            raise ValueError(f"El video supera el límite de {max_duration} segundos")
        frames_dir = path.parent / f"{path.stem}-frames"
        frames_dir.mkdir(exist_ok=True)
        try:
            subprocess.run(
                ["ffmpeg", "-y", "-i", str(path), "-vf", "fps=1/30", "-frames:v", str(_integer("KNOWLEDGE_MAX_VIDEO_FRAMES", 8)), str(frames_dir / "frame-%03d.jpg")],
                capture_output=True,
                timeout=_integer("KNOWLEDGE_VIDEO_PROCESS_TIMEOUT_SECONDS", 120),
                check=True,
            )
            metadata["frames"] = [str(item.relative_to(get_media_root())).replace("\\", "/") for item in sorted(frames_dir.glob("*.jpg"))]
        except Exception as exc:
            metadata["frames_error"] = type(exc).__name__
        metadata["transcription_status"] = "pending"
    else:
        text = data.decode("utf-8", errors="replace")
    return text[:_integer("KNOWLEDGE_MAX_TEXT_CHARS", 100_000)], metadata, digest


async def _transcribe_video(path: Path, metadata: dict) -> str:
    api_key = read_secret("OPENAI_API_KEY") or ""
    if not api_key:
        metadata["transcription_status"] = "provider_unavailable"
        return ""
    try:
        from openai import AsyncOpenAI
        with tempfile.TemporaryDirectory(prefix="growen-knowledge-audio-") as temp_dir:
            audio_path = Path(temp_dir) / "audio.mp3"
            await asyncio.to_thread(
                subprocess.run,
                [
                    "ffmpeg",
                    "-y",
                    "-i",
                    str(path),
                    "-vn",
                    "-ac",
                    "1",
                    "-ar",
                    "16000",
                    "-b:a",
                    "48k",
                    str(audio_path),
                ],
                capture_output=True,
                timeout=_integer("KNOWLEDGE_VIDEO_PROCESS_TIMEOUT_SECONDS", 120),
                check=True,
            )
            if audio_path.stat().st_size > _integer("KNOWLEDGE_MAX_TRANSCRIPTION_AUDIO_BYTES", 24_000_000):
                raise ValueError("El audio extraído supera el límite de transcripción")
            client = AsyncOpenAI(
                api_key=api_key,
                timeout=float(os.getenv("KNOWLEDGE_TRANSCRIPTION_TIMEOUT_SECONDS", "120")),
            )
            with audio_path.open("rb") as audio:
                response = await client.audio.transcriptions.create(
                    model=os.getenv("KNOWLEDGE_TRANSCRIPTION_MODEL", "whisper-1"),
                    file=audio,
                )
        metadata["transcription_status"] = "completed"
        return str(getattr(response, "text", "") or "")
    except Exception as exc:
        metadata["transcription_status"] = "failed"
        metadata["transcription_error"] = type(exc).__name__
        return ""


async def _remote_extract(url: str) -> tuple[str, dict, str, str | None]:
    response = await mcp_client_manager.call_tool(
        "fetch_web_document",
        {"url": url},
        role="admin",
        server_name="web_search",
    )
    if response.get("error"):
        raise RuntimeError(f"MCP Web Search no pudo leer el recurso: {response['error']}")
    text = str(response.get("text") or "")
    if not text:
        raise RuntimeError("El recurso remoto no produjo texto reutilizable")
    digest = response.get("content_hash") or hashlib.sha256(text.encode("utf-8")).hexdigest()
    return text[:_integer("KNOWLEDGE_MAX_TEXT_CHARS", 100_000)], {
        "source": "mcp_web_search",
        "final_url": response.get("url") or url,
        "title": response.get("title"),
    }, digest, response.get("mime_type")


async def _ai_extract(asset: CanonicalKnowledgeAsset, text: str) -> tuple[list[dict], float | None, dict | None]:
    provider = OpenAIProvider()
    if not provider.api_key or not text.strip():
        return [], None, None
    provider.model = os.getenv("KNOWLEDGE_OPENAI_MODEL", os.getenv("ENRICH_OPENAI_MODEL", "gpt-4.1-mini"))
    capabilities = sorted(item.capability_code for item in asset.capabilities if item.enabled)
    prompt = (
        "Sos un extractor de conocimiento de catálogo. Devolvé JSON válido sin HTML. "
        "No inventes datos. Cada claim debe estar explícitamente respaldado por el texto.\n\n"
        f"Capacidades permitidas: {json.dumps(capabilities)}\n"
        f"Texto: {text[:40_000]}\n"
        'Esquema de salida EXACTO: {"claims":[{"fact_key":string,"capability":string,'
        '"value":object,"unit":string|null,"confidence":number,"evidence":string}],'
        '"trust_adjustment":number,"trust_reason":{"summary":string}}'
    )
    try:
        raw = await provider.generate_async(prompt, user_context={"role": "admin", "channel": "web"})
    except Exception as exc:
        logger.warning("Extracción IA no disponible error=%s", type(exc).__name__)
        return [], None, None
    if not raw or raw == prompt or raw.startswith("openai:"):
        return [], None, None
    value = raw.strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip()
    try:
        parsed = json.loads(value)
    except (json.JSONDecodeError, TypeError):
        logger.warning("Extracción IA descartada por esquema JSON inválido")
        return [], None, None
    if not isinstance(parsed, dict):
        logger.warning("Extracción IA descartada por raíz no estructurada")
        return [], None, None
    claims = [
        item for item in parsed.get("claims", [])
        if isinstance(item, dict)
        and item.get("capability") in CAPABILITY_KEYS
        and item.get("fact_key")
        and isinstance(item.get("value"), dict)
    ]
    return claims, parsed.get("trust_adjustment"), parsed.get("trust_reason")


async def _resolve_facts(session, product_id: int) -> None:
    claims = list(await session.scalars(
        select(CanonicalKnowledgeClaim).where(
            CanonicalKnowledgeClaim.canonical_product_id == product_id,
            CanonicalKnowledgeClaim.status.in_(("proposed", "confirmed", "contradicted")),
        )
    ))
    grouped: dict[str, list[CanonicalKnowledgeClaim]] = {}
    for claim in claims:
        grouped.setdefault(claim.fact_key, []).append(claim)
    for fact_key, items in grouped.items():
        values: dict[str, list[CanonicalKnowledgeClaim]] = {}
        for claim in items:
            values.setdefault(json.dumps(claim.value_json, sort_keys=True, ensure_ascii=False), []).append(claim)
        if len(values) != 1:
            for claim in items:
                claim.status = "contradicted"
            continue
        supporters = next(iter(values.values()))
        confidence = min(0.999, 1 - __import__("math").prod(1 - max(0, min(1, item.confidence)) for item in supporters))
        for claim in supporters:
            claim.status = "confirmed"
        fact = await session.scalar(select(CanonicalKnowledgeFact).where(
            CanonicalKnowledgeFact.canonical_product_id == product_id,
            CanonicalKnowledgeFact.fact_key == fact_key,
        ))
        if fact and fact.value_json != supporters[0].value_json:
            continue
        if not fact:
            fact = CanonicalKnowledgeFact(
                canonical_product_id=product_id,
                fact_key=fact_key,
                capability_code=supporters[0].capability_code,
                value_json=supporters[0].value_json,
                confidence=confidence,
                supporting_claim_ids=[],
            )
            session.add(fact)
        fact.confidence = confidence
        fact.supporting_claim_ids = [item.id for item in supporters if item.id]
        fact.revision += 1


async def process_knowledge_async(job_id: str) -> None:
    async with SessionLocal() as session:
        job = await session.get(CanonicalKnowledgeJob, job_id)
        if not job or job.status not in {"queued", "running"}:
            return
        job.status = "running"
        job.stage = "fetch"
        job.started_at = job.started_at or datetime.utcnow()
        await session.commit()
        try:
            asset = await session.scalar(
                select(CanonicalKnowledgeAsset)
                .options(
                    selectinload(CanonicalKnowledgeAsset.locations),
                    selectinload(CanonicalKnowledgeAsset.labels),
                    selectinload(CanonicalKnowledgeAsset.capabilities),
                    selectinload(CanonicalKnowledgeAsset.market_profile),
                )
                .where(CanonicalKnowledgeAsset.id == job.asset_id)
            )
            if not asset or asset.status == "archived":
                raise RuntimeError("El activo no existe o está archivado")
            processed = 0
            created_claims = 0
            for location in asset.locations:
                if location.status == "archived":
                    continue
                if location.storage_path:
                    path = (get_media_root() / location.storage_path).resolve()
                    root = get_media_root().resolve()
                    if root not in path.parents or not path.exists():
                        raise RuntimeError("Archivo de conocimiento inexistente o fuera de MEDIA_ROOT")
                    text, metadata, digest = await asyncio.to_thread(_local_extract, path, location.mime_type)
                    mime = location.mime_type
                    if (mime or "").startswith("video/"):
                        text = await _transcribe_video(path, metadata)
                elif location.url:
                    text, metadata, digest, mime = await _remote_extract(location.url)
                else:
                    continue
                existing = await session.scalar(select(CanonicalKnowledgeVersion).where(
                    CanonicalKnowledgeVersion.location_id == location.id,
                    CanonicalKnowledgeVersion.content_hash == digest,
                ))
                if existing:
                    location.status = "ready"
                    location.last_fetched_at = datetime.utcnow()
                    continue
                location.content_version += 1
                location.content_hash = digest
                location.mime_type = mime or location.mime_type
                location.metadata_json = metadata
                location.status = "ready"
                location.last_fetched_at = datetime.utcnow()
                version = CanonicalKnowledgeVersion(
                    asset_id=asset.id,
                    location_id=location.id,
                    version=location.content_version,
                    content_hash=digest,
                    extracted_text=text,
                    metadata_json=metadata,
                )
                session.add(version)
                await session.flush()
                job.stage = "extract"
                claims, adjustment, reason = await _ai_extract(asset, text)
                apply_ai_adjustment(asset, adjustment, reason)
                for item in claims:
                    session.add(CanonicalKnowledgeClaim(
                        canonical_product_id=asset.canonical_product_id,
                        asset_id=asset.id,
                        version_id=version.id,
                        capability_code=item["capability"],
                        fact_key=str(item["fact_key"])[:160],
                        value_json=item["value"],
                        unit=item.get("unit"),
                        confidence=max(0, min(1, float(item.get("confidence") or 0))),
                        evidence_json={"excerpt": str(item.get("evidence") or "")[:800], "location_id": location.id},
                    ))
                    created_claims += 1
                processed += 1
            await session.flush()
            job.stage = "resolve"
            await _resolve_facts(session, asset.canonical_product_id)
            labels = {item.label for item in asset.labels}
            score, breakdown = deterministic_trust(labels, fresh=processed > 0, extraction_success=1 if processed else 0)
            breakdown["deterministic"] = score
            asset.trust_breakdown = breakdown
            apply_ai_adjustment(asset, asset.ai_trust_adjustment, asset.ai_trust_reason)
            session.add(CanonicalKnowledgeEvent(
                canonical_product_id=asset.canonical_product_id,
                asset_id=asset.id,
                event_type="asset_processed",
                actor_user_id=job.requested_by_user_id,
                payload_json={"locations": processed, "claims": created_claims},
            ))
            job.status = "completed"
            job.stage = None
            job.result_json = {"locations_processed": processed, "claims_created": created_claims}
            job.completed_at = datetime.utcnow()
            await session.commit()
            _event("job_completed", job_id=job.id, asset_id=asset.id, locations=processed, claims=created_claims)
        except Exception as exc:
            await session.rollback()
            job = await session.get(CanonicalKnowledgeJob, job_id)
            if job:
                job.status = "failed"
                job.stage = None
                job.error_code = type(exc).__name__
                job.error_message = str(exc)[:500]
                job.completed_at = datetime.utcnow()
                await session.commit()
            _event("job_failed", job_id=job_id, error_code=type(exc).__name__)
            raise


@dramatiq.actor(
    queue_name="canonical_knowledge",
    max_retries=_integer("KNOWLEDGE_JOB_MAX_RETRIES", 2),
    time_limit=_integer("KNOWLEDGE_JOB_TIME_LIMIT_MS", 600000),
)
def process_knowledge(job_id: str) -> None:
    asyncio.run(process_knowledge_async(job_id))
