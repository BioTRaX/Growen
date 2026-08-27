#!/usr/bin/env python
# NG-HEADER: Nombre de archivo: test_publish_docs_to_siyuan.py
# NG-HEADER: Ubicación: tests/test_publish_docs_to_siyuan.py
# NG-HEADER: Descripción: Pruebas de publicación create-only de Markdown hacia SiYuan.
# NG-HEADER: Lineamientos: Ver AGENTS.md

from __future__ import annotations

from pathlib import Path

import pytest

from scripts import publish_docs_to_siyuan as publisher


class FakeService:
    def __init__(self) -> None:
        self.created: list[tuple[str, str]] = []

    async def create_document(self, path: str, markdown: str):
        self.created.append((path, markdown))
        if path.endswith("Existente"):
            raise publisher.DocumentExistsError("document_exists")
        return {"document_id": "20260827123456-abcdefg", "hpath": path, "created": True}


def test_siyuan_path_preserves_repository_structure() -> None:
    root = Path("C:/repo")

    assert publisher.siyuan_path(root / "README.md", root) == "/Growen/Documentación técnica/README"
    assert publisher.siyuan_path(root / "docs" / "MCP.md", root) == "/Growen/Documentación técnica/docs/MCP"


def test_discover_documents_excludes_archive_and_generated_plans(tmp_path) -> None:
    (tmp_path / "README.md").write_text("root", encoding="utf-8")
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "MCP.md").write_text("mcp", encoding="utf-8")
    (tmp_path / "docs" / "archive").mkdir()
    (tmp_path / "docs" / "archive" / "OLD.md").write_text("old", encoding="utf-8")
    (tmp_path / "docs" / "superpowers").mkdir()
    (tmp_path / "docs" / "superpowers" / "PLAN.md").write_text("plan", encoding="utf-8")

    documents = publisher.discover_documents(tmp_path)

    assert [path.relative_to(tmp_path).as_posix() for path in documents] == ["README.md", "docs/MCP.md"]


@pytest.mark.asyncio
async def test_publish_manifest_contains_hash_but_not_content(tmp_path) -> None:
    document = tmp_path / "Existente.md"
    document.write_text("contenido secreto de documentación", encoding="utf-8")
    service = FakeService()

    result = await publisher.publish_documents([document], tmp_path, service, apply=True)

    assert result[0]["status"] == "skipped"
    assert result[0]["sha256"]
    assert "markdown" not in result[0]
    assert "contenido" not in str(result[0])


@pytest.mark.asyncio
async def test_dry_run_does_not_create_documents(tmp_path) -> None:
    document = tmp_path / "Nueva.md"
    document.write_text("# Nueva", encoding="utf-8")
    service = FakeService()

    result = await publisher.publish_documents([document], tmp_path, service, apply=False)

    assert result[0]["status"] == "planned"
    assert service.created == []
