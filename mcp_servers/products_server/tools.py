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
    """Retorna la URL base de la API principal desde env o default."""
    return os.getenv("API_BASE_URL", "http://api:8000")


def _get_internal_auth_headers() -> Dict[str, str]:
    """Genera headers de autenticación para servicios internos.
    
    Incluye el token de servicio interno (INTERNAL_SERVICE_TOKEN) en el header
    X-Internal-Service-Token para autenticarse ante la API principal.
    
    Returns:
        Dict con headers HTTP incluyendo token de autenticación.
    """
    token = os.getenv("INTERNAL_SERVICE_TOKEN", "")
    if not token:
        logger.warning("INTERNAL_SERVICE_TOKEN no configurado. Las peticiones pueden fallar con 403.")
        return {}
    return {"X-Internal-Service-Token": token}


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


async def get_product_info(sku: str = None, product_id: int = None, user_role: str = "guest") -> Dict[str, Any]:
    """Obtiene información de un producto por SKU canónico o ID, incluyendo descripción.

    Retorna datos del producto: name, sale_price, stock, sku, y descripción/especificaciones
    cuando están disponibles.

    Args:
        sku: SKU canónico del producto (formato XXX_####_YYY).
        product_id: ID interno del producto (alternativa al SKU).
        user_role: Rol declarado del usuario que solicita la información.

    Returns:
        Diccionario con claves: name, sale_price, stock, sku, description, technical_specs, usage_instructions.

    Raises:
        httpx.HTTPStatusError: Si la API responde un status >= 400.
        httpx.RequestError: Problema de red al invocar la API.
        KeyError: Si la respuesta no contiene campos esperados.
    """
    if not sku and not product_id:
        raise ValueError("Se requiere 'sku' o 'product_id'.")
    
    # Cache lookup
    cache_key = f"product_info:{product_id or sku}"
    cached = _cache_get(cache_key)
    if cached:
        logger.debug("Cache HIT para %s", cache_key)
        return cached

    base_url = _get_api_base_url()
    headers = _get_internal_auth_headers()
    
    # Construir URL con el parámetro disponible
    if product_id:
        url = f"{base_url}/variants/lookup?product_id={product_id}"
    else:
        url = f"{base_url}/variants/lookup?sku={sku}"
    
    async with httpx.AsyncClient(timeout=5.0) as client:
        try:
            logger.debug("get_product_info: Consultando URL=%s", url)
            resp = await client.get(url, headers=headers)
            resp.raise_for_status()
            data = resp.json()
            
            # DEBUG: Log de respuesta raw de la API
            logger.debug(
                "get_product_info: API Response raw - product_id=%s, sku=%s, has_description=%s, description_length=%d",
                data.get("product_id"),
                data.get("sku"),
                bool(data.get("description")),
                len(data.get("description") or "") if data.get("description") else 0,
            )
            
            # Construir resultado con toda la información disponible
            result = {
                "product_id": data.get("product_id"),
                "sku": data.get("sku"),
                "name": data.get("name") or data.get("title") or "(sin nombre)",
                "sale_price": data.get("sale_price"),
                "stock": data.get("stock"),
            }
            
            # Incluir descripción y especificaciones si están disponibles
            description = data.get("description")
            if description:
                result["description"] = description
                logger.debug(
                    "get_product_info: Incluyendo descripción (%d chars): %s...",
                    len(description),
                    description[:200] if len(description) > 200 else description,
                )
            else:
                logger.warning(
                    "get_product_info: SIN DESCRIPCION para product_id=%s sku=%s",
                    data.get("product_id"),
                    data.get("sku"),
                )
            
            technical_specs = data.get("technical_specs")
            if technical_specs and isinstance(technical_specs, dict) and technical_specs:
                result["technical_specs"] = technical_specs
                logger.debug("get_product_info: Incluyendo technical_specs: %s", list(technical_specs.keys()))
            
            usage_instructions = data.get("usage_instructions")
            if usage_instructions and isinstance(usage_instructions, dict) and usage_instructions:
                result["usage_instructions"] = usage_instructions
                logger.debug("get_product_info: Incluyendo usage_instructions: %s", list(usage_instructions.keys()))
            
            # DEBUG: Log final del resultado que se devuelve al LLM
            logger.info(
                "get_product_info: Tool Output - product_id=%s, sku=%s, name=%s, stock=%s, has_description=%s",
                result.get("product_id"),
                result.get("sku"),
                result.get("name"),
                result.get("stock"),
                "description" in result,
            )
            
            _cache_put(cache_key, result)
            return result
            
        except httpx.TimeoutException as exc:
            logger.warning("Timeout URL=%s: %s", url, exc)
            raise
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code == 404:
                logger.warning("Producto no encontrado: sku=%s product_id=%s", sku, product_id)
                raise KeyError("Producto no encontrado")
            raise
        except httpx.RequestError as exc:
            logger.warning("RequestError URL=%s: %s", url, exc)
            raise


async def get_product_full_info(sku: str = None, product_id: int = None, user_role: str = "guest") -> Dict[str, Any]:
    """Obtiene información completa del producto incluyendo datos de enriquecimiento.

    Incluye toda la información básica más:
      - description: Descripción enriquecida del producto
      - technical_specs: Especificaciones técnicas (dimensiones, potencia, materiales, etc.)
      - usage_instructions: Instrucciones de uso (pasos, consejos, advertencias)

    Args:
        sku: SKU canónico del producto (formato XXX_####_YYY).
        product_id: ID interno del producto (alternativa al SKU).
        user_role: Rol declarado del usuario que solicita. Debe ser 'admin' o 'colaborador'.

    Returns:
        Diccionario con estructura extendida incluyendo campos de enriquecimiento.

    Raises:
        PermissionError: Si el rol no está autorizado para información "full".
        httpx.HTTPStatusError / httpx.RequestError: Errores de transporte a la API.
        KeyError: Campos faltantes en la respuesta de la API.
    """
    if user_role not in _FULL_INFO_ROLES:
        raise PermissionError("Permission denied: rol insuficiente para información completa.")
    
    if not sku and not product_id:
        raise ValueError("Se requiere 'sku' o 'product_id'.")
    
    # Cache lookup
    cache_key = f"product_full_info:{product_id or sku}"
    cached = _cache_get(cache_key)
    if cached:
        logger.debug("Cache HIT para full info %s", cache_key)
        return cached

    base_url = _get_api_base_url()
    headers = _get_internal_auth_headers()
    
    # Construir URL con el parámetro disponible
    if product_id:
        url = f"{base_url}/variants/lookup?product_id={product_id}"
    else:
        url = f"{base_url}/variants/lookup?sku={sku}"
    
    async with httpx.AsyncClient(timeout=5.0) as client:
        try:
            logger.debug("Consultando URL=%s (full info)", url)
            resp = await client.get(url, headers=headers)
            resp.raise_for_status()
            data = resp.json()
            
            # Construir respuesta completa
            result = {
                "product_id": data.get("product_id"),
                "sku": data.get("sku"),
                "name": data.get("name") or data.get("title") or "(sin nombre)",
                "sale_price": data.get("sale_price"),
                "stock": data.get("stock"),
            }
            
            # Incluir descripción enriquecida si existe
            description = data.get("description")
            if description:
                result["description"] = description
            
            # Agregar datos de enriquecimiento solo si tienen contenido
            technical_specs = data.get("technical_specs")
            if technical_specs and isinstance(technical_specs, dict) and technical_specs:
                result["technical_specs"] = technical_specs
            
            usage_instructions = data.get("usage_instructions")
            if usage_instructions and isinstance(usage_instructions, dict) and usage_instructions:
                result["usage_instructions"] = usage_instructions
            
            _cache_put(cache_key, result)
            logger.debug("Cache SET full info %s", cache_key)
            return result
            
        except httpx.TimeoutException as exc:
            logger.warning("Timeout URL=%s: %s", url, exc)
            raise
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code == 404:
                logger.warning("Producto no encontrado: sku=%s product_id=%s", sku, product_id)
                raise KeyError("Producto no encontrado")
            raise
        except httpx.RequestError as exc:
            logger.warning("RequestError URL=%s: %s", url, exc)
            raise


async def find_products_by_name(query: str, user_role: str) -> Dict[str, Any]:
    """Busca productos por nombre (búsqueda parcial) y retorna coincidencias con stock.

    Args:
        query: Texto ingresado por el usuario (nombre parcial o completo).
        user_role: Rol declarado (no se restringe en MVP).

    Returns:
        Dict con clave `items` que es una lista de productos con:
        - product_id: ID interno (usar para get_product_info)
        - name: Nombre estilizado del producto
        - sku: SKU canónico (formato XXX_####_YYY)
        - stock: Cantidad disponible
        - price: Precio de venta

    Notas:
        - Endpoint usado: /catalog/search?q= (endpoint real implementado en catalog.py).
        - Se autentica como servicio interno usando X-Internal-Service-Token.
        - Solo devuelve productos con SKU canónico (ignora SKUs internos del sistema).
    """
    if not query or not isinstance(query, str):
        raise ValueError("Parámetro 'query' requerido (string no vacío).")
    base_url = _get_api_base_url()
    url = f"{base_url}/catalog/search?q={httpx.QueryParams({'q': query})['q']}"  # asegura encoding
    headers = _get_internal_auth_headers()
    async with httpx.AsyncClient(timeout=5.0) as client:
        resp = await client.get(url, headers=headers)
        resp.raise_for_status()
        data = resp.json()
        # Se asume una lista de productos
        items: List[Dict[str, Any]] = []
        if isinstance(data, list):
            source_iter = data
        else:
            source_iter = data.get("items", []) if isinstance(data, dict) else []
        
        for prod in source_iter:
            if not isinstance(prod, dict):
                continue
            
            # Obtener datos del producto
            product_id = prod.get("id")
            name = prod.get("name") or prod.get("title") or "(sin nombre)"
            sku = prod.get("sku")  # SKU canónico (formato XXX_####_YYY)
            stock = prod.get("stock")
            price = prod.get("price") or prod.get("sale_price")
            
            # Solo incluir si tiene SKU canónico (no mostrar SKUs internos)
            # El SKU canónico tiene formato XXX_####_YYY
            if not sku or not product_id:
                continue
            
            items.append({
                "product_id": product_id,
                "name": name,
                "sku": sku,
                "stock": stock,
                "price": price,
            })
        
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
        parameters: Parámetros (deben incluir `user_role` y `sku` o `product_id`).

    Returns:
        Resultado de la herramienta como dict.

    Raises:
        KeyError: Si el tool no existe.
        ValueError: Validaciones internas de parámetros.
    """
    # DEBUG: Log de entrada
    logger.info("invoke_tool: Tool Call Inputs: %s -> %s", tool_name, parameters)
    
    if tool_name not in TOOLS_REGISTRY:
        raise KeyError(f"Tool desconocida: {tool_name}")
    if not isinstance(parameters, dict):
        raise ValueError("parameters debe ser un objeto JSON (dict).")
    user_role = parameters.get("user_role")
    if not user_role or not isinstance(user_role, str):
        raise ValueError("Parámetro 'user_role' requerido (string).")

    func = TOOLS_REGISTRY[tool_name]
    result: Dict[str, Any] = {}
    
    if tool_name == "find_products_by_name":
        query = parameters.get("query")
        if not query or not isinstance(query, str):
            raise ValueError("Parámetro 'query' requerido (string).")
        logger.info("invoke_tool: Ejecutando %s con query='%s' role='%s'", tool_name, query, user_role)
        result = await func(query=query, user_role=user_role)  # type: ignore[arg-type]
    else:
        # Tools de producto: aceptan sku o product_id
        sku = parameters.get("sku")
        product_id = parameters.get("product_id")
        
        # Convertir product_id a int si viene como string
        if product_id and isinstance(product_id, str) and product_id.isdigit():
            product_id = int(product_id)
        
        if not sku and not product_id:
            raise ValueError("Se requiere 'sku' o 'product_id'.")
        
        logger.info("invoke_tool: Ejecutando %s con sku='%s' product_id=%s role='%s'", tool_name, sku, product_id, user_role)
        result = await func(sku=sku, product_id=product_id, user_role=user_role)  # type: ignore[arg-type]
    
    # DEBUG: Log de salida (truncado si es muy largo)
    result_summary = _summarize_tool_output(result)
    logger.info("invoke_tool: Tool Call Output (%s): %s", tool_name, result_summary)
    
    return result


def _summarize_tool_output(result: Dict[str, Any], max_length: int = 500) -> str:
    """Resume el output de una tool para logging.
    
    Trunca campos largos como 'description' para mantener los logs legibles.
    """
    if not isinstance(result, dict):
        return str(result)[:max_length]
    
    summary = {}
    for key, value in result.items():
        if key == "description" and isinstance(value, str):
            summary[key] = f"({len(value)} chars) {value[:100]}..." if len(value) > 100 else value
        elif key == "items" and isinstance(value, list):
            summary[key] = f"[{len(value)} items]"
        elif isinstance(value, str) and len(value) > 200:
            summary[key] = f"{value[:200]}..."
        else:
            summary[key] = value
    
    return str(summary)[:max_length]
