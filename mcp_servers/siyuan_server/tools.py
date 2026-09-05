#!/usr/bin/env python
# NG-HEADER: Nombre de archivo: tools.py
# NG-HEADER: Ubicación: mcp_servers/siyuan_server/tools.py
# NG-HEADER: Descripción: Herramientas MCP restringidas para documentación en SiYuan.
# NG-HEADER: Lineamientos: Ver AGENTS.md

from __future__ import annotations

import hashlib
import re
import secrets
import string
from datetime import datetime
from typing import Any, Protocol

from .client import SiYuanError


MAX_MARKDOWN_BYTES = 1024 * 1024
MAX_PATH_CHARS = 512
DOCUMENT_ID_RE = re.compile(r"^[0-9]{14}-[a-z0-9]{7}$")
REVISION_SHA256_RE = re.compile(r"^[a-f0-9]{64}$")
ATTRIBUTE_VIEW_ID_RE = re.compile(r'data-av-id="([0-9]{14}-[a-z0-9]{7})"')
NODE_ID_ALPHABET = string.ascii_lowercase + string.digits


def _new_node_id() -> str:
    suffix = "".join(secrets.choice(NODE_ID_ALPHABET) for _ in range(7))
    return f"{datetime.now().strftime('%Y%m%d%H%M%S')}-{suffix}"


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


class DocumentNotFoundError(ValueError):
    pass


class DocumentForbiddenError(PermissionError):
    pass


class GitAuthorityRequiredError(PermissionError):
    pass


class DocumentConflictError(ValueError):
    pass


class DocumentWriteStatusUnknownError(RuntimeError):
    pass


def _sql_literal(value: str) -> str:
    return value.replace("'", "''")


def _like_term(value: str) -> str:
    return _sql_literal(value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_"))


class SiYuanService:
    @staticmethod
    def _normalize_configured_prefix(prefix: str) -> str:
        normalized = str(prefix).strip().rstrip("/")
        if (
            not normalized.startswith("/")
            or normalized == ""
            or len(normalized) > MAX_PATH_CHARS
            or ".." in normalized.split("/")
            or "//" in normalized
        ):
            raise ValueError("path_prefix_invalid")
        return normalized

    def __init__(
        self,
        *,
        client: ClientProtocol,
        notebook_name: str,
        git_path_prefix: str,
        private_path_prefixes: tuple[str, ...] = (),
        visible_path_prefixes: tuple[str, ...] | None = None,
        notebook_id: str | None = None,
    ) -> None:
        self.client = client
        self.notebook_name = notebook_name.strip()
        self.git_path_prefix = self._normalize_configured_prefix(git_path_prefix)
        self.private_path_prefixes = tuple(
            self._normalize_configured_prefix(prefix) for prefix in private_path_prefixes
        )
        if (
            len(set(self.private_path_prefixes)) != len(self.private_path_prefixes)
            or any(
                self._path_matches_prefix(prefix, self.git_path_prefix)
                or self._path_matches_prefix(self.git_path_prefix, prefix)
                for prefix in self.private_path_prefixes
            )
        ):
            raise ValueError("path_prefix_invalid")
        configured_prefixes = {self.git_path_prefix, *self.private_path_prefixes}
        self.visible_path_prefixes = tuple(
            self._normalize_configured_prefix(prefix)
            for prefix in (visible_path_prefixes or (self.git_path_prefix,))
        )
        if not self.visible_path_prefixes or not set(self.visible_path_prefixes).issubset(
            configured_prefixes
        ):
            raise ValueError("path_prefix_invalid")
        self.configured_notebook_id = notebook_id.strip() if notebook_id else None
        self._resolved_notebook_id: str | None = None

    @staticmethod
    def _path_matches_prefix(path: str, prefix: str) -> bool:
        return path == prefix or path.startswith(f"{prefix}/")

    def _path_is_visible(self, path: str) -> bool:
        return any(self._path_matches_prefix(path, prefix) for prefix in self.visible_path_prefixes)

    def _path_is_private(self, path: str) -> bool:
        return any(self._path_matches_prefix(path, prefix) for prefix in self.private_path_prefixes)

    @staticmethod
    def _paths_sql(prefixes: tuple[str, ...]) -> str:
        clauses = []
        for prefix in prefixes:
            literal = _sql_literal(prefix)
            like_literal = _like_term(prefix)
            clauses.append(f"hpath = '{literal}'")
            clauses.append(f"hpath LIKE '{like_literal}/%' ESCAPE '\\'")
        return "(" + " OR ".join(clauses) + ")"

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
        paths_clause = self._paths_sql(self.visible_path_prefixes)
        stmt = (
            "SELECT root_id, hpath, content, updated FROM blocks "
            f"WHERE box = '{_sql_literal(notebook_id)}' "
            f"AND {paths_clause} "
            "AND type IN ('d','h','p','l','i','c') "
            f"AND content LIKE '%{term}%' ESCAPE '\\' "
            "GROUP BY root_id "
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

    async def _document_metadata(self, document_id: str) -> dict[str, str]:
        notebook_id = await self._notebook_id()
        rows = await self.client.post(
            "/api/query/sql",
            {
                "stmt": (
                    "SELECT id, root_id, box, hpath FROM blocks "
                    f"WHERE id = '{_sql_literal(document_id)}' "
                    f"AND root_id = '{_sql_literal(document_id)}' "
                    f"AND box = '{_sql_literal(notebook_id)}' "
                    "AND type = 'd' LIMIT 1"
                ),
                "mode": "readonly",
            },
            retry_read=True,
        )
        if not isinstance(rows, list) or not rows or not isinstance(rows[0], dict):
            raise DocumentNotFoundError("document_not_found")
        metadata = rows[0]
        hpath = str(metadata.get("hpath") or "")
        if not self._path_is_visible(hpath):
            raise DocumentForbiddenError("document_forbidden")
        return {"document_id": document_id, "hpath": hpath}

    async def read_document(self, document_id: str) -> dict[str, Any]:
        document_id = str(document_id).strip()
        if not DOCUMENT_ID_RE.fullmatch(document_id):
            raise ValueError("document_id_invalid")
        metadata = await self._document_metadata(document_id)
        data = await self.client.post(
            "/api/export/exportMdContent",
            {"id": document_id},
            retry_read=True,
        )
        if not isinstance(data, dict):
            raise ValueError("document_response_invalid")
        markdown = str(data.get("content") or "")
        metadata = await self._document_metadata(document_id)
        return {
            "document_id": document_id,
            "hpath": metadata["hpath"],
            "markdown": markdown,
            "revision_sha256": hashlib.sha256(markdown.encode("utf-8")).hexdigest(),
        }

    @staticmethod
    def _validate_markdown(markdown: str) -> str:
        markdown = str(markdown)
        if not markdown.strip() or len(markdown.encode("utf-8")) > MAX_MARKDOWN_BYTES:
            raise ValueError("markdown_invalid")
        return markdown

    @staticmethod
    def _validate_common_path(path: str) -> str:
        path = str(path).strip()
        if (
            not path.startswith("/")
            or len(path) > MAX_PATH_CHARS
            or ".." in path.split("/")
            or "//" in path
        ):
            raise ValueError("path_invalid")
        return path

    def _validate_private_path(self, path: str) -> str:
        path = self._validate_common_path(path)
        if self._path_matches_prefix(path, self.git_path_prefix):
            raise GitAuthorityRequiredError("git_authority_required")
        if not self._path_is_private(path):
            raise DocumentForbiddenError("document_forbidden")
        if path in self.private_path_prefixes:
            raise ValueError("path_invalid")
        return path

    def _validate_git_path(self, path: str) -> str:
        path = self._validate_common_path(path)
        if not self._path_matches_prefix(path, self.git_path_prefix) or path == self.git_path_prefix:
            raise DocumentForbiddenError("document_forbidden")
        return path

    async def find_document_by_path(self, path: str) -> str | None:
        path = self._validate_git_path(path)
        notebook_id = await self._notebook_id()
        existing = await self.client.post(
            "/api/filetree/getIDsByHPath",
            {"notebook": notebook_id, "path": path},
            retry_read=True,
        )
        if not isinstance(existing, list) or not existing:
            return None
        document_id = str(existing[0] or "")
        return document_id or None

    async def _create_at_path(self, path: str, markdown: str) -> dict[str, Any]:
        markdown = self._validate_markdown(markdown)
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

    async def create_document(self, path: str, markdown: str) -> dict[str, Any]:
        return await self._create_at_path(self._validate_private_path(path), markdown)

    async def create_git_document(self, path: str, markdown: str) -> dict[str, Any]:
        return await self._create_at_path(self._validate_git_path(path), markdown)

    @staticmethod
    def _inserted_block_id(response: Any) -> str:
        if not isinstance(response, list):
            raise ValueError("document_write_response_invalid")
        for transaction in response:
            if not isinstance(transaction, dict):
                continue
            for operation in transaction.get("doOperations") or []:
                if not isinstance(operation, dict) or operation.get("action") != "insert":
                    continue
                block_id = str(operation.get("id") or "")
                if DOCUMENT_ID_RE.fullmatch(block_id):
                    return block_id
        raise ValueError("document_write_response_invalid")

    @staticmethod
    def _task_row_id(rendered: Any) -> str:
        view = rendered.get("view") if isinstance(rendered, dict) else None
        rows = view.get("rows") if isinstance(view, dict) else None
        for row in rows if isinstance(rows, list) else []:
            if not isinstance(row, dict):
                continue
            for cell in row.get("cells") or []:
                value = cell.get("value") if isinstance(cell, dict) else None
                block = value.get("block") if isinstance(value, dict) else None
                if isinstance(block, dict) and block.get("content") == "Nueva tarea":
                    item_id = str(row.get("id") or "")
                    if DOCUMENT_ID_RE.fullmatch(item_id):
                        return item_id
        raise ValueError("task_database_row_invalid")

    @staticmethod
    def _generated_default_select_ids(rendered: Any) -> list[str]:
        view = rendered.get("view") if isinstance(rendered, dict) else None
        columns = view.get("columns") if isinstance(view, dict) else None
        result = []
        for column in columns if isinstance(columns, list) else []:
            if not isinstance(column, dict):
                continue
            key_id = str(column.get("id") or "")
            if (
                column.get("name") == "Select"
                and column.get("type") == "select"
                and DOCUMENT_ID_RE.fullmatch(key_id)
            ):
                result.append(key_id)
        return result

    async def create_task_database(self, document_id: str) -> dict[str, Any]:
        document_id = str(document_id).strip()
        if not DOCUMENT_ID_RE.fullmatch(document_id):
            raise ValueError("document_id_invalid")

        metadata = await self._document_metadata(document_id)
        self._authorize_update_path(
            metadata["hpath"],
            writable_path_prefixes=self.private_path_prefixes,
            reject_git_authority=True,
        )
        existing = await self.client.post(
            "/api/query/sql",
            {
                "stmt": (
                    "SELECT id, type, markdown, sort FROM blocks "
                    f"WHERE root_id = '{_sql_literal(document_id)}' "
                    "AND ((type = 'h' AND content = 'Tareas') OR type = 'av') "
                    "ORDER BY sort"
                ),
                "mode": "readonly",
            },
            retry_read=True,
        )
        existing_rows = existing if isinstance(existing, list) else []
        heading = next(
            (
                row
                for row in existing_rows
                if isinstance(row, dict) and row.get("type") == "h"
            ),
            None,
        )
        if isinstance(heading, dict):
            heading_sort = int(heading.get("sort") or 0)
            database = next(
                (
                    row
                    for row in existing_rows
                    if isinstance(row, dict)
                    and row.get("type") == "av"
                    and int(row.get("sort") or 0) > heading_sort
                    and ATTRIBUTE_VIEW_ID_RE.search(str(row.get("markdown") or ""))
                ),
                None,
            )
            if not isinstance(database, dict):
                raise DocumentExistsError("document_exists")
            match = ATTRIBUTE_VIEW_ID_RE.search(str(database.get("markdown") or ""))
            attribute_view_id = match.group(1) if match else ""
            database_block_id = str(database.get("id") or "")
            heading_id = str(heading.get("id") or "")
            if not all(
                DOCUMENT_ID_RE.fullmatch(value)
                for value in (attribute_view_id, database_block_id, heading_id)
            ):
                raise DocumentExistsError("document_exists")

            await self.client.post(
                "/api/history/createDocHistory",
                {"id": document_id},
            )
            metadata = await self._document_metadata(document_id)
            self._authorize_update_path(
                metadata["hpath"],
                writable_path_prefixes=self.private_path_prefixes,
                reject_git_authority=True,
            )
            mutation_started = False
            try:
                rendered = await self.client.post(
                    "/api/av/renderAttributeView",
                    {
                        "id": attribute_view_id,
                        "blockID": database_block_id,
                        "viewID": "",
                        "page": 1,
                        "pageSize": 50,
                        "query": "",
                        "groupPaging": {},
                        "createIfNotExist": False,
                    },
                    retry_read=True,
                )
                columns = rendered.get("view", {}).get("columns", []) if isinstance(rendered, dict) else []
                required = {("Fecha", "date"), ("Estado", "select"), ("Última modificación", "updated")}
                present = {
                    (str(column.get("name") or ""), str(column.get("type") or ""))
                    for column in columns
                    if isinstance(column, dict)
                }
                if not required.issubset(present):
                    raise DocumentExistsError("document_exists")
                for key_id in self._generated_default_select_ids(rendered):
                    mutation_started = True
                    await self.client.post(
                        "/api/av/removeAttributeViewKey",
                        {
                            "avID": attribute_view_id,
                            "keyID": key_id,
                            "removeRelationDest": False,
                        },
                    )
                if mutation_started:
                    rendered = await self.client.post(
                        "/api/av/renderAttributeView",
                        {
                            "id": attribute_view_id,
                            "blockID": database_block_id,
                            "viewID": "",
                            "page": 1,
                            "pageSize": 50,
                            "query": "",
                            "groupPaging": {},
                            "createIfNotExist": False,
                        },
                        retry_read=True,
                    )
                view_id = str(rendered.get("viewID") or "")
                row_id = self._task_row_id(rendered)
                metadata = await self._document_metadata(document_id)
                self._authorize_update_path(
                    metadata["hpath"],
                    writable_path_prefixes=self.private_path_prefixes,
                    reject_git_authority=True,
                )
            except Exception as exc:
                if mutation_started:
                    raise DocumentWriteStatusUnknownError("document_write_status_unknown") from exc
                raise
            return {
                "document_id": document_id,
                "hpath": metadata["hpath"],
                "heading_id": heading_id,
                "database_block_id": database_block_id,
                "attribute_view_id": attribute_view_id,
                "view_id": view_id,
                "row_id": row_id,
                "created": False,
            }

        await self.client.post(
            "/api/history/createDocHistory",
            {"id": document_id},
        )
        metadata = await self._document_metadata(document_id)
        self._authorize_update_path(
            metadata["hpath"],
            writable_path_prefixes=self.private_path_prefixes,
            reject_git_authority=True,
        )

        mutation_started = False
        try:
            heading_response = await self.client.post(
                "/api/block/appendBlock",
                {"dataType": "markdown", "data": "## Tareas", "parentID": document_id},
            )
            mutation_started = True
            heading_id = self._inserted_block_id(heading_response)

            attribute_view_id = _new_node_id()
            database_seed_id = _new_node_id()
            database_response = await self.client.post(
                "/api/block/appendBlock",
                {
                    "dataType": "dom",
                    "data": (
                        f'<div data-node-id="{database_seed_id}" '
                        'data-type="NodeAttributeView" '
                        f'data-av-id="{attribute_view_id}" data-av-type="table"></div>'
                    ),
                    "parentID": document_id,
                },
            )
            database_block_id = self._inserted_block_id(database_response)
            rendered = await self.client.post(
                "/api/av/renderAttributeView",
                {
                    "id": attribute_view_id,
                    "blockID": database_block_id,
                    "viewID": "",
                    "page": 1,
                    "pageSize": 50,
                    "query": "",
                    "groupPaging": {},
                    "initialLayout": "table",
                    "createIfNotExist": True,
                },
            )
            view = rendered.get("view") if isinstance(rendered, dict) else None
            columns = view.get("columns") if isinstance(view, dict) else None
            primary_key_id = (
                str(columns[0].get("id") or "")
                if isinstance(columns, list) and columns and isinstance(columns[0], dict)
                else ""
            )
            view_id = str(rendered.get("viewID") or "") if isinstance(rendered, dict) else ""
            if not DOCUMENT_ID_RE.fullmatch(primary_key_id) or not DOCUMENT_ID_RE.fullmatch(view_id):
                raise ValueError("task_database_response_invalid")

            for key_id in self._generated_default_select_ids(rendered):
                await self.client.post(
                    "/api/av/removeAttributeViewKey",
                    {
                        "avID": attribute_view_id,
                        "keyID": key_id,
                        "removeRelationDest": False,
                    },
                )

            previous_key_id = primary_key_id
            field_ids: dict[str, str] = {}
            for field_name, field_type, field_key in (
                ("Fecha", "date", "date"),
                ("Estado", "select", "status"),
                ("Última modificación", "updated", "updated"),
            ):
                key_id = _new_node_id()
                await self.client.post(
                    "/api/av/addAttributeViewKey",
                    {
                        "avID": attribute_view_id,
                        "blockID": database_block_id,
                        "keyID": key_id,
                        "keyName": field_name,
                        "keyType": field_type,
                        "keyIcon": "",
                        "previousKeyID": previous_key_id,
                    },
                )
                field_ids[field_key] = key_id
                previous_key_id = key_id

            await self.client.post(
                "/api/av/addAttributeViewBlocks",
                {
                    "avID": attribute_view_id,
                    "blockID": database_block_id,
                    "viewID": view_id,
                    "groupID": "",
                    "previousID": "",
                    "srcs": [
                        {"id": _new_node_id(), "isDetached": True, "content": "Nueva tarea"}
                    ],
                    "ignoreDefaultFill": False,
                },
            )
            rendered = await self.client.post(
                "/api/av/renderAttributeView",
                {
                    "id": attribute_view_id,
                    "blockID": database_block_id,
                    "viewID": view_id,
                    "page": 1,
                    "pageSize": 50,
                    "query": "",
                    "groupPaging": {},
                    "createIfNotExist": False,
                },
            )
            row_id = self._task_row_id(rendered)
            now_ms = int(datetime.now().timestamp() * 1000)
            await self.client.post(
                "/api/av/setAttributeViewBlockAttr",
                {
                    "avID": attribute_view_id,
                    "keyID": field_ids["date"],
                    "itemID": row_id,
                    "value": {
                        "type": "date",
                        "date": {"content": now_ms, "isNotEmpty": True},
                    },
                },
            )
            await self.client.post(
                "/api/av/setAttributeViewBlockAttr",
                {
                    "avID": attribute_view_id,
                    "keyID": field_ids["status"],
                    "itemID": row_id,
                    "value": {
                        "type": "select",
                        "mSelect": [{"content": "Pendiente", "color": "1"}],
                    },
                },
            )
            metadata = await self._document_metadata(document_id)
            self._authorize_update_path(
                metadata["hpath"],
                writable_path_prefixes=self.private_path_prefixes,
                reject_git_authority=True,
            )
        except Exception as exc:
            if mutation_started:
                raise DocumentWriteStatusUnknownError("document_write_status_unknown") from exc
            raise

        return {
            "document_id": document_id,
            "hpath": metadata["hpath"],
            "heading_id": heading_id,
            "database_block_id": database_block_id,
            "attribute_view_id": attribute_view_id,
            "view_id": view_id,
            "row_id": row_id,
            "created": True,
        }

    async def update_document(
        self,
        document_id: str,
        markdown: str,
        expected_revision_sha256: str,
    ) -> dict[str, Any]:
        return await self._update_document_in_prefixes(
            document_id,
            markdown,
            expected_revision_sha256,
            writable_path_prefixes=self.private_path_prefixes,
            reject_git_authority=True,
        )

    async def update_git_document(
        self,
        document_id: str,
        markdown: str,
        expected_revision_sha256: str,
    ) -> dict[str, Any]:
        return await self._update_document_in_prefixes(
            document_id,
            markdown,
            expected_revision_sha256,
            writable_path_prefixes=(self.git_path_prefix,),
            reject_git_authority=False,
        )

    async def _update_document_in_prefixes(
        self,
        document_id: str,
        markdown: str,
        expected_revision_sha256: str,
        *,
        writable_path_prefixes: tuple[str, ...],
        reject_git_authority: bool,
    ) -> dict[str, Any]:
        document_id = str(document_id).strip()
        if not DOCUMENT_ID_RE.fullmatch(document_id):
            raise ValueError("document_id_invalid")
        markdown = self._validate_markdown(markdown)
        expected_revision_sha256 = str(expected_revision_sha256).strip().lower()
        if not REVISION_SHA256_RE.fullmatch(expected_revision_sha256):
            raise ValueError("revision_sha256_invalid")

        metadata = await self._document_metadata(document_id)
        hpath = metadata["hpath"]
        self._authorize_update_path(
            hpath,
            writable_path_prefixes=writable_path_prefixes,
            reject_git_authority=reject_git_authority,
        )

        current = await self.client.post(
            "/api/export/exportMdContent",
            {"id": document_id},
            retry_read=True,
        )
        if not isinstance(current, dict):
            raise ValueError("document_response_invalid")
        current_markdown = str(current.get("content") or "")
        previous_revision = hashlib.sha256(current_markdown.encode("utf-8")).hexdigest()
        if previous_revision != expected_revision_sha256:
            raise DocumentConflictError("document_conflict")

        await self.client.post(
            "/api/history/createDocHistory",
            {"id": document_id},
        )

        confirmed = await self.client.post(
            "/api/export/exportMdContent",
            {"id": document_id},
            retry_read=True,
        )
        if not isinstance(confirmed, dict):
            raise ValueError("document_response_invalid")
        confirmed_markdown = str(confirmed.get("content") or "")
        confirmed_revision = hashlib.sha256(
            confirmed_markdown.encode("utf-8")
        ).hexdigest()
        if confirmed_revision != previous_revision:
            raise DocumentConflictError("document_conflict")

        metadata = await self._document_metadata(document_id)
        hpath = metadata["hpath"]
        self._authorize_update_path(
            hpath,
            writable_path_prefixes=writable_path_prefixes,
            reject_git_authority=reject_git_authority,
        )

        try:
            await self.client.post(
                "/api/block/updateBlock",
                {"dataType": "markdown", "data": markdown, "id": document_id},
            )
        except SiYuanError as exc:
            raise DocumentWriteStatusUnknownError("document_write_status_unknown") from exc

        try:
            updated = await self.client.post(
                "/api/export/exportMdContent",
                {"id": document_id},
                retry_read=True,
            )
        except SiYuanError as exc:
            raise DocumentWriteStatusUnknownError("document_write_status_unknown") from exc
        if not isinstance(updated, dict):
            raise DocumentWriteStatusUnknownError("document_write_status_unknown")
        updated_markdown = str(updated.get("content") or "")
        if not updated_markdown.strip():
            raise DocumentWriteStatusUnknownError("document_write_status_unknown")
        updated_revision = hashlib.sha256(updated_markdown.encode("utf-8")).hexdigest()
        requested_revision = hashlib.sha256(markdown.encode("utf-8")).hexdigest()
        if updated_revision == previous_revision and requested_revision != previous_revision:
            raise DocumentWriteStatusUnknownError("document_write_status_unknown")
        try:
            metadata = await self._document_metadata(document_id)
            hpath = metadata["hpath"]
            self._authorize_update_path(
                hpath,
                writable_path_prefixes=writable_path_prefixes,
                reject_git_authority=reject_git_authority,
            )
        except (SiYuanError, DocumentForbiddenError, GitAuthorityRequiredError) as exc:
            raise DocumentWriteStatusUnknownError("document_write_status_unknown") from exc
        return {
            "document_id": document_id,
            "hpath": hpath,
            "updated": True,
            "previous_revision_sha256": previous_revision,
            "revision_sha256": updated_revision,
        }

    def _authorize_update_path(
        self,
        hpath: str,
        *,
        writable_path_prefixes: tuple[str, ...],
        reject_git_authority: bool,
    ) -> None:
        if reject_git_authority and self._path_matches_prefix(hpath, self.git_path_prefix):
            raise GitAuthorityRequiredError("git_authority_required")
        if not any(self._path_matches_prefix(hpath, prefix) for prefix in writable_path_prefixes):
            raise DocumentForbiddenError("document_forbidden")


__all__ = [
    "DocumentExistsError",
    "DocumentConflictError",
    "DocumentForbiddenError",
    "DocumentNotFoundError",
    "DocumentWriteStatusUnknownError",
    "GitAuthorityRequiredError",
    "SiYuanService",
]
