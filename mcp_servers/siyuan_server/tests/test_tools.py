#!/usr/bin/env python
# NG-HEADER: Nombre de archivo: test_tools.py
# NG-HEADER: Ubicación: mcp_servers/siyuan_server/tests/test_tools.py
# NG-HEADER: Descripción: Pruebas de validación y herramientas documentales de SiYuan.
# NG-HEADER: Lineamientos: Ver AGENTS.md

from __future__ import annotations

import hashlib
import importlib
from typing import Any

import pytest


tools_module = importlib.import_module("mcp_servers.siyuan_server.tools")
client_module = importlib.import_module("mcp_servers.siyuan_server.client")


class FakeClient:
    def __init__(self, responses: dict[str, Any]) -> None:
        self.responses = responses
        self.calls: list[tuple[str, dict[str, Any], bool]] = []

    async def post(self, endpoint: str, payload: dict[str, Any], *, retry_read: bool = False) -> Any:
        self.calls.append((endpoint, payload, retry_read))
        response = self.responses[endpoint]
        if isinstance(response, tuple):
            current, *remaining = response
            self.responses[endpoint] = tuple(remaining)
            response = current
        if isinstance(response, Exception):
            raise response
        return response


class SequencedExportClient(FakeClient):
    def __init__(self, responses: dict[str, Any], exports: list[Any]) -> None:
        super().__init__(responses)
        self.exports = list(exports)

    async def post(self, endpoint: str, payload: dict[str, Any], *, retry_read: bool = False) -> Any:
        if endpoint == "/api/export/exportMdContent":
            self.calls.append((endpoint, payload, retry_read))
            response = self.exports.pop(0)
            if isinstance(response, Exception):
                raise response
            return response
        return await super().post(endpoint, payload, retry_read=retry_read)


def _service(
    client: FakeClient,
    *,
    visible_path_prefixes: tuple[str, ...] = ("/Growen",),
):
    return tools_module.SiYuanService(
        client=client,
        notebook_name="Nice Grow",
        git_path_prefix="/Growen",
        private_path_prefixes=("/Negocio", "/Operación"),
        visible_path_prefixes=visible_path_prefixes,
    )


def _admin_service(client: FakeClient):
    return _service(
        client,
        visible_path_prefixes=("/Growen", "/Negocio", "/Operación"),
    )


@pytest.mark.parametrize(
    ("private_prefixes", "visible_prefixes"),
    [
        (("Negocio",), ("/Growen", "Negocio")),
        (("/Growen",), ("/Growen",)),
        (("/Negocio/../Secreto",), ("/Growen", "/Negocio/../Secreto")),
        (("/Negocio",), ("/Growen", "/Otra")),
    ],
)
def test_service_rejects_unsafe_or_unconfigured_path_prefixes(
    private_prefixes: tuple[str, ...],
    visible_prefixes: tuple[str, ...],
) -> None:
    with pytest.raises(ValueError, match="path_prefix_invalid"):
        tools_module.SiYuanService(
            client=FakeClient({}),
            notebook_name="Nice Grow",
            git_path_prefix="/Growen",
            private_path_prefixes=private_prefixes,
            visible_path_prefixes=visible_prefixes,
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
    assert "GROUP BY root_id" in payload["stmt"]
    assert retry_read is True
    assert result["count"] == 1
    assert result["items"][0]["document_id"] == "doc-1"


@pytest.mark.asyncio
async def test_search_limits_sql_to_collaborator_visible_root() -> None:
    client = FakeClient(
        {
            "/api/notebook/lsNotebooks": {
                "notebooks": [{"id": "box-1", "name": "Nice Grow", "closed": False}]
            },
            "/api/query/sql": [],
        }
    )

    await _service(client).search_documents("Growen")

    stmt = client.calls[-1][1]["stmt"]
    assert "hpath = '/Growen'" in stmt
    assert "hpath LIKE '/Growen/%'" in stmt
    assert "/Negocio" not in stmt
    assert "/Operación" not in stmt


@pytest.mark.asyncio
async def test_search_admin_sql_includes_all_authorized_roots() -> None:
    client = FakeClient(
        {
            "/api/notebook/lsNotebooks": {
                "notebooks": [{"id": "box-1", "name": "Nice Grow", "closed": False}]
            },
            "/api/query/sql": [],
        }
    )

    await _service(
        client,
        visible_path_prefixes=("/Growen", "/Negocio", "/Operación"),
    ).search_documents("privado")

    stmt = client.calls[-1][1]["stmt"]
    assert "hpath LIKE '/Growen/%'" in stmt
    assert "hpath LIKE '/Negocio/%'" in stmt
    assert "hpath LIKE '/Operación/%'" in stmt


@pytest.mark.asyncio
async def test_search_escapes_like_wildcards_in_configured_root() -> None:
    client = FakeClient(
        {
            "/api/notebook/lsNotebooks": {
                "notebooks": [{"id": "box-1", "name": "Nice Grow", "closed": False}]
            },
            "/api/query/sql": [],
        }
    )
    service = tools_module.SiYuanService(
        client=client,
        notebook_name="Nice Grow",
        git_path_prefix="/Growen",
        private_path_prefixes=("/Negocio_%",),
        visible_path_prefixes=("/Negocio_%",),
    )

    await service.search_documents("privado")

    stmt = client.calls[-1][1]["stmt"]
    assert "hpath LIKE '/Negocio\\_\\%/%' ESCAPE '\\'" in stmt


@pytest.mark.parametrize("query", ["", "a", "x" * 201])
@pytest.mark.asyncio
async def test_search_rejects_query_outside_limits(query: str) -> None:
    client = FakeClient({})
    with pytest.raises(ValueError, match="query_invalid"):
        await _service(client).search_documents(query)


@pytest.mark.parametrize(
    "path",
    ["Negocio/SinBarra", "/Otra/Nota", "/Negocio/../Secreto", "/Negocio/" + "x" * 505],
)
@pytest.mark.asyncio
async def test_create_rejects_paths_outside_authorized_prefix(path: str) -> None:
    client = FakeClient({})
    with pytest.raises((ValueError, tools_module.DocumentForbiddenError)):
        await _admin_service(client).create_document(path, "contenido")


@pytest.mark.asyncio
async def test_create_rejects_growen_because_git_is_authoritative() -> None:
    client = FakeClient({})

    with pytest.raises(tools_module.GitAuthorityRequiredError, match="git_authority_required"):
        await _admin_service(client).create_document("/Growen/Nueva", "contenido")


@pytest.mark.asyncio
async def test_create_rejects_existing_document_without_writing() -> None:
    client = FakeClient(
        {
            "/api/notebook/lsNotebooks": {"notebooks": [{"id": "box-1", "name": "Nice Grow", "closed": False}]},
            "/api/filetree/getIDsByHPath": ["doc-existing"],
        }
    )

    with pytest.raises(tools_module.DocumentExistsError, match="document_exists"):
        await _admin_service(client).create_document("/Negocio/Existente", "contenido")

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

    result = await _admin_service(client).create_document("/Negocio/Nueva", "# Nueva")

    assert result == {"document_id": "doc-new", "hpath": "/Negocio/Nueva", "created": True}
    create_calls = [call for call in client.calls if call[0] == "/api/filetree/createDocWithMd"]
    assert len(create_calls) == 1
    assert create_calls[0][1] == {"notebook": "box-1", "path": "/Negocio/Nueva", "markdown": "# Nueva"}
    assert create_calls[0][2] is False


@pytest.mark.asyncio
async def test_read_returns_exported_markdown() -> None:
    client = FakeClient(
        {
            "/api/notebook/lsNotebooks": {
                "notebooks": [{"id": "box-1", "name": "Nice Grow", "closed": False}]
            },
            "/api/query/sql": [
                {
                    "id": "20260827123456-abcdefg",
                    "root_id": "20260827123456-abcdefg",
                    "box": "box-1",
                    "hpath": "/Growen/Nota",
                }
            ],
            "/api/export/exportMdContent": {"hPath": "/Growen/Nota", "content": "# Nota"},
        }
    )

    result = await _service(client).read_document("20260827123456-abcdefg")

    assert result == {
        "document_id": "20260827123456-abcdefg",
        "hpath": "/Growen/Nota",
        "markdown": "# Nota",
        "revision_sha256": hashlib.sha256(b"# Nota").hexdigest(),
    }


@pytest.mark.asyncio
async def test_read_rejects_private_document_before_export_for_collaborator() -> None:
    client = FakeClient(
        {
            "/api/notebook/lsNotebooks": {
                "notebooks": [{"id": "box-1", "name": "Nice Grow", "closed": False}]
            },
            "/api/query/sql": [
                {
                    "id": "20260827123456-abcdefg",
                    "root_id": "20260827123456-abcdefg",
                    "box": "box-1",
                    "hpath": "/Negocio/Plan privado",
                }
            ],
        }
    )

    with pytest.raises(tools_module.DocumentForbiddenError, match="document_forbidden"):
        await _service(client).read_document("20260827123456-abcdefg")

    assert all(call[0] != "/api/export/exportMdContent" for call in client.calls)


@pytest.mark.asyncio
async def test_read_revalidates_path_after_export_before_returning_content() -> None:
    client = FakeClient(
        {
            "/api/notebook/lsNotebooks": {
                "notebooks": [{"id": "box-1", "name": "Nice Grow", "closed": False}]
            },
            "/api/query/sql": (
                [_document_row("/Growen/Nota")],
                [_document_row("/Negocio/Nota privada")],
            ),
            "/api/export/exportMdContent": {
                "hPath": "/Growen/Nota",
                "content": "contenido que ya no debe devolverse",
            },
        }
    )

    with pytest.raises(tools_module.DocumentForbiddenError, match="document_forbidden"):
        await _service(client).read_document("20260827123456-abcdefg")


def _document_row(hpath: str) -> dict[str, str]:
    return {
        "id": "20260827123456-abcdefg",
        "root_id": "20260827123456-abcdefg",
        "box": "box-1",
        "hpath": hpath,
    }


def _update_client(*, hpath: str = "/Negocio/Plan", exports: list[Any] | None = None):
    return SequencedExportClient(
        {
            "/api/notebook/lsNotebooks": {
                "notebooks": [{"id": "box-1", "name": "Nice Grow", "closed": False}]
            },
            "/api/query/sql": [_document_row(hpath)],
            "/api/history/createDocHistory": None,
            "/api/block/updateBlock": [{"doOperations": [{"action": "update"}]}],
        },
        exports
        or [
            {"hPath": hpath, "content": "versión anterior"},
            {"hPath": hpath, "content": "versión anterior"},
            {"hPath": hpath, "content": "versión normalizada"},
        ],
    )


@pytest.mark.asyncio
async def test_update_private_document_uses_history_and_returns_actual_revision() -> None:
    client = _update_client()
    previous = hashlib.sha256("versión anterior".encode()).hexdigest()

    result = await _admin_service(client).update_document(
        "20260827123456-abcdefg",
        "versión nueva",
        previous,
    )

    assert result == {
        "document_id": "20260827123456-abcdefg",
        "hpath": "/Negocio/Plan",
        "updated": True,
        "previous_revision_sha256": previous,
        "revision_sha256": hashlib.sha256("versión normalizada".encode()).hexdigest(),
    }
    endpoints = [call[0] for call in client.calls]
    assert endpoints.index("/api/history/createDocHistory") < endpoints.index("/api/block/updateBlock")
    update_call = next(call for call in client.calls if call[0] == "/api/block/updateBlock")
    assert update_call[1] == {
        "dataType": "markdown",
        "data": "versión nueva",
        "id": "20260827123456-abcdefg",
    }
    assert update_call[2] is False


@pytest.mark.asyncio
async def test_update_rejects_stale_revision_without_writing() -> None:
    client = _update_client(exports=[{"hPath": "/Negocio/Plan", "content": "actual"}])

    with pytest.raises(tools_module.DocumentConflictError, match="document_conflict"):
        await _admin_service(client).update_document(
            "20260827123456-abcdefg",
            "nuevo",
            "0" * 64,
        )

    endpoints = [call[0] for call in client.calls]
    assert "/api/history/createDocHistory" not in endpoints
    assert "/api/block/updateBlock" not in endpoints


@pytest.mark.asyncio
async def test_update_rechecks_revision_after_history_before_writing() -> None:
    client = _update_client(
        exports=[
            {"hPath": "/Negocio/Plan", "content": "actual"},
            {"hPath": "/Negocio/Plan", "content": "cambio concurrente"},
        ]
    )
    revision = hashlib.sha256(b"actual").hexdigest()

    with pytest.raises(tools_module.DocumentConflictError, match="document_conflict"):
        await _admin_service(client).update_document(
            "20260827123456-abcdefg",
            "nuevo",
            revision,
        )

    assert all(call[0] != "/api/block/updateBlock" for call in client.calls)


@pytest.mark.asyncio
async def test_update_revalidates_path_immediately_before_writing() -> None:
    client = _update_client(
        exports=[
            {"hPath": "/Negocio/Plan", "content": "actual"},
            {"hPath": "/Negocio/Plan", "content": "actual"},
        ]
    )
    client.responses["/api/query/sql"] = (
        [_document_row("/Negocio/Plan")],
        [_document_row("/Growen/Plan")],
    )
    revision = hashlib.sha256(b"actual").hexdigest()

    with pytest.raises(tools_module.GitAuthorityRequiredError, match="git_authority_required"):
        await _admin_service(client).update_document(
            "20260827123456-abcdefg",
            "nuevo",
            revision,
        )

    assert all(call[0] != "/api/block/updateBlock" for call in client.calls)


@pytest.mark.asyncio
async def test_update_rejects_growen_before_export() -> None:
    client = _update_client(hpath="/Growen/docs/MCP", exports=[])

    with pytest.raises(tools_module.GitAuthorityRequiredError, match="git_authority_required"):
        await _admin_service(client).update_document(
            "20260827123456-abcdefg",
            "nuevo",
            "0" * 64,
        )

    assert all(call[0] != "/api/export/exportMdContent" for call in client.calls)


@pytest.mark.asyncio
async def test_update_timeout_reports_unknown_status_without_retry() -> None:
    client = _update_client(
        exports=[
            {"hPath": "/Negocio/Plan", "content": "actual"},
            {"hPath": "/Negocio/Plan", "content": "actual"},
        ]
    )
    client.responses["/api/block/updateBlock"] = client_module.SiYuanTimeoutError("siyuan_timeout")
    revision = hashlib.sha256(b"actual").hexdigest()

    with pytest.raises(
        tools_module.DocumentWriteStatusUnknownError,
        match="document_write_status_unknown",
    ):
        await _admin_service(client).update_document(
            "20260827123456-abcdefg",
            "nuevo",
            revision,
        )

    update_calls = [call for call in client.calls if call[0] == "/api/block/updateBlock"]
    assert len(update_calls) == 1


@pytest.mark.asyncio
async def test_update_api_error_reports_unknown_status_without_retry() -> None:
    client = _update_client(
        exports=[
            {"hPath": "/Negocio/Plan", "content": "actual"},
            {"hPath": "/Negocio/Plan", "content": "actual"},
        ]
    )
    client.responses["/api/block/updateBlock"] = client_module.SiYuanAPIError(
        "siyuan_api_error"
    )
    revision = hashlib.sha256(b"actual").hexdigest()

    with pytest.raises(
        tools_module.DocumentWriteStatusUnknownError,
        match="document_write_status_unknown",
    ):
        await _admin_service(client).update_document(
            "20260827123456-abcdefg",
            "nuevo",
            revision,
        )

    update_calls = [call for call in client.calls if call[0] == "/api/block/updateBlock"]
    assert len(update_calls) == 1


@pytest.mark.asyncio
async def test_update_history_failure_aborts_before_write() -> None:
    client = _update_client(exports=[{"hPath": "/Negocio/Plan", "content": "actual"}])
    client.responses["/api/history/createDocHistory"] = RuntimeError("history_failed")
    revision = hashlib.sha256(b"actual").hexdigest()

    with pytest.raises(RuntimeError, match="history_failed"):
        await _admin_service(client).update_document(
            "20260827123456-abcdefg",
            "nuevo",
            revision,
        )

    assert all(call[0] != "/api/block/updateBlock" for call in client.calls)


@pytest.mark.asyncio
async def test_update_empty_readback_reports_unknown_status() -> None:
    client = _update_client(
        exports=[
            {"hPath": "/Negocio/Plan", "content": "actual"},
            {"hPath": "/Negocio/Plan", "content": "actual"},
            {"hPath": "/Negocio/Plan", "content": ""},
        ]
    )
    revision = hashlib.sha256(b"actual").hexdigest()

    with pytest.raises(
        tools_module.DocumentWriteStatusUnknownError,
        match="document_write_status_unknown",
    ):
        await _admin_service(client).update_document(
            "20260827123456-abcdefg",
            "nuevo",
            revision,
        )


@pytest.mark.asyncio
async def test_update_success_without_observable_change_reports_unknown_status() -> None:
    client = _update_client(
        exports=[
            {"hPath": "/Negocio/Plan", "content": "actual"},
            {"hPath": "/Negocio/Plan", "content": "actual"},
            {"hPath": "/Negocio/Plan", "content": "actual"},
        ]
    )
    revision = hashlib.sha256(b"actual").hexdigest()

    with pytest.raises(
        tools_module.DocumentWriteStatusUnknownError,
        match="document_write_status_unknown",
    ):
        await _admin_service(client).update_document(
            "20260827123456-abcdefg",
            "nuevo",
            revision,
        )


def _task_database_client(*, hpath: str = "/Operación") -> FakeClient:
    return FakeClient(
        {
            "/api/notebook/lsNotebooks": {
                "notebooks": [{"id": "box-1", "name": "Nice Grow", "closed": False}]
            },
            "/api/query/sql": (
                [_document_row(hpath)],
                [],
                [_document_row(hpath)],
                [_document_row(hpath)],
            ),
            "/api/history/createDocHistory": None,
            "/api/block/appendBlock": (
                [{"doOperations": [{"action": "insert", "id": "20260828120000-heading"}]}],
                [{"doOperations": [{"action": "insert", "id": "20260828120000-avblock"}]}],
            ),
            "/api/av/renderAttributeView": (
                {
                    "id": "20260828120000-avid001",
                    "viewID": "20260828120000-view001",
                    "view": {
                        "columns": [
                            {"id": "20260828120000-primary", "name": "Primary Key", "type": "block"},
                            {"id": "20260828120000-default", "name": "Select", "type": "select"},
                        ],
                        "rows": [],
                    },
                },
                {
                    "id": "20260828120000-avid001",
                    "viewID": "20260828120000-view001",
                    "view": {
                        "columns": [
                            {"id": "20260828120000-primary", "name": "Primary Key", "type": "block"}
                        ],
                        "rows": [
                            {
                                "id": "20260828120000-item001",
                                "cells": [
                                    {
                                        "value": {
                                            "type": "block",
                                            "block": {"content": "Nueva tarea"},
                                        }
                                    }
                                ],
                            }
                        ],
                    },
                },
            ),
            "/api/av/addAttributeViewKey": None,
            "/api/av/removeAttributeViewKey": None,
            "/api/av/addAttributeViewBlocks": None,
            "/api/av/setAttributeViewBlockAttr": None,
        }
    )


@pytest.mark.asyncio
async def test_create_task_database_builds_expected_private_table(monkeypatch) -> None:
    client = _task_database_client()
    generated = iter(
        [
            "20260828120000-avid001",
            "20260828120000-avseed1",
            "20260828120000-date001",
            "20260828120000-state01",
            "20260828120000-updated",
            "20260828120000-rowseed",
        ]
    )
    monkeypatch.setattr(tools_module, "_new_node_id", lambda: next(generated))

    result = await _admin_service(client).create_task_database(
        "20260827123456-abcdefg"
    )

    assert result == {
        "document_id": "20260827123456-abcdefg",
        "hpath": "/Operación",
        "heading_id": "20260828120000-heading",
        "database_block_id": "20260828120000-avblock",
        "attribute_view_id": "20260828120000-avid001",
        "view_id": "20260828120000-view001",
        "row_id": "20260828120000-item001",
        "created": True,
    }
    endpoints = [call[0] for call in client.calls]
    assert endpoints.index("/api/history/createDocHistory") < endpoints.index(
        "/api/block/appendBlock"
    )
    assert endpoints.count("/api/block/appendBlock") == 2
    assert endpoints.count("/api/av/addAttributeViewKey") == 3
    assert endpoints.count("/api/av/removeAttributeViewKey") == 1
    assert endpoints.count("/api/av/setAttributeViewBlockAttr") == 2
    heading_call = next(
        call
        for call in client.calls
        if call[0] == "/api/block/appendBlock" and call[1]["dataType"] == "markdown"
    )
    assert heading_call[1]["data"] == "## Tareas"
    key_calls = [call[1] for call in client.calls if call[0] == "/api/av/addAttributeViewKey"]
    assert [(call["keyName"], call["keyType"]) for call in key_calls] == [
        ("Fecha", "date"),
        ("Estado", "select"),
        ("Última modificación", "updated"),
    ]


@pytest.mark.asyncio
async def test_create_task_database_rejects_growen_before_history() -> None:
    client = _task_database_client(hpath="/Growen")

    with pytest.raises(tools_module.GitAuthorityRequiredError, match="git_authority_required"):
        await _admin_service(client).create_task_database("20260827123456-abcdefg")

    assert all(call[0] != "/api/history/createDocHistory" for call in client.calls)


@pytest.mark.asyncio
async def test_create_task_database_reports_unknown_after_partial_write() -> None:
    client = _task_database_client()
    client.responses["/api/block/appendBlock"] = (
        [{"doOperations": [{"action": "insert", "id": "20260828120000-heading"}]}],
        client_module.SiYuanAPIError("siyuan_api_error"),
    )

    with pytest.raises(
        tools_module.DocumentWriteStatusUnknownError,
        match="document_write_status_unknown",
    ):
        await _admin_service(client).create_task_database("20260827123456-abcdefg")


@pytest.mark.asyncio
async def test_create_task_database_reconciles_generated_default_select() -> None:
    client = _task_database_client()
    client.responses["/api/query/sql"] = (
        [_document_row("/Operación")],
        [
            {"id": "20260828120000-heading", "type": "h", "markdown": "## Tareas", "sort": 10},
            {
                "id": "20260828120000-avblock",
                "type": "av",
                "markdown": (
                    '<div data-type="NodeAttributeView" '
                    'data-av-id="20260828120000-avid001" data-av-type="table"></div>'
                ),
                "sort": 20,
            },
        ],
        [_document_row("/Operación")],
        [_document_row("/Operación")],
    )
    rendered = {
        "id": "20260828120000-avid001",
        "viewID": "20260828120000-view001",
        "view": {
            "columns": [
                {"id": "20260828120000-primary", "name": "Primary Key", "type": "block"},
                {"id": "20260828120000-date001", "name": "Fecha", "type": "date"},
                {"id": "20260828120000-state01", "name": "Estado", "type": "select"},
                {"id": "20260828120000-updated", "name": "Última modificación", "type": "updated"},
                {"id": "20260828120000-default", "name": "Select", "type": "select"},
            ],
            "rows": [
                {
                    "id": "20260828120000-item001",
                    "cells": [
                        {"value": {"type": "block", "block": {"content": "Nueva tarea"}}}
                    ],
                }
            ],
        },
    }
    client.responses["/api/av/renderAttributeView"] = (rendered, rendered)

    result = await _admin_service(client).create_task_database("20260827123456-abcdefg")

    assert result["created"] is False
    assert result["attribute_view_id"] == "20260828120000-avid001"
    assert [call[0] for call in client.calls].count("/api/av/removeAttributeViewKey") == 1
    assert all(call[0] != "/api/block/appendBlock" for call in client.calls)


@pytest.mark.asyncio
async def test_find_document_by_path_is_restricted_to_git_root() -> None:
    client = FakeClient(
        {
            "/api/notebook/lsNotebooks": {
                "notebooks": [{"id": "box-1", "name": "Nice Grow", "closed": False}]
            },
            "/api/filetree/getIDsByHPath": ["20260827123456-abcdefg"],
        }
    )

    document_id = await _admin_service(client).find_document_by_path(
        "/Growen/Documentación técnica/README"
    )

    assert document_id == "20260827123456-abcdefg"
    assert client.calls[-1][1] == {
        "notebook": "box-1",
        "path": "/Growen/Documentación técnica/README",
    }


@pytest.mark.asyncio
async def test_create_git_document_uses_internal_git_policy() -> None:
    client = FakeClient(
        {
            "/api/notebook/lsNotebooks": {
                "notebooks": [{"id": "box-1", "name": "Nice Grow", "closed": False}]
            },
            "/api/filetree/getIDsByHPath": [],
            "/api/filetree/createDocWithMd": "20260827123456-abcdefg",
        }
    )

    result = await _admin_service(client).create_git_document(
        "/Growen/Documentación técnica/README",
        "# Growen",
    )

    assert result["created"] is True
    assert result["hpath"] == "/Growen/Documentación técnica/README"


@pytest.mark.asyncio
async def test_update_git_document_uses_same_history_and_revision_guard() -> None:
    client = _update_client(hpath="/Growen/Documentación técnica/README")
    previous = hashlib.sha256("versión anterior".encode()).hexdigest()

    result = await _admin_service(client).update_git_document(
        "20260827123456-abcdefg",
        "versión Git",
        previous,
    )

    assert result["updated"] is True
    assert result["previous_revision_sha256"] == previous
    endpoints = [call[0] for call in client.calls]
    assert endpoints.index("/api/history/createDocHistory") < endpoints.index("/api/block/updateBlock")
