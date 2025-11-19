#!/usr/bin/env python
# NG-HEADER: Nombre de archivo: __init__.py
# NG-HEADER: Ubicación: workers/scraping/__init__.py
# NG-HEADER: Descripción: Módulo de scraping de precios desde fuentes externas
# NG-HEADER: Lineamientos: Ver AGENTS.md

"""
Módulo de scraping para obtener precios desde fuentes externas.

Este módulo proporciona funciones para extraer precios de:
- Páginas estáticas (HTML directo) usando requests + BeautifulSoup
- Páginas dinámicas (JavaScript) usando Playwright
- Normalización de precios con detección de moneda
"""

from workers.scraping.static_scraper import scrape_static_price
from workers.scraping.dynamic_scraper import scrape_dynamic_price, scrape_dynamic_price_sync
from workers.scraping.price_normalizer import normalize_price

__all__ = [
    "scrape_static_price",
    "scrape_dynamic_price",
    "scrape_dynamic_price_sync",
    "normalize_price",
]
