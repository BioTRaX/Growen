import os
import uuid
import asyncio
from fastapi.testclient import TestClient

os.environ.setdefault('DB_URL', 'sqlite+aiosqlite:///:memory:')

from services.api import app
from services.auth import SessionData, current_session, require_csrf
from db.session import SessionLocal
from db.models import Product, SupplierProduct
from sqlalchemy import select

client = TestClient(app)
app.dependency_overrides[current_session] = lambda: SessionData(None, None, 'admin')
app.dependency_overrides[require_csrf] = lambda: None

resp = client.post('/suppliers', json={'slug': 'sup-inspect', 'name': 'Proveedor Inspect'})
data = resp.json()
supplier_id = data['id'] if isinstance(data, dict) and 'id' in data else client.get('/suppliers').json()[-1]['id']
unique_ok = 'KIT-R-1-' + uuid.uuid4().hex[:4]
unique_out = 'KIT-R-2-' + uuid.uuid4().hex[:4]
client.post('/catalog/products', json={
    'title': 'Kit Ranking Plus',
    'initial_stock': 5,
    'supplier_id': supplier_id,
    'supplier_sku': unique_ok,
    'sku': unique_ok,
    'purchase_price': 120.0,
    'sale_price': 120.0,
})
client.post('/catalog/products', json={
    'title': 'Kit Ranking Basic',
    'initial_stock': 0,
    'supplier_id': supplier_id,
    'supplier_sku': unique_out,
    'sku': unique_out,
    'purchase_price': 95.0,
    'sale_price': 95.0,
})

async def main():
    async with SessionLocal() as session:
        products = (await session.execute(select(Product.id, Product.title, Product.stock))).all()
        supplier_products = (
            await session.execute(
                select(
                    SupplierProduct.id,
                    SupplierProduct.title,
                    SupplierProduct.internal_product_id,
                    SupplierProduct.current_sale_price,
                    SupplierProduct.supplier_product_id,
                )
            )
        ).all()
        print('Products:', products)
        print('SupplierProducts:', supplier_products)

asyncio.run(main())
