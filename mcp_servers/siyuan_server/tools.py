#!/usr/bin/env python
# NG-HEADER: Nombre de archivo: tools.py
# NG-HEADER: Ubicación: mcp_servers/siyuan_server/tools.py
# NG-HEADER: Descripción: Herramientas MCP restringidas para documentación en SiYuan.
# NG-HEADER: Lineamientos: Ver AGENTS.md

from __future__ import annotations

import re
from typing import Any, Protocol


MAX_MARKDOWN_BYTES = 1024 * 1024
MAX_PATH_CHARS = 512
DOCUMENT_ID_RE = re.compile(r"^[0-9]{14}-[a-z0-9]{7}$")


class ClientProtocol(Protocol):
    async def post(
        self,
        endpoint: str,
        payload: dict[str, Any],
        *,
        retry_read: bool = False,
    ) -> Any: ...


class DocumentExistsError(ValueError):
    pass


def _sql_literal(value: str) -> str:
    return value.replace("'", "''")


def _like_term(value: str) -> str:
    return _sql_literal(value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_"))


class SiYuanService:
    def __init__(
        self,
        *,
        client: ClientProtocol,
        notebook_name: str,
        allowed_path_prefix: str,
        notebook_id: str | None = None,
    ) -> None:
        self.client = client
        self.notebook_name = notebook_name.strip()
        self.allowed_path_prefix = allowed_path_prefix.rstrip("/")
        self.configured_notebook_id = notebook_id.strip() if notebook_id else None
        self._resolved_notebook_id: str | None = None

    async def list_notebooks(self) -> dict[str, Any]:
        data = await self.client.post(
            "/api/notebook/lsNotebooks",
            {},
            retry_read=True,
        )
        notebooks = data.get("notebooks", []) if isinstance(data, dict) else []
        items = [
            {
                "id": str(item.get("id") or ""),
                "name": str(item.get("name") or ""),
                "closed": bool(item.get("closed", False)),
            }
            for item in notebooks
            if isinstance(item, dict) and item.get("id")
        ]
        return {"items": items, "count": len(items)}

    async def _notebook_id(self) -> str:
        if self._resolved_notebook_id:
            return self._resolved_notebook_id
        listed = await self.list_notebooks()
        items = listed["items"]
        if self.configured_notebook_id:
            match = next((item for item in items if item["id"] == self.configured_notebook_id), None)
        else:
            match = next((item for item in items if item["name"] == self.notebook_name), None)
        if not match or match["closed"]:
            raise ValueError("notebook_unavailable")
        self._resolved_notebook_id = match["id"]
        return self._resolved_notebook_id

    async def search_documents(self, query: str, limit: int = 20) -> dict[str, Any]:
        query = str(query).strip()
        if not 2 <= len(query) <= 200:
            raise ValueError("query_invalid")
        limit = int(limit)
        if not 1 <= limit <= 50:
            raise ValueError("limit_invalid")
        notebook_id = await self._notebook_id()
        term = _like_term(query)
        prefix = _sql_literal(f"{self.allowed_path_prefix}/%")
        stmt = (
            "SELECT root_id, hpath, content, updated FROM blocks "
            f"WHERE box = '{_sql_literal(notebook_id)}' "
            f"AND hpath LIKE '{prefix}' "
            "AND type IN ('d','h','p','l','i','c') "
            f"AND content LIKE '%{term}%' ESCAPE '\\' "
            "ORDER BY updated DESC "
            f"LIMIT {limit}"
        )
        rows = await self.client.post(
            "/api/query/sql",
            {"stmt": stmt, "mode": "readonly"},
            retry_read=True,
        )
        seen: set[str] = set()
        items: list[dict[str, Any]] = []
        for row in rows if isinstance(rows, list) else []:
            document_id = str(row.get("root_id") or "")
            if not document_id or document_id in seen:
                continue
            seen.add(document_id)
            items.append(
                {
                    "document_id": document_id,
                    "hpath": str(row.get("hpath") or ""),
                    "snippet": str(row.get("content") or "")[:500],
                    "updated": str(row.get("updated") or ""),
                }
            )
        return {"items": items, "count": len(items), "query": query}

    async def read_document(self, document_id: str) -> dict[str, Any]:
        document_id = str(document_id).strip()
        if not DOCUMENT_ID_RE.fullmatch(document_id):
            raise ValueError("document_id_invalid")
        data = await self.client.post(
            "/api/export/exportMdContent",
            {"id": document_id},
            retry_read=True,
        )
        if not isinstance(data, dict):
            raise ValueError("document_response_invalid")
        return {
            "document_id": document_id,
            "hpath": str(data.get("hPath") or ""),
            "markdown": str(data.get("content") or ""),
        }

    def _validate_path(self, path: str) -> str:
        path = str(path).strip()
        if (
            not path.startswith(f"{self.allowed_path_prefix}/")
            or len(path) > MAX_PATH_CHARS
            or ".." in path.split("/")
            or "//" in path
        ):
            raise ValueError("path_invalid")
        return path

    async def create_document(self, path: str, markdown: str) -> dict[str, Any]:
        path = self._validate_path(path)
        markdown = str(markdown)
        if not markdown.strip() or len(markdown.encode("utf-8")) > MAX_MARKDOWN_BYTES:
            raise ValueError("markdown_invalid")
        notebook_id = await self._notebook_id()
        existing = await self.client.post(
            "/api/filetree/getIDsByHPath",
            {"notebook": notebook_id, "path": path},
            retry_read=True,
        )
        if existing:
            raise DocumentExistsError("document_exists")
        document_id = await self.client.post(
            "/api/filetree/createDocWithMd",
            {"notebook": notebook_id, "path": path, "markdown": markdown},
        )
        if not isinstance(document_id, str) or not document_id:
            raise ValueError("document_create_invalid")
        return {"document_id": document_id, "hpath": path, "created": True}


__all__ = ["DocumentExistsError", "SiYuanService"]
