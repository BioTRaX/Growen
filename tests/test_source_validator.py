#!/usr/bin/env python
# NG-HEADER: Nombre de archivo: test_source_validator.py
# NG-HEADER: Ubicación: tests/test_source_validator.py
# NG-HEADER: Descripción: Tests para validación de fuentes sugeridas
# NG-HEADER: Lineamientos: Ver AGENTS.md

"""
Tests para workers/discovery/source_validator.py

Valida:
- Detección de dominios de alta confianza
- Verificación de disponibilidad de URLs
- Detección de precio en HTML
- Validación completa de fuentes
"""

import pytest
import httpx
from workers.discovery.source_validator import (
    get_domain,
    is_high_confidence_domain,
    detect_price_in_html,
    validate_source,
    HIGH_CONFIDENCE_DOMAINS,
)


class TestGetDomain:
    """Tests para extracción de dominio"""
    
    def test_domain_with_www(self):
        url = "https://www.mercadolibre.com.ar/producto"
        assert get_domain(url) == "mercadolibre.com.ar"
    
    def test_domain_without_www(self):
        url = "https://santaplanta.com/producto"
        assert get_domain(url) == "santaplanta.com"
    
    def test_domain_with_subdomain(self):
        url = "https://shop.cultivargrowshop.com/producto"
        assert get_domain(url) == "shop.cultivargrowshop.com"
    
    def test_domain_with_port(self):
        url = "http://localhost:8000/producto"
        assert get_domain(url) == "localhost:8000"


class TestIsHighConfidenceDomain:
    """Tests para detección de dominios confiables"""
    
    def test_mercadolibre_ar_is_high_confidence(self):
        url = "https://www.mercadolibre.com.ar/producto"
        assert is_high_confidence_domain(url) is True
    
    def test_mercadolibre_com_is_high_confidence(self):
        url = "https://articulo.mercadolibre.com/MLA-123456"
        assert is_high_confidence_domain(url) is True
    
    def test_santaplanta_is_high_confidence(self):
        url = "https://www.santaplanta.com/producto"
        assert is_high_confidence_domain(url) is True
    
    def test_cultivar_is_high_confidence(self):
        url = "https://cultivargrowshop.com/producto"
        assert is_high_confidence_domain(url) is True
    
    def test_unknown_domain_is_not_high_confidence(self):
        url = "https://example.com/producto"
        assert is_high_confidence_domain(url) is False
    
    def test_low_confidence_growshop(self):
        # El dominio debe estar en HIGH_CONFIDENCE_DOMAINS
        # "growshop" genérico NO está en la lista de alta confianza
        url = "https://randomgrowshop.com/producto"
        assert is_high_confidence_domain(url) is False


class TestDetectPriceInHtml:
    """Tests para detección de precio en HTML (usando mocks)"""
    
    @pytest.mark.asyncio
    async def test_detect_price_with_dollar_sign(self, respx_mock):
        """Precio con símbolo $"""
        url = "https://example.com/producto"
        html = "<html><body><span>Precio: $1250</span></body></html>"
        
        respx_mock.get(url).mock(return_value=httpx.Response(200, text=html))
        
        from workers.discovery.source_validator import detect_price_in_html
        result = await detect_price_in_html(url)
        
        assert result is True
    
    @pytest.mark.asyncio
    async def test_detect_price_with_formatted_price(self, respx_mock):
        """Precio formateado con separadores"""
        url = "https://example.com/producto"
        html = '<html><body><span class="price">$1.250,00</span></body></html>'
        
        respx_mock.get(url).mock(return_value=httpx.Response(200, text=html))
        
        from workers.discovery.source_validator import detect_price_in_html
        result = await detect_price_in_html(url)
        
        assert result is True
    
    @pytest.mark.asyncio
    async def test_detect_price_with_precio_word(self, respx_mock):
        """Precio con palabra 'precio'"""
        url = "https://example.com/producto"
        html = "<html><body><div>Precio: 1250 ARS</div></body></html>"
        
        respx_mock.get(url).mock(return_value=httpx.Response(200, text=html))
        
        from workers.discovery.source_validator import detect_price_in_html
        result = await detect_price_in_html(url)
        
        assert result is True
    
    @pytest.mark.asyncio
    async def test_detect_price_in_meta_tag(self, respx_mock):
        """Precio en meta tag schema.org"""
        url = "https://example.com/producto"
        html = '''
        <html>
            <head>
                <meta property="product:price:amount" content="1250.00" />
            </head>
            <body>Producto test</body>
        </html>
        '''
        
        respx_mock.get(url).mock(return_value=httpx.Response(200, text=html))
        
        from workers.discovery.source_validator import detect_price_in_html
        result = await detect_price_in_html(url)
        
        assert result is True
    
    @pytest.mark.asyncio
    async def test_detect_price_in_class_element(self, respx_mock):
        """Precio en elemento con clase 'price'"""
        url = "https://example.com/producto"
        html = '<html><body><span class="product-price">2.500</span></body></html>'
        
        respx_mock.get(url).mock(return_value=httpx.Response(200, text=html))
        
        from workers.discovery.source_validator import detect_price_in_html
        result = await detect_price_in_html(url)
        
        assert result is True
    
    @pytest.mark.asyncio
    async def test_no_price_detected(self, respx_mock):
        """HTML sin precio"""
        url = "https://example.com/producto"
        html = "<html><body><h1>Producto sin precio</h1></body></html>"
        
        respx_mock.get(url).mock(return_value=httpx.Response(200, text=html))
        
        from workers.discovery.source_validator import detect_price_in_html
        result = await detect_price_in_html(url)
        
        assert result is False
    
    @pytest.mark.asyncio
    async def test_network_error_handling(self, respx_mock):
        """Manejo de error de red"""
        url = "https://example.com/producto"
        
        respx_mock.get(url).mock(side_effect=httpx.TimeoutException("Timeout"))
        
        from workers.discovery.source_validator import detect_price_in_html, NetworkError
        
        with pytest.raises(NetworkError):
            await detect_price_in_html(url)


class TestValidateSource:
    """Tests para validación completa de fuentes"""
    
    @pytest.mark.asyncio
    async def test_high_confidence_domain_approved_immediately(self, respx_mock):
        """Dominios de alta confianza se aprueban sin validar precio"""
        url = "https://www.mercadolibre.com.ar/producto"
        
        # Mock HEAD request (disponibilidad)
        respx_mock.head(url).mock(return_value=httpx.Response(200))
        
        from workers.discovery.source_validator import validate_source
        is_valid, reason = await validate_source(url)
        
        assert is_valid is True
        assert reason == "high_confidence"
    
    @pytest.mark.asyncio
    async def test_valid_source_with_price(self, respx_mock):
        """Fuente válida con precio detectado"""
        url = "https://example.com/producto"
        html = "<html><body><span>Precio: $1250</span></body></html>"
        
        # Mock HEAD (disponibilidad)
        respx_mock.head(url).mock(return_value=httpx.Response(200))
        # Mock GET (contenido)
        respx_mock.get(url).mock(return_value=httpx.Response(200, text=html))
        
        from workers.discovery.source_validator import validate_source
        is_valid, reason = await validate_source(url)
        
        assert is_valid is True
        assert reason == "price_found"
    
    @pytest.mark.asyncio
    async def test_invalid_source_no_price(self, respx_mock):
        """Fuente inválida sin precio"""
        url = "https://example.com/producto"
        html = "<html><body><h1>Producto</h1></body></html>"
        
        respx_mock.head(url).mock(return_value=httpx.Response(200))
        respx_mock.get(url).mock(return_value=httpx.Response(200, text=html))
        
        from workers.discovery.source_validator import validate_source
        is_valid, reason = await validate_source(url)
        
        assert is_valid is False
        assert reason == "price_not_found"
    
    @pytest.mark.asyncio
    async def test_invalid_source_not_available(self, respx_mock):
        """Fuente inválida (404)"""
        url = "https://example.com/producto"
        
        respx_mock.head(url).mock(return_value=httpx.Response(404))
        
        from workers.discovery.source_validator import validate_source
        is_valid, reason = await validate_source(url)
        
        assert is_valid is False
        assert reason == "url_not_available"
    
    @pytest.mark.asyncio
    async def test_quick_validation_skips_price_check(self, respx_mock):
        """Validación rápida solo verifica disponibilidad"""
        url = "https://example.com/producto"
        
        respx_mock.head(url).mock(return_value=httpx.Response(200))
        # No debería hacer GET si quick=True
        
        from workers.discovery.source_validator import validate_source
        is_valid, reason = await validate_source(url, quick=True)
        
        assert is_valid is True
        assert reason == "quick_check_passed"


# Fixture para respx (HTTP mocking)
@pytest.fixture
def respx_mock():
    """Fixture para mockear requests HTTP con respx"""
    import respx
    import httpx
    
    with respx.mock:
        yield respx


# Note: Tests que requieren httpx real están marcados con @pytest.mark.integration
# y deben ejecutarse con: pytest -m integration
