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


def load_notion_settings() -> NotionSettings:
    return NotionSettings(
        enabled=_bool_env(os.getenv("NOTION_FEATURE_ENABLED"), False),
        api_key=os.getenv("NOTION_API_KEY") or None,
        errors_db=os.getenv("NOTION_ERRORS_DATABASE_ID") or None,
        dry_run=_bool_env(os.getenv("NOTION_DRY_RUN"), True),
        timeout=int(os.getenv("NOTION_TIMEOUT", "25")),
        max_retries=int(os.getenv("NOTION_MAX_RETRIES", "3")),
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
