#!/usr/bin/env python
# NG-HEADER: Nombre de archivo: ollama_client.py
# NG-HEADER: Ubicación: services/catalog_audit/ollama_client.py
# NG-HEADER: Descripción: Cliente Ollama estricto y exclusivo del auditor de catálogo.
# NG-HEADER: Lineamientos: Ver AGENTS.md
"""Evaluación semántica local, determinista y con fallo cerrado."""

from __future__ import annotations

import json
import os
from typing import Any

import httpx


MODEL = "llama3.1:8b"
SEMANTIC_SCHEMA = {
    "type": "object",
    "properties": {
        "classification": {"type": "string"},
        "score": {"type": "integer", "minimum": 0, "maximum": 100},
        "critical": {"type": "boolean"},
        "fields": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "field": {"type": "string"},
                    "score": {"type": "integer", "minimum": 0, "maximum": 100},
                    "proposed_value": {},
                    "confidence": {"type": "number", "minimum": 0, "maximum": 1},
                    "explanation": {"type": "string"},
                    "sources": {"type": "array", "items": {"type": "string"}},
                },
                "required": ["field", "score", "confidence", "explanation", "sources"],
            },
        },
    },
    "required": ["classification", "score", "fields", "critical"],
}


class SemanticAuditError(RuntimeError):
    pass


class CatalogAuditOllamaClient:
    def __init__(self, *, transport: httpx.AsyncBaseTransport | None = None) -> None:
        self.base_url = os.getenv("CATALOG_AUDIT_OLLAMA_URL", "http://127.0.0.1:11434").rstrip("/")
        self.model = os.getenv("CATALOG_AUDIT_OLLAMA_MODEL", MODEL)
        self.transport = transport

    async def preflight(self) -> dict[str, Any]:
        runtime: dict[str, Any] = {}
        try:
            async with httpx.AsyncClient(transport=self.transport, timeout=5) as client:
                response = await client.get(f"{self.base_url}/api/tags")
                response.raise_for_status()
                models = [entry.get("name") for entry in response.json().get("models", [])]
                try:
                    running = await client.get(f"{self.base_url}/api/ps")
                    running.raise_for_status()
                    loaded = next((entry for entry in running.json().get("models", []) if entry.get("name") == self.model), None)
                    if loaded:
                        runtime = {
                            "loaded": True,
                            "size_bytes": loaded.get("size"),
                            "size_vram_bytes": loaded.get("size_vram"),
                        }
                except Exception:
                    runtime = {"loaded": False}
        except Exception:
            return {"ok": False, "code": "daemon_unavailable", "model": self.model}
        available = self.model in models or any(name and name.startswith(f"{self.model}:") for name in models)
        return {
            "ok": available,
            "code": None if available else "model_unavailable",
            "model": self.model,
            "runtime": runtime,
        }

    async def audit(self, snapshot: dict[str, Any]) -> dict[str, Any]:
        prompt = (
            "Audita este producto de catálogo. No propongas cambios de precio, stock, identidad ni SKU. "
            "Devuelve solamente JSON conforme al schema. Producto: "
            + json.dumps(snapshot, ensure_ascii=False, default=str)
        )
        payload = {
            "model": self.model,
            "prompt": prompt,
            "stream": False,
            "format": SEMANTIC_SCHEMA,
            "options": {"temperature": 0, "num_ctx": 4096, "num_predict": 2048},
        }
        try:
            async with httpx.AsyncClient(transport=self.transport, timeout=180) as client:
                for attempt in range(2):
                    response = await client.post(f"{self.base_url}/api/generate", json=payload)
                    response.raise_for_status()
                    envelope = response.json()
                    raw = envelope.get("response")
                    try:
                        result = json.loads(raw)
                        break
                    except (TypeError, json.JSONDecodeError) as exc:
                        if attempt == 1:
                            raise SemanticAuditError("invalid_json") from exc
        except httpx.HTTPError as exc:
            raise SemanticAuditError("daemon_unavailable") from exc
        if not self._valid(result):
            raise SemanticAuditError("schema_invalid")
        result["_runtime"] = {
            "model": envelope.get("model") or self.model,
            "total_duration_ns": envelope.get("total_duration"),
            "load_duration_ns": envelope.get("load_duration"),
            "eval_duration_ns": envelope.get("eval_duration"),
            "eval_count": envelope.get("eval_count"),
        }
        return result

    @staticmethod
    def _valid(result: Any) -> bool:
        if not isinstance(result, dict):
            return False
        if not isinstance(result.get("classification"), str):
            return False
        if not isinstance(result.get("score"), int) or not 0 <= result["score"] <= 100:
            return False
        if not isinstance(result.get("critical"), bool) or not isinstance(result.get("fields"), list):
            return False
        required = {"field", "score", "confidence", "explanation", "sources"}
        return all(isinstance(field, dict) and required <= set(field) and isinstance(field["sources"], list) for field in result["fields"])
