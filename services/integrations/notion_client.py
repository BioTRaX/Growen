#!/usr/bin/env python
# NG-HEADER: Nombre de archivo: notion_client.py
# NG-HEADER: Ubicación: services/integrations/notion_client.py
# NG-HEADER: Descripción: Cliente reusable para Notion (wrapper con backoff, dry-run y sanitización)
# NG-HEADER: Lineamientos: Ver AGENTS.md
from __future__ import annotations

import os
import time
import logging
from dataclasses import dataclass
from typing import Any, Dict, Optional

from agent_core.config import settings

try:  # notion sdk es opcional; la feature lleva flag
    from notion_client import Client as _NotionClient  # type: ignore
    from notion_client.errors import APIResponseError as _NotionAPIError  # type: ignore
except Exception:  # pragma: no cover - ausencia en entornos sin la lib
    _NotionClient = None  # type: ignore
    _NotionAPIError = Exception  # type: ignore


LOG = logging.getLogger("services.integrations.notion")


def _bool_env(x: Optional[str], default: bool = False) -> bool:
    if x is None:
        return default
    return str(x).strip().lower() in {"1", "true", "yes", "on"}


@dataclass
class NotionSettings:
    enabled: bool
    api_key: Optional[str]
    errors_db: Optional[str]
    dry_run: bool
    timeout: int
    max_retries: int
    mode: str  # 'cards' (por defecto) | 'sections'


def load_notion_settings() -> NotionSettings:
    return NotionSettings(
        enabled=_bool_env(os.getenv("NOTION_FEATURE_ENABLED"), False),
        api_key=os.getenv("NOTION_API_KEY") or None,
        errors_db=os.getenv("NOTION_ERRORS_DATABASE_ID") or None,
        dry_run=_bool_env(os.getenv("NOTION_DRY_RUN"), True),
        timeout=int(os.getenv("NOTION_TIMEOUT", "25")),
        max_retries=int(os.getenv("NOTION_MAX_RETRIES", "3")),
        mode=(os.getenv("NOTION_MODE") or "cards").strip().lower(),
    )


class NotionWrapper:
    """Wrapper del SDK de Notion con backoff y sanitización básica.

    Métodos principales:
    - health(): verifica precondiciones y credenciales mínimas cargadas.
    - query_by_fingerprint(db_id, fingerprint)
    - create_page(db_id, properties)
    - update_page(page_id, properties)
    """

    def __init__(self) -> None:
        self.cfg = load_notion_settings()
        self._client = None
        if self.cfg.enabled and self.cfg.api_key and _NotionClient is not None:
            self._client = _NotionClient(auth=self.cfg.api_key, timeout_ms=self.cfg.timeout * 1000)
        elif self.cfg.enabled and not self.cfg.api_key:
            LOG.warning("NOTION_FEATURE_ENABLED pero falta NOTION_API_KEY")

    def health(self) -> dict:
        return {
            "enabled": self.cfg.enabled,
            "has_sdk": _NotionClient is not None,
            "has_key": bool(self.cfg.api_key),
            "has_errors_db": bool(self.cfg.errors_db),
            "dry_run": self.cfg.dry_run,
        }

    # ---- Helpers
    def _sanitize_props(self, props: Dict[str, Any]) -> Dict[str, Any]:
        """Trunca campos largos y remueve valores None; caller debe usar tipos Notion.
        Asumimos que props viene en formato de propiedades Notion (title/rich_text/etc).
        """
        def truncate_text(text: str, max_len: int = 1800) -> str:
            return text if len(text) <= max_len else text[: max_len - 3] + "..."

        def walk(v: Any) -> Any:
            if isinstance(v, dict):
                return {k: walk(x) for k, x in v.items() if x is not None}
            if isinstance(v, list):
                return [walk(x) for x in v if x is not None]
            if isinstance(v, str):
                return truncate_text(v)
            return v

        return walk(props)  # type: ignore

    def _with_backoff(self, fn, *args, **kwargs):
        delay = 0.8
        for attempt in range(self.cfg.max_retries + 1):
            try:
                return fn(*args, **kwargs)
            except _NotionAPIError as e:  # type: ignore
                code = getattr(e, "status", None)
                if code in (429, 500, 502, 503, 504) and attempt < self.cfg.max_retries:
                    LOG.warning("Notion API error %s, retrying in %.1fs (attempt %d)", code, delay, attempt + 1)
                    time.sleep(delay)
                    delay *= 1.8
                    continue
                raise

    # ---- API
    def retrieve_database(self, db_id: str) -> Optional[Dict[str, Any]]:
        """Obtiene metadatos de una base (propiedades y tipos).

        Nota: las lecturas no se ven afectadas por dry_run; si el SDK o la key
        no están disponibles, retorna None.
        """
        if not self._client:
            LOG.info("[dry-run=%s] retrieve_database %s (sin cliente)", self.cfg.dry_run, db_id)
            return None
        try:
            res = self._with_backoff(self._client.databases.retrieve, **{"database_id": db_id})
            return res if isinstance(res, dict) else None
        except Exception as e:  # pragma: no cover
            LOG.exception("Error leyendo base Notion: %s", e)
            return None

    def get_title_property_name(self, db_id: str) -> Optional[str]:
        """Devuelve el nombre de la propiedad de tipo 'title' en la base."""
        meta = self.retrieve_database(db_id)
        if not meta or not isinstance(meta, dict):
            return None
        props = meta.get("properties", {})
        if isinstance(props, dict):
            for name, p in props.items():
                if isinstance(p, dict) and p.get("type") == "title":
                    return name
        return None

    def query_db_by_title(self, db_id: str, title_prop: str, title_equals: str) -> Optional[str]:
        """Busca una página en la DB cuyo título (prop dada) sea exactamente title_equals."""
        if self.cfg.dry_run or not self._client:
            LOG.info("[dry-run=%s] query_db_by_title %s=%s", self.cfg.dry_run, title_prop, title_equals)
            return None
        try:
            res = self._with_backoff(
                self._client.databases.query,
                **{
                    "database_id": db_id,
                    "filter": {
                        "property": title_prop,
                        "title": {"equals": title_equals},
                    },
                    "page_size": 1,
                },
            )
            results = res.get("results", []) if isinstance(res, dict) else []
            if results:
                return results[0]["id"]
            return None
        except Exception as e:  # pragma: no cover
            LOG.exception("Error consultando DB por título Notion: %s", e)
            return None

    def query_by_fingerprint(self, db_id: str, fingerprint: str) -> Optional[str]:
        if self.cfg.dry_run or not self._client:
            LOG.info("[dry-run=%s] query_by_fingerprint %s", self.cfg.dry_run, fingerprint)
            return None
        try:
            res = self._with_backoff(
                self._client.databases.query,
                **{
                    "database_id": db_id,
                    "filter": {
                        "property": "Fingerprint",
                        "rich_text": {"equals": fingerprint},
                    },
                    "page_size": 1,
                },
            )
            results = res.get("results", []) if isinstance(res, dict) else []
            if results:
                return results[0]["id"]
            return None
        except Exception as e:  # pragma: no cover
            LOG.exception("Error consultando Notion: %s", e)
            return None

    def create_page(self, db_id: str, properties: Dict[str, Any]) -> Optional[str]:
        props = self._sanitize_props(properties)
        if self.cfg.dry_run or not self._client:
            LOG.info("[dry-run=%s] create_page in %s: %s", self.cfg.dry_run, db_id, list(props.keys()))
            return None
        try:
            res = self._with_backoff(
                self._client.pages.create,
                **{
                    "parent": {"database_id": db_id},
                    "properties": props,
                },
            )
            return res.get("id") if isinstance(res, dict) else None
        except Exception as e:  # pragma: no cover
            LOG.exception("Error creando página Notion: %s", e)
            return None

    def update_page(self, page_id: str, properties: Dict[str, Any]) -> bool:
        props = self._sanitize_props(properties)
        if self.cfg.dry_run or not self._client:
            LOG.info("[dry-run=%s] update_page %s: %s", self.cfg.dry_run, page_id, list(props.keys()))
            return True
        try:
            self._with_backoff(self._client.pages.update, **{"page_id": page_id, "properties": props})
            return True
        except Exception as e:  # pragma: no cover
            LOG.exception("Error actualizando página Notion: %s", e)
            return False

    # ---- Blocks / Child pages (para modo 'sections')
    def list_block_children(self, block_id: str, page_size: int = 100) -> list[dict]:
        if not self._client:
            LOG.info("[dry-run=%s] list_block_children %s", self.cfg.dry_run, block_id)
            return []
        try:
            results: list[dict] = []
            start_cursor = None
            while True:
                kwargs = {"block_id": block_id, "page_size": page_size}
                if start_cursor:
                    kwargs["start_cursor"] = start_cursor
                res = self._with_backoff(self._client.blocks.children.list, **kwargs)
                if isinstance(res, dict):
                    results.extend(res.get("results", []))
                    if res.get("has_more") and res.get("next_cursor"):
                        start_cursor = res.get("next_cursor")
                        continue
                break
            return results
        except Exception as e:  # pragma: no cover
            LOG.exception("Error listando hijos Notion: %s", e)
            return []

    def create_child_page(self, parent_page_id: str, title: str, children_blocks: Optional[list[dict]] = None) -> Optional[str]:
        """Crea una subpágina bajo una página existente con contenido opcional."""
        if self.cfg.dry_run or not self._client:
            LOG.info("[dry-run=%s] create_child_page under %s: %s", self.cfg.dry_run, parent_page_id, title)
            return None
        try:
            payload: Dict[str, Any] = {
                "parent": {"page_id": parent_page_id},
                "properties": {"title": {"title": [{"type": "text", "text": {"content": title}}]}},
            }
            if children_blocks:
                payload["children"] = children_blocks
            res = self._with_backoff(self._client.pages.create, **payload)
            return res.get("id") if isinstance(res, dict) else None
        except Exception as e:  # pragma: no cover
            LOG.exception("Error creando subpágina Notion: %s", e)
            return None

    def find_child_page_by_title(self, parent_page_id: str, title: str) -> Optional[str]:
        """Busca una subpágina (child_page) bajo parent_page_id por su título exacto.

        Devuelve el id de la página (usa el id del block child_page, válido para appends).
        """
        children = self.list_block_children(parent_page_id)
        for ch in children:
            try:
                if ch.get("object") == "block" and ch.get("type") == "child_page":
                    cp = ch.get("child_page", {})
                    if isinstance(cp, dict) and cp.get("title") == title:
                        return ch.get("id")
            except Exception:
                continue
        return None

    def append_children(self, block_or_page_id: str, children_blocks: list[dict]) -> bool:
        """Agrega bloques al final del contenido de una página o bloque contenedor."""
        if self.cfg.dry_run or not self._client:
            LOG.info("[dry-run=%s] append_children %s: %d blocks", self.cfg.dry_run, block_or_page_id, len(children_blocks))
            return True
        try:
            self._with_backoff(
                self._client.blocks.children.append,
                **{"block_id": block_or_page_id, "children": children_blocks},
            )
            return True
        except Exception as e:  # pragma: no cover
            LOG.exception("Error anexando bloques en Notion: %s", e)
            return False
