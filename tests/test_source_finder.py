#!/usr/bin/env python
# NG-HEADER: Nombre de archivo: test_source_finder.py
# NG-HEADER: Ubicación: tests/test_source_finder.py
# NG-HEADER: Descripción: Tests para el descubrimiento automático de fuentes
# NG-HEADER: Lineamientos: Ver AGENTS.md

# Tests unitarios puros (sin dependencias de DB)

from workers.discovery.source_finder import (
    build_search_query,
    is_valid_ecommerce_url,
    has_price_indicators,
    is_excluded_url,
    extract_valid_urls,
)


class TestBuildSearchQuery:
    """Tests para construcción de query de búsqueda"""
    
    def test_query_with_name_only(self):
        query = build_search_query("Sustrato de coco")
        assert "Sustrato de coco" in query
        assert "precio" in query
        assert "comprar" in query
    
    def test_query_with_category(self):
        query = build_search_query("Sustrato de coco", category="Sustratos")
        assert "Sustrato de coco" in query
        assert "Sustratos" in query
        assert "precio" in query
    
    def test_query_with_sku(self):
        query = build_search_query("Sustrato de coco", sku="COCO-20L")
        assert "Sustrato de coco" in query
        assert "COCO-20L" in query
    
    def test_query_skips_internal_sku(self):
        query = build_search_query("Sustrato de coco", sku="PROD-001")
        assert "PROD-001" not in query
        assert "NG-" not in query
    
    def test_query_skips_generic_category(self):
        query = build_search_query("Producto", category="General")
        assert "General" not in query


class TestIsValidEcommerceUrl:
    """Tests para validación de URLs de e-commerce"""
    
    def test_mercadolibre_valid(self):
        assert is_valid_ecommerce_url("https://articulo.mercadolibre.com.ar/MLA-123456789")
    
    def test_santaplanta_valid(self):
        assert is_valid_ecommerce_url("https://www.santaplanta.com/shop/products/sustrato")
    
    def test_cultivar_valid(self):
        assert is_valid_ecommerce_url("https://cultivargrowshop.com/producto/luz-led")
    
    def test_generic_growshop_valid(self):
        assert is_valid_ecommerce_url("https://migrowshop.com.ar/producto")
    
    def test_invalid_domain(self):
        assert not is_valid_ecommerce_url("https://www.google.com")
        assert not is_valid_ecommerce_url("https://www.wikipedia.org")
    
    def test_invalid_url_format(self):
        assert not is_valid_ecommerce_url("not-a-url")


class TestHasPriceIndicators:
    """Tests para detección de indicadores de precio"""
    
    def test_snippet_with_dollar_sign(self):
        assert has_price_indicators("Sustrato de coco 20L $2500")
    
    def test_snippet_with_precio_word(self):
        assert has_price_indicators("Mejor precio del mercado")
    
    def test_snippet_with_comprar_word(self):
        assert has_price_indicators("Comprar online con envío gratis")
    
    def test_snippet_with_ars(self):
        assert has_price_indicators("Disponible por ARS 2500")
    
    def test_snippet_with_formatted_price(self):
        assert has_price_indicators("Oferta $1,250.00")
    
    def test_snippet_without_indicators(self):
        assert not has_price_indicators("Información sobre sustratos para cultivo")
    
    def test_empty_snippet(self):
        assert not has_price_indicators("")


class TestIsExcludedUrl:
    """Tests para exclusión de URLs no deseadas"""
    
    def test_image_extensions_excluded(self):
        assert is_excluded_url("https://example.com/image.jpg")
        assert is_excluded_url("https://example.com/photo.png")
        assert is_excluded_url("https://example.com/banner.gif")
        assert is_excluded_url("https://example.com/thumbnail.webp")
    
    def test_static_paths_excluded(self):
        assert is_excluded_url("https://example.com/static/css/style.css")
        assert is_excluded_url("https://example.com/assets/js/main.js")
    
    def test_valid_product_url(self):
        assert not is_excluded_url("https://example.com/productos/sustrato-coco")


class TestExtractValidUrls:
    """Tests para extracción de URLs válidas"""
    
    def test_extract_valid_mercadolibre(self):
        results = [
            {
                "url": "https://articulo.mercadolibre.com.ar/MLA-123",
                "title": "Sustrato de Coco 20L",
                "snippet": "Precio: $2500 - Envío gratis"
            }
        ]
        valid = extract_valid_urls(results)
        assert len(valid) == 1
        assert valid[0]["url"] == "https://articulo.mercadolibre.com.ar/MLA-123"
    
    def test_filter_invalid_domains(self):
        results = [
            {
                "url": "https://www.google.com/search",
                "title": "Search Results",
                "snippet": "Precio $123"
            }
        ]
        valid = extract_valid_urls(results)
        assert len(valid) == 0
    
    def test_filter_no_price_indicators(self):
        results = [
            {
                "url": "https://cultivargrowshop.com/blog/guia-sustratos",
                "title": "Guía de Sustratos",
                "snippet": "Aprende sobre diferentes tipos de sustratos"
            }
        ]
        valid = extract_valid_urls(results)
        assert len(valid) == 0
    
    def test_filter_duplicates(self):
        results = [
            {
                "url": "https://santaplanta.com/producto",
                "title": "Producto 1",
                "snippet": "Precio $100"
            },
            {
                "url": "https://santaplanta.com/producto",
                "title": "Producto 1 (duplicado)",
                "snippet": "Precio $100"
            }
        ]
        valid = extract_valid_urls(results)
        assert len(valid) == 1
    
    def test_filter_excluded_extensions(self):
        results = [
            {
                "url": "https://santaplanta.com/image.jpg",
                "title": "Product Image",
                "snippet": "Precio $100"
            }
        ]
        valid = extract_valid_urls(results)
        assert len(valid) == 0
    
    def test_allow_high_priority_without_price(self):
        """Dominios de alta prioridad se incluyen aunque no tengan indicadores de precio"""
        results = [
            {
                "url": "https://articulo.mercadolibre.com.ar/MLA-123",
                "title": "Sustrato de Coco",
                "snippet": "Envío gratis a todo el país"
            }
        ]
        valid = extract_valid_urls(results)
        assert len(valid) == 1
