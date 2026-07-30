#!/usr/bin/env python
# NG-HEADER: Nombre de archivo: chat_policy.py
# NG-HEADER: Ubicación: agent_core/chat_policy.py
# NG-HEADER: Descripción: Política central de roles, canales y herramientas del chatbot.
# NG-HEADER: Lineamientos: Ver AGENTS.md
"""Registro canónico de autorización del chatbot y sus herramientas."""

from __future__ import annotations

from dataclasses import dataclass
from contextvars import ContextVar
import os
from typing import Any, Literal


Role = Literal["guest", "cliente", "proveedor", "colaborador", "admin"]
Channel = Literal["web", "websocket", "telegram"]

ROLE_ORDER: tuple[Role, ...] = (
    "guest",
    "cliente",
    "proveedor",
    "colaborador",
    "admin",
)

# Propaga sólo el ID opaco de la ejecución dentro del mismo task async.
current_chat_run_id: ContextVar[str | None] = ContextVar("current_chat_run_id", default=None)
current_chat_citations: ContextVar[tuple[dict[str, Any], ...]] = ContextVar("current_chat_citations", default=())
current_chat_rag_cache_hit: ContextVar[bool] = ContextVar("current_chat_rag_cache_hit", default=False)


@dataclass(frozen=True)
class ToolPolicy:
    name: str
    server: str
    roles: frozenset[Role]
    channels: frozenset[Channel]
    capability: str
    read_only: bool = True
    output_profile: Literal["public", "operational"] = "public"


TOOL_POLICIES: dict[str, ToolPolicy] = {
    "find_products_by_name": ToolPolicy(
        "find_products_by_name",
        "products",
        frozenset(ROLE_ORDER),
        frozenset({"web", "websocket", "telegram"}),
        "catalog.public.read",
    ),
    "get_product_info": ToolPolicy(
        "get_product_info",
        "products",
        frozenset(ROLE_ORDER),
        frozenset({"web", "websocket", "telegram"}),
        "catalog.public.read",
    ),
    "get_product_full_info": ToolPolicy(
        "get_product_full_info",
        "products",
        frozenset({"colaborador", "admin"}),
        frozenset({"web", "websocket", "telegram"}),
        "catalog.operational.read",
        output_profile="operational",
    ),
    "search_web": ToolPolicy(
        "search_web",
        "web_search",
        frozenset({"colaborador", "admin"}),
        frozenset({"web", "websocket", "telegram"}),
        "web_search.read",
        output_profile="operational",
    ),
    "fetch_web_document": ToolPolicy(
        "fetch_web_document",
        "web_search",
        frozenset({"colaborador", "admin"}),
        frozenset({"web", "websocket", "telegram"}),
        "web_search.read",
        output_profile="operational",
    ),
}


def normalize_role(role: str | None) -> Role:
    """Normaliza aliases de canal al vocabulario canónico de Growen."""

    normalized = (role or "guest").strip().lower()
    if normalized in {"anon", "anonymous", "anonimo", "anónimo"}:
        return "guest"
    if normalized in ROLE_ORDER:
        return normalized  # type: ignore[return-value]
    return "guest"


def effective_role(account_role: str | None, channel: str, ceiling: str | None = None) -> Role:
    """Aplica el techo del canal sin modificar el rol persistido del usuario."""

    role = normalize_role(account_role)
    if channel != "telegram":
        return role
    channel_ceiling = normalize_role(ceiling or os.getenv("TELEGRAM_CHANNEL_ROLE_CEILING", "colaborador"))
    return ROLE_ORDER[min(ROLE_ORDER.index(role), ROLE_ORDER.index(channel_ceiling))]


def tool_allowed(tool_name: str, role: str, channel: str = "web") -> bool:
    policy = TOOL_POLICIES.get(tool_name)
    if policy is None or not policy.read_only and channel == "telegram":
        return False
    return normalize_role(role) in policy.roles and channel in policy.channels


def allowed_roles_for(tool_name: str) -> frozenset[Role]:
    policy = TOOL_POLICIES.get(tool_name)
    return policy.roles if policy else frozenset()


def public_product_result(value: dict[str, Any], role: str) -> dict[str, Any]:
    """Oculta SKU y stock exacto para perfiles de catálogo público."""

    if normalize_role(role) in {"colaborador", "admin"}:
        return value
    blocked = {
        "sku", "unique_sku", "supplier_sku", "variant_skus", "stock", "stock_qty",
        "initial_stock", "exact_stock", "product_id", "supplier_item_id", "canonical_id",
    }
    stock_marker = next((value.get(key) for key in ("stock", "stock_qty", "initial_stock", "exact_stock") if key in value), None)
    clean: dict[str, Any] = {}
    for key, item in value.items():
        if key.lower() in blocked or key.lower().endswith("_sku"):
            continue
        if isinstance(item, dict):
            clean[key] = public_product_result(item, role)
        elif isinstance(item, list):
            clean[key] = [public_product_result(entry, role) if isinstance(entry, dict) else entry for entry in item]
        else:
            clean[key] = item
    if stock_marker is not None:
        try:
            clean["availability"] = "disponible" if float(stock_marker) > 0 else "sin disponibilidad inmediata"
        except (TypeError, ValueError):
            clean["availability"] = "consultar"
    return clean
