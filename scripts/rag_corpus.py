#!/usr/bin/env python
# NG-HEADER: Nombre de archivo: rag_corpus.py
# NG-HEADER: Ubicación: scripts/rag_corpus.py
# NG-HEADER: Descripción: Carga y evalúa el corpus RAG controlado por rol y canal.
# NG-HEADER: Lineamientos: Ver AGENTS.md
from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from sqlalchemy import delete, select

from ai.embeddings import get_embedding_service
from db.models import KnowledgeChunk, KnowledgeSource
from db.models import ChatRolloutCheck
from db.session import SessionLocal
from services.rag.search import RAGSearchService
from services.rag.ingest import DocumentIngestor

MANIFEST = ROOT / "docs" / "rag" / "corpus-manifest.v1.json"


def utcnow_naive() -> datetime:
    """UTC compatible con columnas PostgreSQL `timestamp without time zone`."""

    return datetime.now(UTC).replace(tzinfo=None)


def load_manifest() -> dict[str, Any]:
    return json.loads(MANIFEST.read_text(encoding="utf-8"))


def source_content(item: dict[str, Any]) -> str:
    if item["kind"] == "curated":
        path = (ROOT / item["path"]).resolve()
        if ROOT not in path.parents or not path.is_file():
            raise ValueError("curated_source_path_invalid")
        return path.read_text(encoding="utf-8")
    return str(item["content"])


async def load_sources(kinds: set[str], dry_run: bool) -> dict[str, int]:
    manifest = load_manifest()
    selected = [item for item in manifest["sources"] if item["kind"] in kinds]
    if dry_run:
        return {"selected": len(selected), "created": 0, "updated": 0, "unchanged": 0}
    embedding_service = get_embedding_service()
    splitter = DocumentIngestor(embedding_service=embedding_service).text_splitter
    counters = {"selected": len(selected), "created": 0, "updated": 0, "unchanged": 0}
    async with SessionLocal() as session:
        for item in selected:
            content = source_content(item)
            digest = hashlib.sha256(content.encode("utf-8")).hexdigest()
            source = await session.scalar(select(KnowledgeSource).where(KnowledgeSource.filename == item["filename"]).order_by(KnowledgeSource.id).limit(1))
            previous_meta = source.meta_json if source is not None else {}
            changed = (
                source is None
                or source.hash != digest
                or source.content_version != int(item["version"])
                or (previous_meta or {}).get("chunking_version") != 1
            )
            if source is None:
                source = KnowledgeSource(filename=item["filename"], hash=digest)
                session.add(source)
                counters["created"] += 1
            elif changed:
                await session.execute(delete(KnowledgeChunk).where(KnowledgeChunk.source_id == source.id))
                counters["updated"] += 1
            else:
                counters["unchanged"] += 1
            source.hash = digest
            source.meta_json = {
                "corpus_id": item["id"],
                "kind": item["kind"],
                "manifest_version": manifest["manifest_version"],
                "chunking_version": 1,
            }
            source.role_scope = item["roles"]
            source.channel_scope = item["channels"]
            source.visibility = item["visibility"]
            source.status = item["status"]
            source.content_version = int(item["version"])
            now = utcnow_naive()
            source.indexed_at = now
            source.expires_at = now - timedelta(days=1) if item.get("expired") else None
            await session.flush()
            if changed:
                chunks = splitter.split_text(content) if item["kind"] == "curated" else [content]
                embeddings = await embedding_service.generate_embeddings_batch(chunks)
                for chunk_index, (chunk, embedding) in enumerate(zip(chunks, embeddings)):
                    session.add(KnowledgeChunk(
                        source_id=source.id,
                        chunk_index=chunk_index,
                        content=chunk,
                        embedding=embedding,
                        chunk_metadata={"corpus_id": item["id"]},
                    ))
        await session.commit()
    return counters


async def cleanup_synthetic(dry_run: bool) -> dict[str, int]:
    async with SessionLocal() as session:
        sources = (await session.scalars(select(KnowledgeSource))).all()
        targets = [source for source in sources if (source.meta_json or {}).get("kind") == "synthetic"]
        if not dry_run:
            for source in targets:
                await session.delete(source)
            await session.commit()
        return {"selected": len(targets), "deleted": 0 if dry_run else len(targets)}


async def evaluate() -> dict[str, Any]:
    manifest = load_manifest()
    service = RAGSearchService()
    synthetic_ranks: list[int] = []
    curated_ranks: list[int] = []
    leaks = 0
    citations_complete = 0
    returned = 0
    context_budget_hits = 0
    context_budget_cases = 0
    cases: list[dict[str, Any]] = []
    async with SessionLocal() as session:
        corpus_ids = {
            source.id: (source.meta_json or {}).get("corpus_id")
            for source in (await session.scalars(select(KnowledgeSource))).all()
        }
        source_ids = {corpus_id: source_id for source_id, corpus_id in corpus_ids.items() if corpus_id}
        for case in manifest["evaluations"]:
            min_similarity = float(case.get("min_similarity", 0.0))
            results = await service.search(case["query"], session, top_k=5, min_similarity=min_similarity, role=case["role"], channel=case["channel"])
            ids = [corpus_ids.get(item["source_id"]) for item in results]
            expected = case["expected"]
            rank = ids.index(expected) + 1 if expected in ids else 0
            if expected:
                (curated_ranks if expected.startswith("curated-") else synthetic_ranks).append(rank)
                context_budget_cases += 1
                formatted_context = await service.search_and_format_context(
                    case["query"],
                    session,
                    top_k=5,
                    min_similarity=min_similarity,
                    role=case["role"],
                    channel=case["channel"],
                )
                expected_source_id = source_ids.get(expected)
                if expected_source_id and f"fuente:{expected_source_id} " in formatted_context:
                    context_budget_hits += 1
            forbidden = set(case.get("forbidden") or [])
            if forbidden.intersection(ids):
                leaks += 1
            for item in results:
                returned += 1
                citation = item.get("citation") or {}
                if all(key in citation for key in ("source_id", "title", "chunk_index", "page", "score", "content_version")):
                    citations_complete += 1
            cases.append({"role": case["role"], "channel": case["channel"], "intent": case["intent"], "expected_found": bool(rank) if expected else not bool(forbidden.intersection(ids)), "result_count": len(ids)})

    recall = sum(1 for rank in synthetic_ranks if 0 < rank <= 5) / max(1, len(synthetic_ranks))
    curated_recall = sum(1 for rank in curated_ranks if 0 < rank <= 5) / max(1, len(curated_ranks))
    mrr = sum(1 / rank for rank in synthetic_ranks if rank) / max(1, len(synthetic_ranks))
    citation_rate = citations_complete / max(1, returned)
    context_budget_rate = context_budget_hits / max(1, context_budget_cases)
    scoped_cache_keys = {
        RAGSearchService._cache_key("q", "guest", "web", 1),
        RAGSearchService._cache_key("q", "cliente", "web", 1),
        RAGSearchService._cache_key("q", "cliente", "telegram", 1),
    }
    cache_role_channel = len(scoped_cache_keys) == 3
    cache_version = RAGSearchService._cache_key("q", "guest", "web", 1) != RAGSearchService._cache_key("q", "guest", "web", 2)
    passed = leaks == 0 and recall >= 0.95 and curated_recall >= 0.80 and mrr >= 0.90 and citation_rate == 1.0 and context_budget_rate == 1.0 and cache_role_channel and cache_version
    return {"passed": passed, "synthetic_recall_at_5": recall, "curated_recall_at_5": curated_recall, "synthetic_mrr": mrr, "scope_leaks": leaks, "citation_rate": citation_rate, "context_budget_rate": context_budget_rate, "cache_role_channel_separated": cache_role_channel, "cache_version_invalidated": cache_version, "cases": cases}


async def main() -> int:
    parser = argparse.ArgumentParser(description="Gestiona el corpus RAG controlado")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--synthetic", action="store_true")
    parser.add_argument("--curated", action="store_true")
    parser.add_argument("--cleanup-synthetic", action="store_true")
    parser.add_argument("--evaluate", action="store_true")
    parser.add_argument("--record-rollout-check", action="store_true")
    args = parser.parse_args()
    output: dict[str, Any] = {"manifest_version": load_manifest()["manifest_version"]}
    if args.cleanup_synthetic:
        output["cleanup"] = await cleanup_synthetic(args.dry_run)
    kinds = {kind for kind, enabled in (("synthetic", args.synthetic), ("curated", args.curated)) if enabled}
    if kinds:
        output["load"] = await load_sources(kinds, args.dry_run)
    if args.evaluate:
        output["evaluation"] = await evaluate()
        if args.record_rollout_check:
            from services.chat.rollout import get_rollout_state

            async with SessionLocal() as session:
                state = await get_rollout_state(session)
                session.add(ChatRolloutCheck(check_name="rag_eval", phase=state.phase, status="passed" if output["evaluation"]["passed"] else "failed", code=None if output["evaluation"]["passed"] else "rag_scope_leak"))
                await session.commit()
    print(json.dumps(output, ensure_ascii=False, sort_keys=True))
    return 1 if output.get("evaluation", {}).get("passed") is False else 0


if __name__ == "__main__":
    loop_factory = asyncio.SelectorEventLoop if sys.platform == "win32" else None
    raise SystemExit(asyncio.run(main(), loop_factory=loop_factory))
