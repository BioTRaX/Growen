#!/usr/bin/env python
# NG-HEADER: Nombre de archivo: tools.py
# NG-HEADER: Ubicación: mcp_servers/products_server/tools.py
# NG-HEADER: Descripción: Implementación de herramientas MCP para consulta de productos
# NG-HEADER: Lineamientos: Ver AGENTS.md

"""Herramientas (tools) expuestas por el Servidor MCP de Productos.

Solo cubre el MVP de "info de primer nivel".

Futuras expansiones:
- info de segundo nivel (relaciones, categoría, supplier offers)
- info extendida (historial de stock, pricing, auditoría)

Todas las funciones reciben `user_role` para aplicar control de acceso.
"""
from __future__ import annotations

from typing import Any, Dict, Tuple, List
import os
import time
import httpx
import logging

# Cache in-memory simple (MVP). Se consulta TTL en runtime para permitir variación en tests.
_cache: dict[str, Tuple[float, Dict[str, Any]]] = {}

# Logger básico configurable vía LOG_LEVEL (info por defecto)
LOG_LEVEL = os.getenv("LOG_LEVEL", "info").upper()
logging.basicConfig(level=getattr(logging, LOG_LEVEL, logging.INFO))
logger = logging.getLogger("mcp_products.tools")

# Roles permitidos para la herramienta "full" (por ahora hace lo mismo que la básica)
_FULL_INFO_ROLES = {"admin", "colaborador"}


class PermissionError(ValueError):
    """Error de permiso insuficiente para la operación solicitada."""


def _get_cache_ttl() -> float:
    """Lee el TTL de cache desde variables de entorno en runtime."""
    try:
        return float(os.getenv("MCP_CACHE_TTL_SECONDS", "0") or 0)
    except ValueError:
        return 0.0


def _get_api_base_url() -> str:
    return os.getenv("API_BASE_URL", "http://api:8000")


def _cache_get(key: str) -> Dict[str, Any] | None:
    ttl = _get_cache_ttl()
    if ttl <= 0:
        return None
    item = _cache.get(key)
    if not item:
        return None
    ts, value = item
    if time.time() - ts > ttl:
        _cache.pop(key, None)
        return None
    return value


def _cache_put(key: str, value: Dict[str, Any]) -> None:
    ttl = _get_cache_ttl()
    if ttl <= 0:
        return
    _cache[key] = (time.time(), value)


async def get_product_info(sku: str, user_role: str) -> Dict[str, Any]:
    """Obtiene información de primer nivel de un producto por SKU interno.

    Args:
        sku: SKU interno del sistema (variant.sku en el dominio actual).
        user_role: Rol declarado del usuario que solicita la información. No se restringe en MVP.

    Returns:
        Diccionario con claves: name, sale_price, stock, sku.

    Raises:
        httpx.HTTPStatusError: Si la API responde un status >= 400.
        httpx.RequestError: Problema de red al invocar la API.
        KeyError: Si la respuesta no contiene campos esperados (indicará necesidad de ajustar mapping).
    """
    # Diseño: la API actual probablemente expone /products o /variants.
    # Suponemos un endpoint existente /variants/lookup?sku={sku} (si no existe, se documentará para backend principal).
    # Como fallback se intenta /products/by-sku/{sku}.
    # Cache lookup
    cache_key = f"product_info:{sku}"
    cached = _cache_get(cache_key)
    if cached:
        logger.debug("Cache HIT para sku=%s", sku)
        return cached

    base_url = _get_api_base_url()
    candidate_endpoints = [
        f"{base_url}/variants/lookup?sku={sku}",  # endpoint sugerido / a implementar
        f"{base_url}/products/by-sku/{sku}",      # alternativa posible
    ]
    async with httpx.AsyncClient(timeout=5.0) as client:
        last_exc: Exception | None = None
        for url in candidate_endpoints:
            try:
                logger.debug("Consultando URL=%s", url)
                resp = await client.get(url)
                if resp.status_code == 404:
                    # probamos siguiente
                    logger.debug("Endpoint %s devolvió 404, probando siguiente", url)
                    continue
                resp.raise_for_status()
                data = resp.json()
                # Se asume shape potencial:
                # Variante: {"sku":..., "name":..., "sale_price":..., "stock": ...}
                result = {
                    "sku": data["sku"],
                    "name": data.get("name") or data.get("title") or "(sin nombre)",
                    "sale_price": data.get("sale_price"),
                    "stock": data.get("stock"),
                }
                _cache_put(cache_key, result)
                logger.debug("Cache SET sku=%s", sku)
                return result
            except httpx.TimeoutException as exc:  # noqa: PERF203
                logger.warning("Timeout URL=%s sku=%s: %s", url, sku, exc)
                last_exc = exc
                continue
            except httpx.RequestError as exc:
                logger.warning("RequestError URL=%s sku=%s: %s", url, sku, exc)
                last_exc = exc
                continue
            except Exception as exc:  # noqa: BLE001 (controlado para fallback)
                last_exc = exc
                continue
        if last_exc:
            logger.warning("Fallo al obtener producto sku=%s: %s", sku, last_exc)
            raise last_exc
        raise KeyError("No se encontró el producto ni se pudo mapear la respuesta.")


async def get_product_full_info(sku: str, user_role: str) -> Dict[str, Any]:
    """Obtiene información completa (MVP: igual a primer nivel) validando permisos.

    En el futuro se añadirá:
      - detalles extendidos (categorías, suppliers, históricos, métricas).

    Args:
        sku: SKU interno del sistema.
        user_role: Rol declarado del usuario que solicita. Debe ser 'admin' o 'colaborador'.

    Returns:
        Diccionario con la misma estructura que `get_product_info` en este MVP.

    Raises:
        PermissionError: Si el rol no está autorizado para información "full".
        httpx.HTTPStatusError / httpx.RequestError: Errores de transporte a la API.
        KeyError: Campos faltantes en la respuesta de la API.
    """
    if user_role not in _FULL_INFO_ROLES:
        raise PermissionError("Permission denied: rol insuficiente para información completa.")
    # Por ahora reutiliza la función simple.
    return await get_product_info(sku=sku, user_role=user_role)


async def find_products_by_name(query: str, user_role: str) -> Dict[str, Any]:
    """Busca productos por nombre (búsqueda parcial) y retorna coincidencias básicas.

    Args:
        query: Texto ingresado por el usuario (nombre parcial o completo).
        user_role: Rol declarado (no se restringe en MVP).

    Returns:
        Dict con clave `items` que es una lista de productos (name, sku) y `count`.

    Notas:
        - Endpoint asumido: /products/search?q= (debe existir en la API principal).
        - En caso de error de red o status >=400 se propaga la excepción httpx.* para manejo superior.
        - Se normalizan claves mínimas para el agente.
    """
    if not query or not isinstance(query, str):
        raise ValueError("Parámetro 'query' requerido (string no vacío).")
    base_url = _get_api_base_url()
    url = f"{base_url}/products/search?q={httpx.QueryParams({'q': query})['q']}"  # asegura encoding
    async with httpx.AsyncClient(timeout=5.0) as client:
        resp = await client.get(url)
        resp.raise_for_status()
        data = resp.json()
        # Se asume una lista de productos. Adaptar si la API devuelve otro shape.
        items: List[Dict[str, Any]] = []
        if isinstance(data, list):
            source_iter = data
        else:
            # Fallback si la API responde {"items": [...]} o similar
            source_iter = data.get("items", []) if isinstance(data, dict) else []
        for prod in source_iter:
            if not isinstance(prod, dict):
                continue
            name = prod.get("name") or prod.get("title") or "(sin nombre)"
            sku = prod.get("sku") or prod.get("variant_sku") or prod.get("id")
            if not sku:
                continue  # ignorar entradas sin SKU interno
            items.append({"name": name, "sku": sku})
        return {"items": items, "count": len(items), "query": query}


TOOLS_REGISTRY = {
    "get_product_info": get_product_info,
    "get_product_full_info": get_product_full_info,
    "find_products_by_name": find_products_by_name,
}


async def invoke_tool(tool_name: str, parameters: Dict[str, Any]) -> Dict[str, Any]:
    """Despacha la herramienta solicitada.

    Args:
        tool_name: Nombre registrado de la herramienta.
        parameters: Parámetros (deben incluir `sku` y `user_role`).

    Returns:
        Resultado de la herramienta como dict.

    Raises:
        KeyError: Si el tool no existe.
        ValueError: Validaciones internas de parámetros.
    """
    if tool_name not in TOOLS_REGISTRY:
        raise KeyError(f"Tool desconocida: {tool_name}")
    if not isinstance(parameters, dict):
        raise ValueError("parameters debe ser un objeto JSON (dict).")
    user_role = parameters.get("user_role")
    if not user_role or not isinstance(user_role, str):
        raise ValueError("Parámetro 'user_role' requerido (string).")

    func = TOOLS_REGISTRY[tool_name]
    if tool_name == "find_products_by_name":
        query = parameters.get("query")
        if not query or not isinstance(query, str):
            raise ValueError("Parámetro 'query' requerido (string).")
        logger.info("Invocando tool=%s query=%s role=%s", tool_name, query, user_role)
        return await func(query=query, user_role=user_role)  # type: ignore[arg-type]
    else:
        sku = parameters.get("sku")
        if not sku or not isinstance(sku, str):
            raise ValueError("Parámetro 'sku' requerido (string).")
        logger.info("Invocando tool=%s sku=%s role=%s", tool_name, sku, user_role)
        return await func(sku=sku, user_role=user_role)  # type: ignore[arg-type]
