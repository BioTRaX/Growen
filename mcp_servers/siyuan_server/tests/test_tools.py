#!/usr/bin/env python
# NG-HEADER: Nombre de archivo: test_tools.py
# NG-HEADER: Ubicación: mcp_servers/siyuan_server/tests/test_tools.py
# NG-HEADER: Descripción: Pruebas de validación y herramientas documentales de SiYuan.
# NG-HEADER: Lineamientos: Ver AGENTS.md

from __future__ import annotations

import importlib
from typing import Any

import pytest


tools_module = importlib.import_module("mcp_servers.siyuan_server.tools")


class FakeClient:
    def __init__(self, responses: dict[str, Any]) -> None:
        self.responses = responses
        self.calls: list[tuple[str, dict[str, Any], bool]] = []

    async def post(self, endpoint: str, payload: dict[str, Any], *, retry_read: bool = False) -> Any:
        self.calls.append((endpoint, payload, retry_read))
        return self.responses[endpoint]


def _service(client: FakeClient):
    return tools_module.SiYuanService(
        client=client,
        notebook_name="Nice Grow",
        allowed_path_prefix="/Growen",
    )


@pytest.mark.asyncio
async def test_search_uses_readonly_fixed_sql_and_escapes_user_term() -> None:
    client = FakeClient(
        {
            "/api/notebook/lsNotebooks": {"notebooks": [{"id": "box-1", "name": "Nice Grow", "closed": False}]},
            "/api/query/sql": [
                {"root_id": "doc-1", "hpath": "/Growen/Uno", "content": "50%", "updated": "20260827"},
                {"root_id": "doc-1", "hpath": "/Growen/Uno", "content": "duplicado", "updated": "20260827"},
            ],
        }
    )

    result = await _service(client).search_documents("50%_'", limit=20)

    endpoint, payload, retry_read = client.calls[-1]
    assert endpoint == "/api/query/sql"
    assert payload["mode"] == "readonly"
    assert "50\\%\\_''" in payload["stmt"]
    assert "box = 'box-1'" in payload["stmt"]
    assert "hpath LIKE '/Growen/%'" in payload["stmt"]
    assert retry_read is True
    assert result["count"] == 1
    assert result["items"][0]["document_id"] == "doc-1"


@pytest.mark.parametrize("query", ["", "a", "x" * 201])
@pytest.mark.asyncio
async def test_search_rejects_query_outside_limits(query: str) -> None:
    client = FakeClient({})
    with pytest.raises(ValueError, match="query_invalid"):
        await _service(client).search_documents(query)


@pytest.mark.parametrize(
    "path",
    ["Growen/SinBarra", "/Otra/Nota", "/Growen/../Secreto", "/Growen/" + "x" * 505],
)
@pytest.mark.asyncio
async def test_create_rejects_paths_outside_authorized_prefix(path: str) -> None:
    client = FakeClient({})
    with pytest.raises(ValueError, match="path_invalid"):
        await _service(client).create_document(path, "contenido")


@pytest.mark.asyncio
async def test_create_rejects_existing_document_without_writing() -> None:
    client = FakeClient(
        {
            "/api/notebook/lsNotebooks": {"notebooks": [{"id": "box-1", "name": "Nice Grow", "closed": False}]},
            "/api/filetree/getIDsByHPath": ["doc-existing"],
        }
    )

    with pytest.raises(tools_module.DocumentExistsError, match="document_exists"):
        await _service(client).create_document("/Growen/Existente", "contenido")

    assert all(call[0] != "/api/filetree/createDocWithMd" for call in client.calls)


@pytest.mark.asyncio
async def test_create_writes_once_and_returns_stable_shape() -> None:
    client = FakeClient(
        {
            "/api/notebook/lsNotebooks": {"notebooks": [{"id": "box-1", "name": "Nice Grow", "closed": False}]},
            "/api/filetree/getIDsByHPath": [],
            "/api/filetree/createDocWithMd": "doc-new",
        }
    )

    result = await _service(client).create_document("/Growen/Nueva", "# Nueva")

    assert result == {"document_id": "doc-new", "hpath": "/Growen/Nueva", "created": True}
    create_calls = [call for call in client.calls if call[0] == "/api/filetree/createDocWithMd"]
    assert len(create_calls) == 1
    assert create_calls[0][1] == {"notebook": "box-1", "path": "/Growen/Nueva", "markdown": "# Nueva"}
    assert create_calls[0][2] is False


@pytest.mark.asyncio
async def test_read_returns_exported_markdown() -> None:
    client = FakeClient({"/api/export/exportMdContent": {"hPath": "/Growen/Nota", "content": "# Nota"}})

    result = await _service(client).read_document("20260827123456-abcdefg")

    assert result == {
        "document_id": "20260827123456-abcdefg",
        "hpath": "/Growen/Nota",
        "markdown": "# Nota",
    }
