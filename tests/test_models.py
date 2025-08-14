from decimal import Decimal

from agent_core.models import Product, Variant, Image, Inventory


def test_create_product_with_relations(session):
    product = Product(title="Prod", slug="prod")
    variant1 = Variant(sku="SKU1", price=Decimal("10.00"), product=product)
    variant2 = Variant(sku="SKU2", price=Decimal("20.00"), product=product)
    Image(url="http://example.com/img.jpg", product=product)
    Inventory(variant=variant1, stock_qty=5)

    session.add(product)
    session.commit()

    assert session.query(Product).count() == 1
    assert session.query(Variant).count() == 2
    assert session.query(Image).count() == 1
    assert session.query(Inventory).filter_by(variant_id=variant1.id).one().stock_qty == 5
