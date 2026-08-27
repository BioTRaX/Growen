#!/usr/bin/env python
# NG-HEADER: Nombre de archivo: test_siyuan_smoke.py
# NG-HEADER: Ubicación: tests/test_siyuan_smoke.py
# NG-HEADER: Descripción: Prueba del flujo de smoke documental de SiYuan.
# NG-HEADER: Lineamientos: Ver AGENTS.md

from __future__ import annotations

import pytest

from scripts import smoke_siyuan_mcp as smoke


class FakeService:
    async def list_notebooks(self):
        return {"items": [{"id": "box", "name": "Nice Grow", "closed": False}], "count": 1}

    async def search_documents(self, query: str, limit: int = 20):
        return {"items": [{"document_id": "20260827120000-abcdefg", "hpath": "/Growen/README"}], "count": 1, "query": query}

    async def read_document(self, document_id: str):
        if document_id == "20260827120000-abcdefg":
            return {"document_id": document_id, "hpath": "/Growen/README", "markdown": "Growen"}
        return {"document_id": document_id, "hpath": "/Growen/Pruebas MCP/Test", "markdown": smoke.SMOKE_MARKDOWN}

    async def create_document(self, path: str, markdown: str):
        assert path.startswith("/Growen/Pruebas MCP/")
        assert markdown == smoke.SMOKE_MARKDOWN
        return {"document_id": "20260827130000-hijklmn", "hpath": path, "created": True}


@pytest.mark.asyncio
async def test_smoke_reads_existing_creates_and_reads_back() -> None:
    result = await smoke.run_smoke(FakeService(), timestamp="20260827-130000")

    assert result["status"] == "ok"
    assert result["existing_document_id"] == "20260827120000-abcdefg"
    assert result["created_document_id"] == "20260827130000-hijklmn"
    assert "markdown" not in result
