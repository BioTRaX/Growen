"""
Tests para las funciones de parsing NPK del módulo cultivator.

Cobertura:
- parse_npk_from_tags: parsing de strings NPK con formatos español/inglés
- filter_products_by_deficiency: filtrado por carencia detectada
- classify_products_by_price_tier: clasificación por rango de precio
"""
import pytest
from services.chat.cultivator import (
    parse_npk_from_tags,
    filter_products_by_deficiency,
    classify_products_by_price_tier,
)


class TestParseNPKFromTags:
    """Tests para parse_npk_from_tags."""
    
    def test_parse_spanish_format_with_commas(self):
        """Tags con formato español (comas como decimal)."""
        tags = ["NPK 10-2,4-6 + Zinc(Zn) 0.09%", "#Organico"]
        result = parse_npk_from_tags(tags)
        assert result is not None
        assert result["N"] == 10.0
        assert result["P"] == 2.4
        assert result["K"] == 6.0
    
    def test_parse_english_format_with_dots(self):
        """Tags con formato inglés (puntos como decimal)."""
        tags = ["NPK 15.5-10.2-20.3"]
        result = parse_npk_from_tags(tags)
        assert result is not None
        assert result["N"] == 15.5
        assert result["P"] == 10.2
        assert result["K"] == 20.3
    
    def test_parse_integer_values(self):
        """Tags con valores enteros."""
        tags = ["NPK 20-20-20"]
        result = parse_npk_from_tags(tags)
        assert result is not None
        assert result["N"] == 20.0
        assert result["P"] == 20.0
        assert result["K"] == 20.0
    
    def test_parse_zeros(self):
        """Tags con valores cero (ej: PK puro)."""
        tags = ["NPK 0-0-20 + Potasio"]
        result = parse_npk_from_tags(tags)
        assert result is not None
        assert result["N"] == 0.0
        assert result["P"] == 0.0
        assert result["K"] == 20.0
    
    def test_no_npk_tag(self):
        """Lista sin tags NPK."""
        tags = ["#Fertilizante", "#Vegetativo", "#Organico"]
        result = parse_npk_from_tags(tags)
        assert result is None
    
    def test_empty_list(self):
        """Lista vacía."""
        result = parse_npk_from_tags([])
        assert result is None
    
    def test_case_insensitive(self):
        """NPK en distintas mayúsculas/minúsculas."""
        tags = ["npk 5-10-15"]
        result = parse_npk_from_tags(tags)
        assert result is not None
        assert result["N"] == 5.0
        assert result["P"] == 10.0
        assert result["K"] == 15.0
    
    def test_npk_with_extra_content(self):
        """NPK seguido de contenido adicional."""
        tags = ["NPK 10-2,4-6 + Zinc(Zn) 0.09%, Molibdeno(Mo) 0.01%, Ácidos húmicos s/muestra humeda---1.3%"]
        result = parse_npk_from_tags(tags)
        assert result is not None
        assert result["N"] == 10.0
        assert result["P"] == 2.4
        assert result["K"] == 6.0


class TestFilterProductsByDeficiency:
    """Tests para filter_products_by_deficiency."""
    
    @pytest.fixture
    def sample_products(self):
        """Productos de ejemplo para tests."""
        return [
            {"title": "Veg High N", "tags": ["NPK 15-5-5", "#Vegetativo"], "stock": 10, "price": 5000},
            {"title": "Bloom PK", "tags": ["NPK 0-10-20", "#Floracion"], "stock": 5, "price": 8000},
            {"title": "Balanced", "tags": ["NPK 10-10-10"], "stock": 0, "price": 6000},
            {"title": "CalMag Plus", "tags": ["#CalMag", "#Calcio", "#Magnesio"], "stock": 15, "price": 4000},
            {"title": "Iron Chelate", "tags": ["#Hierro", "#Quelato"], "stock": 3, "price": 7000},
            {"title": "No NPK Tag", "tags": ["#Organico"], "stock": 20, "price": 3000},
        ]
    
    def test_filter_nitrogen_deficiency(self, sample_products):
        """Filtrar por carencia de nitrógeno."""
        result = filter_products_by_deficiency(sample_products, "carencia de nitrógeno")
        assert len(result) == 1
        assert result[0]["title"] == "Veg High N"
    
    def test_filter_potassium_deficiency(self, sample_products):
        """Filtrar por carencia de potasio."""
        result = filter_products_by_deficiency(sample_products, "carencia de potasio")
        # Bloom PK (NPK 0-10-20) should be first with highest K value
        assert len(result) >= 1
        assert result[0]["title"] == "Bloom PK"

    
    def test_filter_calcium_deficiency(self, sample_products):
        """Filtrar por carencia de calcio."""
        result = filter_products_by_deficiency(sample_products, "carencia de calcio")
        assert len(result) == 1
        assert result[0]["title"] == "CalMag Plus"
    
    def test_filter_iron_deficiency(self, sample_products):
        """Filtrar por carencia de hierro."""
        result = filter_products_by_deficiency(sample_products, "carencia de hierro")
        assert len(result) == 1
        assert result[0]["title"] == "Iron Chelate"
    
    def test_exclude_zero_stock_by_default(self, sample_products):
        """Por defecto excluye productos sin stock."""
        # Balanced tiene NPK 10-10-10 pero stock=0
        result = filter_products_by_deficiency(sample_products, "carencia de nitrógeno", only_with_stock=True)
        for p in result:
            assert p.get("stock", 0) > 0
    
    def test_include_zero_stock_when_requested(self, sample_products):
        """Permite incluir productos sin stock."""
        result = filter_products_by_deficiency(sample_products, "carencia de nitrógeno", only_with_stock=False)
        # Debería incluir Balanced (NPK 10-10-10, 10 >= 10 en N)
        titles = [p["title"] for p in result]
        assert "Veg High N" in titles
        assert "Balanced" in titles


class TestClassifyProductsByPriceTier:
    """Tests para classify_products_by_price_tier."""
    
    def test_classify_three_products(self):
        """Clasifica 3 productos en 3 gamas."""
        products = [
            {"title": "Cheap", "price": 1000},
            {"title": "Medium", "price": 5000},
            {"title": "Premium", "price": 10000},
        ]
        result = classify_products_by_price_tier(products, max_per_tier=1)
        
        assert len(result["low"]) == 1
        assert result["low"][0]["title"] == "Cheap"
        
        assert len(result["medium"]) == 1
        assert result["medium"][0]["title"] == "Medium"
        
        assert len(result["high"]) == 1
        assert result["high"][0]["title"] == "Premium"
    
    def test_single_product_goes_to_medium(self):
        """Un solo producto va a gama media."""
        products = [{"title": "Solo", "price": 5000}]
        result = classify_products_by_price_tier(products, max_per_tier=1)
        
        assert len(result["low"]) == 0
        assert len(result["medium"]) == 1
        assert len(result["high"]) == 0
    
    def test_two_products(self):
        """Dos productos: uno low, uno high."""
        products = [
            {"title": "Cheap", "price": 1000},
            {"title": "Expensive", "price": 10000},
        ]
        result = classify_products_by_price_tier(products, max_per_tier=1)
        
        assert len(result["low"]) == 1
        assert len(result["medium"]) == 0
        assert len(result["high"]) == 1
    
    def test_empty_list(self):
        """Lista vacía."""
        result = classify_products_by_price_tier([], max_per_tier=1)
        assert result == {"low": [], "medium": [], "high": []}
    
    def test_products_without_price(self):
        """Productos sin precio son ignorados."""
        products = [
            {"title": "No Price"},
            {"title": "With Price", "price": 5000},
        ]
        result = classify_products_by_price_tier(products, max_per_tier=1)
        # Solo el producto con precio debe aparecer
        total = len(result["low"]) + len(result["medium"]) + len(result["high"])
        assert total == 1
