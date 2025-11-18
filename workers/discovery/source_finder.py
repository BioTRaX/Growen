#!/usr/bin/env python
# NG-HEADER: Nombre de archivo: source_finder.py
# NG-HEADER: Ubicación: workers/discovery/source_finder.py
# NG-HEADER: Descripción: Descubrimiento automático de fuentes de precios usando MCP Web Search
# NG-HEADER: Lineamientos: Ver AGENTS.md

from __future__ import annotations

import os
import logging
import re
from typing import List, Dict, Any, Optional
from urllib.parse import urlparse

import httpx

logger = logging.getLogger(__name__)

# Dominios conocidos de e-commerce argentino y growshops
KNOWN_ECOMMERCE_DOMAINS = [
    # Marketplaces generales
    "mercadolibre.com.ar",
    "mercadolibre.com",
    "mlstatic.com",
    
    # Growshops específicos
    "santaplanta.com",
    "cultivargrowshop.com",
    "growbarato.net",
    "indoorgrow.com.ar",
    "tricomas.com.ar",
    "cannabisargento.com.ar",
    "huertourbano.net",
    
    # Retailers grandes
    "easy.com.ar",
    "sodimac.com.ar",
    "farmacity.com",
    "simplicityar.com",
    
    # Término genérico en URL
    "growshop",
    "grow-shop",
    "hidroponico",
    "hidroponia",
]

# Palabras clave que indican presencia de precio en snippet
PRICE_INDICATORS = [
    "$",
    "ars",
    "precio",
    "comprar",
    "oferta",
    "venta",
    "envío",
    "stock",
    "disponible",
]

# Patrones de URL a excluir (imágenes, estáticas, etc.)
URL_EXCLUDE_PATTERNS = [
    r"\.jpg$",
    r"\.png$",
    r"\.gif$",
    r"\.webp$",
    r"\.pdf$",
    r"\.css$",
    r"\.js$",
    r"/static/",
    r"/assets/",
    r"/cdn-cgi/",
]


def build_search_query(product_name: str, category: str = "", sku: str = "") -> str:
    """
    Construye query de búsqueda contextual para encontrar fuentes de precio.
    
    Args:
        product_name: Nombre del producto
        category: Categoría del producto (opcional)
        sku: SKU del producto (opcional, útil para productos específicos)
        
    Returns:
        Query optimizada para búsqueda de precios
    """
    parts = []
    
    # Agregar nombre del producto (obligatorio)
    if product_name:
        parts.append(product_name)
    
    # Agregar SKU si es informativo (no interno tipo "PROD-001")
    if sku and not sku.startswith(("PROD-", "NG-", "SKU-")):
        parts.append(sku)
    
    # Agregar categoría si aporta contexto
    if category and category.lower() not in ["general", "varios", "sin categoría"]:
        parts.append(category)
    
    # Agregar palabras clave para búsqueda de precios
    parts.append("precio")
    parts.append("comprar")
    
    return " ".join(parts).strip()


def is_valid_ecommerce_url(url: str) -> bool:
    """
    Valida si la URL pertenece a un sitio de e-commerce conocido.
    
    Args:
        url: URL a validar
        
    Returns:
        True si es un dominio de e-commerce válido
    """
    try:
        parsed = urlparse(url)
        domain = parsed.netloc.lower()
        
        # Verificar si contiene alguno de los dominios conocidos
        for known_domain in KNOWN_ECOMMERCE_DOMAINS:
            if known_domain in domain:
                return True
        
        return False
    except Exception:
        return False


def has_price_indicators(snippet: str) -> bool:
    """
    Verifica si el snippet contiene indicadores de precio.
    
    Args:
        snippet: Texto del snippet
        
    Returns:
        True si contiene indicadores de precio
    """
    if not snippet:
        return False
    
    snippet_lower = snippet.lower()
    
    # Verificar palabras clave
    for indicator in PRICE_INDICATORS:
        if indicator in snippet_lower:
            return True
    
    # Verificar patrón de precio ($1234 o $1,234.00)
    if re.search(r'\$\s*\d+[\d,\.]*', snippet):
        return True
    
    return False


def is_excluded_url(url: str) -> bool:
    """
    Verifica si la URL debe ser excluida (imágenes, estáticos, etc.).
    
    Args:
        url: URL a verificar
        
    Returns:
        True si debe ser excluida
    """
    url_lower = url.lower()
    
    for pattern in URL_EXCLUDE_PATTERNS:
        if re.search(pattern, url_lower):
            return True
    
    return False


def extract_valid_urls(results: List[Dict[str, Any]]) -> List[Dict[str, str]]:
    """
    Filtra y extrae URLs válidas de resultados de búsqueda.
    
    Args:
        results: Lista de resultados del MCP Web Search (items)
        
    Returns:
        Lista de diccionarios con url, title y snippet de URLs válidas
    """
    valid_sources = []
    seen_urls = set()
    
    for result in results:
        url = result.get("url", "")
        title = result.get("title", "")
        snippet = result.get("snippet", "")
        
        # Validaciones básicas
        if not url or not title:
            continue
        
        # Evitar duplicados
        if url in seen_urls:
            continue
        
        # Filtrar URLs excluidas
        if is_excluded_url(url):
            continue
        
        # Verificar que sea un sitio de e-commerce conocido
        if not is_valid_ecommerce_url(url):
            continue
        
        # Priorizar resultados con indicadores de precio
        if not has_price_indicators(snippet):
            # Solo incluir sin indicadores si es dominio MUY confiable
            domain = urlparse(url).netloc.lower()
            high_priority_domains = ["mercadolibre", "santaplanta"]
            if not any(d in domain for d in high_priority_domains):
                continue
        
        seen_urls.add(url)
        valid_sources.append({
            "url": url,
            "title": title,
            "snippet": snippet or "",
        })
    
    return valid_sources


async def call_mcp_web_search(
    query: str,
    max_results: int = 15,
    user_role: str = "admin"
) -> Dict[str, Any]:
    """
    Llama al servicio MCP Web Search con la query especificada.
    
    Args:
        query: Query de búsqueda
        max_results: Máximo número de resultados a solicitar
        user_role: Rol del usuario (para validación MCP)
        
    Returns:
        Respuesta del MCP con items o error
    """
    mcp_url = os.getenv("MCP_WEB_SEARCH_URL", "http://mcp_web_search:8002/invoke_tool")
    
    payload = {
        "tool_name": "search_web",
        "parameters": {
            "query": query,
            "user_role": user_role,
            "max_results": max_results,
        }
    }
    
    try:
        logger.info(f"[discovery] Llamando MCP Web Search: query='{query}' max_results={max_results}")
        
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(mcp_url, json=payload)
            
            if resp.status_code != 200:
                logger.error(
                    f"[discovery] MCP Web Search respondió status={resp.status_code} "
                    f"detail={resp.text[:200]}"
                )
                return {"error": "mcp_call_failed", "status": resp.status_code}
            
            result = resp.json().get("result", {})
            
            items = result.get("items", [])
            logger.info(f"[discovery] MCP Web Search retornó {len(items)} resultados")
            
            return result
            
    except httpx.RequestError as e:
        logger.error(f"[discovery] Error de red llamando MCP Web Search: {e}")
        return {"error": "network_failure"}
    except Exception as e:
        logger.exception(f"[discovery] Error inesperado llamando MCP Web Search: {e}")
        return {"error": "internal_failure"}


async def discover_price_sources(
    product_name: str,
    category: str = "",
    sku: str = "",
    existing_urls: Optional[List[str]] = None,
    max_results: int = 15,
    user_role: str = "admin"
) -> Dict[str, Any]:
    """
    Descubre automáticamente nuevas fuentes de precios para un producto.
    
    Construye una query contextual, consulta el MCP Web Search y filtra
    resultados para retornar URLs válidas de e-commerce.
    
    Args:
        product_name: Nombre del producto
        category: Categoría del producto (opcional)
        sku: SKU del producto (opcional)
        existing_urls: URLs ya existentes para evitar duplicados (opcional)
        max_results: Máximo de resultados a solicitar al MCP
        user_role: Rol del usuario para validación MCP
        
    Returns:
        Dict con:
        - success: bool
        - query: str (query usada)
        - total_results: int (resultados del MCP)
        - valid_sources: int (fuentes válidas encontradas)
        - sources: List[Dict] (URLs con title y snippet)
        - error: str (si hubo error)
    """
    # 1. Construir query de búsqueda
    query = build_search_query(product_name, category, sku)
    
    logger.info(
        f"[discovery] Iniciando descubrimiento para producto='{product_name}' "
        f"category='{category}' query='{query}'"
    )
    
    # 2. Llamar MCP Web Search
    mcp_result = await call_mcp_web_search(query, max_results, user_role)
    
    # Verificar errores del MCP
    if "error" in mcp_result:
        return {
            "success": False,
            "query": query,
            "total_results": 0,
            "valid_sources": 0,
            "sources": [],
            "error": mcp_result["error"],
        }
    
    # 3. Extraer y filtrar resultados
    items = mcp_result.get("items", [])
    valid_sources = extract_valid_urls(items)
    
    # 4. Filtrar URLs ya existentes
    if existing_urls:
        existing_set = set(existing_urls)
        valid_sources = [
            s for s in valid_sources
            if s["url"] not in existing_set
        ]
        logger.info(
            f"[discovery] Filtradas {len(items) - len(valid_sources)} URLs duplicadas"
        )
    
    # 5. Limitar resultados finales
    max_return = 10
    if len(valid_sources) > max_return:
        logger.info(
            f"[discovery] Limitando resultados de {len(valid_sources)} a {max_return}"
        )
        valid_sources = valid_sources[:max_return]
    
    logger.info(
        f"[discovery] Descubrimiento completado: {len(valid_sources)} fuentes válidas "
        f"de {len(items)} resultados totales"
    )
    
    return {
        "success": True,
        "query": query,
        "total_results": len(items),
        "valid_sources": len(valid_sources),
        "sources": valid_sources,
    }
