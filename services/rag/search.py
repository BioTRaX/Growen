#!/usr/bin/env python
# NG-HEADER: Nombre de archivo: search.py
# NG-HEADER: Ubicación: services/rag/search.py
# NG-HEADER: Descripción: Recuperación RAG híbrida, autorizada, cacheada y con citas.
# NG-HEADER: Lineamientos: Ver AGENTS.md
"""Búsqueda híbrida que filtra scopes antes de rankear y retorna citas."""

from __future__ import annotations

import hashlib
import logging
import math
import time
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import Float, and_, cast, func, or_, select
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.asyncio import AsyncSession

from agent_core.config import settings
from agent_core.chat_policy import current_chat_citations, current_chat_rag_cache_hit
from ai.embeddings import get_embedding_service
from db.models import KnowledgeChunk, KnowledgeSource

logger = logging.getLogger(__name__)


class RAGSearchService:
    """Recuperador con deny-by-default por rol, canal, estado y vigencia."""

    def __init__(self) -> None:
        self.embedding_service = get_embedding_service()
        self._cache: dict[str, tuple[float, list[dict[str, Any]]]] = {}

    @staticmethod
    def _source_allowed(source: KnowledgeSource, role: str, channel: str) -> bool:
        now = datetime.now(UTC).replace(tzinfo=None)
        if source.status != "active":
            return False
        if source.expires_at and source.expires_at <= now:
            return False
        return role in (source.role_scope or []) and channel in (source.channel_scope or [])

    async def _corpus_version(self, session: AsyncSession) -> str:
        """Devuelve una huella que cambia ante cualquier cambio de política o versión."""

        rows = (
            await session.execute(
                select(
                    KnowledgeSource.id,
                    KnowledgeSource.content_version,
                    KnowledgeSource.role_scope,
                    KnowledgeSource.channel_scope,
                    KnowledgeSource.status,
                    KnowledgeSource.expires_at,
                ).order_by(KnowledgeSource.id)
            )
        ).all()
        if not rows:
            return ""
        payload = "\n".join(
            repr((source_id, version, roles, channels, status, expires_at))
            for source_id, version, roles, channels, status, expires_at in rows
        )
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()

    @staticmethod
    def _cache_key(query: str, role: str, channel: str, version: int | str) -> str:
        payload = f"{role}\0{channel}\0{version}\0{query.strip().lower()}".encode("utf-8")
        return hashlib.sha256(payload).hexdigest()

    @staticmethod
    def _cosine(left: list[float], right: list[float]) -> float:
        if not left or not right or len(left) != len(right):
            return 0.0
        numerator = sum(a * b for a, b in zip(left, right))
        denominator = math.sqrt(sum(a * a for a in left)) * math.sqrt(sum(b * b for b in right))
        return numerator / denominator if denominator else 0.0

    @staticmethod
    def _result(chunk: KnowledgeChunk, source: KnowledgeSource, score: float) -> dict[str, Any]:
        page = (chunk.chunk_metadata or {}).get("page")
        citation = {
            "source_id": source.id,
            "title": source.filename,
            "chunk_index": chunk.chunk_index,
            "page": page,
            "score": round(float(score), 6),
            "content_version": source.content_version,
        }
        return {
            "content": chunk.content,
            "source": source.filename,
            "similarity": round(float(score), 6),
            "chunk_index": chunk.chunk_index,
            "source_id": source.id,
            "citation": citation,
        }

    async def _search_sqlite(
        self,
        query: str,
        query_embedding: list[float] | None,
        session: AsyncSession,
        role: str,
        channel: str,
        limit: int,
    ) -> list[dict[str, Any]]:
        rows = (
            await session.execute(
                select(KnowledgeChunk, KnowledgeSource).join(
                    KnowledgeSource, KnowledgeChunk.source_id == KnowledgeSource.id
                )
            )
        ).all()
        terms = {term for term in query.lower().split() if len(term) > 2}
        ranked: list[tuple[float, KnowledgeChunk, KnowledgeSource]] = []
        for chunk, source in rows:
            if not self._source_allowed(source, role, channel):
                continue
            lexical = sum(1 for term in terms if term in chunk.content.lower()) / max(1, len(terms))
            vector = self._cosine(query_embedding or [], list(chunk.embedding or []))
            score = max(vector, (vector + lexical) / 2 if query_embedding else lexical)
            ranked.append((score, chunk, source))
        ranked.sort(key=lambda item: item[0], reverse=True)
        return [self._result(chunk, source, score) for score, chunk, source in ranked[:limit]]

    async def _search_postgresql(
        self,
        query: str,
        query_embedding: list[float] | None,
        session: AsyncSession,
        role: str,
        channel: str,
        limit: int,
    ) -> list[dict[str, Any]]:
        filters = [
            KnowledgeSource.status == "active",
            cast(KnowledgeSource.role_scope, JSONB).contains([role]),
            cast(KnowledgeSource.channel_scope, JSONB).contains([channel]),
            or_(KnowledgeSource.expires_at.is_(None), KnowledgeSource.expires_at > func.now()),
        ]
        candidates: dict[int, tuple[KnowledgeChunk, KnowledgeSource, float]] = {}
        rank_lists: list[list[int]] = []

        if query_embedding and settings.rag_search_mode in {"hybrid", "vector"}:
            distance = KnowledgeChunk.embedding.cosine_distance(query_embedding)
            rows = (
                await session.execute(
                    select(KnowledgeChunk, KnowledgeSource, (1 - cast(distance, Float)).label("score"))
                    .join(KnowledgeSource, KnowledgeChunk.source_id == KnowledgeSource.id)
                    .where(and_(*filters), KnowledgeChunk.embedding.isnot(None))
                    .order_by(distance)
                    .limit(limit)
                )
            ).all()
            rank_lists.append([chunk.id for chunk, _, _ in rows])
            for chunk, source, score in rows:
                candidates[chunk.id] = (chunk, source, float(score))

        if settings.rag_search_mode in {"hybrid", "text"}:
            vector = func.to_tsvector("spanish", KnowledgeChunk.content)
            tsquery = func.plainto_tsquery("spanish", query)
            rank = func.ts_rank_cd(vector, tsquery)
            rows = (
                await session.execute(
                    select(KnowledgeChunk, KnowledgeSource, rank.label("score"))
                    .join(KnowledgeSource, KnowledgeChunk.source_id == KnowledgeSource.id)
                    .where(and_(*filters), vector.op("@@")(tsquery))
                    .order_by(rank.desc())
                    .limit(limit)
                )
            ).all()
            rank_lists.append([chunk.id for chunk, _, _ in rows])
            for chunk, source, score in rows:
                previous = candidates.get(chunk.id)
                candidates[chunk.id] = (chunk, source, max(float(score), previous[2] if previous else 0.0))

        fused: dict[int, float] = {chunk_id: 0.0 for chunk_id in candidates}
        for ranking in rank_lists:
            for position, chunk_id in enumerate(ranking, 1):
                fused[chunk_id] += 1.0 / (60 + position)
        ordered = sorted(candidates, key=lambda chunk_id: fused[chunk_id], reverse=True)
        return [
            self._result(candidates[item][0], candidates[item][1], candidates[item][2])
            for item in ordered[:limit]
        ]

    async def search(
        self,
        query: str,
        session: AsyncSession,
        top_k: int = 5,
        min_similarity: float = 0.5,
        role: str = "guest",
        channel: str = "web",
    ) -> list[dict[str, Any]]:
        if not query or not query.strip():
            return []
        version = await self._corpus_version(session)
        if not version:
            await self._mark_chat_run(session, [], cache_hit=False)
            return []
        cache_key = self._cache_key(query, role, channel, version)
        cached = self._cache.get(cache_key)
        if cached and time.monotonic() - cached[0] < settings.rag_cache_ttl_seconds:
            cached_results = [dict(item, cache_hit=True) for item in cached[1]]
            await self._mark_chat_run(session, cached_results, cache_hit=True)
            return cached_results

        query_embedding: list[float] | None = None
        if settings.rag_search_mode in {"hybrid", "vector"}:
            try:
                query_embedding = await self.embedding_service.generate_embedding(query)
            except Exception as exc:
                logger.warning("Embedding RAG no disponible error=%s", type(exc).__name__)
                if settings.rag_search_mode == "vector":
                    return []
        dialect = session.bind.dialect.name if session.bind is not None else "postgresql"
        limit = max(top_k * 4, top_k)
        try:
            if dialect == "postgresql":
                results = await self._search_postgresql(query, query_embedding, session, role, channel, limit)
            else:
                results = await self._search_sqlite(query, query_embedding, session, role, channel, limit)
        except Exception as exc:
            logger.error("Error en búsqueda RAG error=%s", type(exc).__name__)
            return []
        filtered = [item for item in results if item["similarity"] >= min_similarity][:top_k]
        self._cache[cache_key] = (time.monotonic(), filtered)
        await self._mark_chat_run(session, filtered, cache_hit=False)
        logger.info("RAG search completada role=%s channel=%s found=%s", role, channel, len(filtered))
        return filtered

    @staticmethod
    async def _mark_chat_run(session: AsyncSession, results: list[dict[str, Any]], *, cache_hit: bool) -> None:
        current_chat_citations.set(tuple(item["citation"] for item in results if item.get("citation")))
        current_chat_rag_cache_hit.set(cache_hit)

    async def search_and_format_context(
        self,
        query: str,
        session: AsyncSession,
        top_k: int = 3,
        min_similarity: float = 0.5,
        role: str = "guest",
        channel: str = "web",
    ) -> str:
        chunks = await self.search(query, session, top_k, min_similarity, role, channel)
        context: list[str] = []
        used_tokens = 0
        for index, chunk in enumerate(chunks, 1):
            citation = chunk["citation"]
            block = (
                f"--- Fragmento {index} [fuente:{citation['source_id']} chunk:{citation['chunk_index']} "
                f"versión:{citation['content_version']}] ---\n{chunk['content']}\n"
            )
            estimated_tokens = max(1, len(block) // 4)
            if used_tokens + estimated_tokens > settings.rag_context_max_tokens:
                break
            context.append(block)
            used_tokens += estimated_tokens
        return "\n".join(context)


_rag_search_service: RAGSearchService | None = None


def get_rag_search_service() -> RAGSearchService:
    global _rag_search_service
    if _rag_search_service is None:
        _rag_search_service = RAGSearchService()
    return _rag_search_service
