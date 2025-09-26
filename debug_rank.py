import os
import uuid
import asyncio
from fastapi.testclient import TestClient

os.environ.setdefault('DB_URL', 'sqlite+aiosqlite:///:memory:')

from services.api import app
from services.auth import SessionData, current_session, require_csrf
from services.chat.price_lookup import extract_product_query, resolve_product_info
from db.session import SessionLocal

client = TestClient(app)
app.dependency_overrides[current_session] = lambda: SessionData(None, None, 'admin')
app.dependency_overrides[require_csrf] = lambda: None

resp = client.post('/suppliers', json={'slug': 'sup-debug-1', 'name': 'Proveedor Debug 1'})
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

query = extract_product_query('precio kit ranking')
print('query:', query)
async def main():
    async with SessionLocal() as session:
        result = await resolve_product_info(query, session)
        print('status:', result.status)
        for entry in result.entries:
            print('entry:', entry.name, entry.stock_status, entry.stock_qty)
        print('suggestions:', result.suggestions)

asyncio.run(main())
