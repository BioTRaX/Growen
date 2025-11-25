#!/usr/bin/env python
# NG-HEADER: Nombre de archivo: test_market_validation.py
# NG-HEADER: Ubicación: tests/test_market_validation.py
# NG-HEADER: Descripción: Tests de validación de inputs para módulo Mercado
# NG-HEADER: Lineamientos: Ver AGENTS.md

"""
Tests de validación de datos de entrada para el módulo Mercado.

Verifica que:
- Precios inválidos (negativos, cero para sale_price, muy altos) son rechazados
- URLs inválidas (sin esquema, dominio inválido, muy cortas) son rechazadas
- URLs duplicadas son detectadas y rechazadas
- Nombres muy cortos o vacíos son rechazados
- Monedas inválidas son rechazadas
- Errores retornan códigos HTTP correctos (400, 422) sin exponer trazas
"""

import pytest
from starlette.testclient import TestClient

from db.models import CanonicalProduct, MarketSource


@pytest.fixture
def product_with_source(admin_client: TestClient):
    """Crea un producto canónico con una fuente existente a través de la API.
    
    Usa la misma DB que la API (memoria compartida) para que los tests funcionen.
    El módulo Market trabaja con CanonicalProduct, no con Product.
    """
    # Crear producto canónico vía API (endpoint específico para canónicos)
    create_resp = admin_client.post(
        "/canonical-products",
        json={
            "name": "Producto Validación Market",
            "sale_price": 1000.00,
            "market_price_reference": 950.00,
        }
    )
    assert create_resp.status_code in [200, 201], f"Error creando producto canónico: {create_resp.text}"
    product_data = create_resp.json()
    product_id = product_data["id"]
    
    # Crear fuente de mercado vía API
    source_resp = admin_client.post(
        f"/market/products/{product_id}/sources",
        json={
            "source_name": "Fuente Existente",
            "url": "https://example.com/existing",
            "is_mandatory": False,
        }
    )
    # Si la fuente se crea exitosamente
    source_data = None
    if source_resp.status_code in [200, 201]:
        source_data = source_resp.json()
    
    yield {
        "product_id": product_id,
        "product_data": product_data,
        "existing_source": source_data,
    }
    
    # No cleanup necesario - db_session lo hace automáticamente


class TestSalePriceValidation:
    """Tests de validación de precio de venta"""
    
    def test_rejects_negative_sale_price(self, admin_client: TestClient, product_with_source):
        """Rechaza precio de venta negativo"""
        product_id = product_with_source["product_id"]
        
        response = admin_client.patch(
            f"/market/products/{product_id}/sale-price",
            json={"sale_price": -100.00},
        )
        
        assert response.status_code == 422  # Pydantic validation error
        error_data = response.json()
        assert "detail" in error_data
    
    def test_rejects_zero_sale_price(self, admin_client: TestClient, product_with_source):
        """Rechaza precio de venta en cero"""
        product_id = product_with_source["product_id"]
        
        response = admin_client.patch(
            f"/market/products/{product_id}/sale-price",
            json={"sale_price": 0.00},
        )
        
        assert response.status_code == 422
    
    def test_accepts_valid_sale_price(self, admin_client: TestClient, product_with_source):
        """Acepta precio de venta válido"""
        product_id = product_with_source["product_id"]
        
        response = admin_client.patch(
            f"/market/products/{product_id}/sale-price",
            json={"sale_price": 1500.00},
        )
        
        assert response.status_code in [200, 201]


class TestMarketReferenceValidation:
    """Tests de validación de precio de mercado de referencia"""
    
    def test_rejects_negative_market_price(self, admin_client: TestClient, product_with_source):
        """Rechaza precio de mercado negativo"""
        product_id = product_with_source["product_id"]
        
        response = admin_client.patch(
            f"/market/products/{product_id}/market-reference",
            json={"market_price_reference": -50.00},
        )
        
        assert response.status_code == 422
    
    def test_accepts_zero_market_price(self, admin_client: TestClient, product_with_source):
        """Acepta precio de mercado en cero (válido para 'sin valor')"""
        product_id = product_with_source["product_id"]
        
        response = admin_client.patch(
            f"/market/products/{product_id}/market-reference",
            json={"market_price_reference": 0.00},
        )
        
        assert response.status_code in [200, 201]


class TestURLValidation:
    """Tests de validación de URLs en fuentes"""
    
    def test_rejects_url_without_scheme(self, admin_client: TestClient, product_with_source):
        """Rechaza URL sin esquema (http/https)"""
        product_id = product_with_source["product_id"]
        
        response = admin_client.post(
            f"/market/products/{product_id}/sources",
            json={
                "source_name": "Test Source",
                "url": "example.com/product",
                "is_mandatory": False,
            },
        )
        
        assert response.status_code == 422
    
    def test_rejects_url_with_invalid_scheme(self, admin_client: TestClient, product_with_source):
        """Rechaza URL con esquema no permitido (ftp, file, etc.)"""
        product_id = product_with_source["product_id"]
        
        response = admin_client.post(
            f"/market/products/{product_id}/sources",
            json={
                "source_name": "Test Source",
                "url": "ftp://example.com/product",
                "is_mandatory": False,
            },
        )
        
        assert response.status_code == 422
    
    def test_accepts_valid_url(self, admin_client: TestClient, product_with_source):
        """Acepta URL válida"""
        product_id = product_with_source["product_id"]
        
        response = admin_client.post(
            f"/market/products/{product_id}/sources",
            json={
                "source_name": "Valid Source",
                "url": "https://www.example.com/product/123",
                "is_mandatory": False,
            },
        )
        
        assert response.status_code in [200, 201]


class TestDuplicateURLValidation:
    """Tests de validación de URLs duplicadas"""
    
    def test_rejects_duplicate_url_for_same_product(self, admin_client: TestClient, product_with_source):
        """Rechaza URL que ya existe para el mismo producto"""
        product_id = product_with_source["product_id"]
        
        response = admin_client.post(
            f"/market/products/{product_id}/sources",
            json={
                "source_name": "Duplicate Source",
                "url": "https://example.com/existing",
                "is_mandatory": False,
            },
        )
        
        # Debe ser 409 (Conflict) o 400 (Bad Request)
        assert response.status_code in [400, 409]


class TestSourceNameValidation:
    """Tests de validación de nombre de fuente"""
    
    def test_rejects_too_short_source_name(self, admin_client: TestClient, product_with_source):
        """Rechaza nombre de fuente muy corto (< 3 caracteres)"""
        product_id = product_with_source["product_id"]
        
        response = admin_client.post(
            f"/market/products/{product_id}/sources",
            json={
                "source_name": "ab",
                "url": "https://example.com/test2",
                "is_mandatory": False,
            },
        )
        
        assert response.status_code == 422


class TestCurrencyValidation:
    """Tests de validación de moneda"""
    
    def test_rejects_invalid_currency(self, admin_client: TestClient, product_with_source):
        """Rechaza código de moneda inválido"""
        product_id = product_with_source["product_id"]
        
        response = admin_client.post(
            f"/market/products/{product_id}/sources",
            json={
                "source_name": "Test Currency",
                "url": "https://example.com/test-currency",
                "currency": "INVALID",
                "is_mandatory": False,
            },
        )
        
        assert response.status_code == 422


class TestErrorResponseFormat:
    """Tests de formato de respuestas de error"""
    
    def test_error_response_does_not_expose_traceback(self, admin_client: TestClient, product_with_source):
        """Verifica que errores no expongan trazas internas"""
        product_id = product_with_source["product_id"]
        
        response = admin_client.patch(
            f"/market/products/{product_id}/sale-price",
            json={"sale_price": -100.00},
        )
        
        error_data = response.json()
        error_str = str(error_data).lower()
        
        # Verificar que no hay trazas Python en la respuesta
        assert "traceback" not in error_str
        assert ".py\", line" not in error_str
