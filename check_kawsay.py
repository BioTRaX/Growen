"""Check product tags for Kawsay."""
import asyncio
from sqlalchemy import text
from db.session import get_session

async def check():
    async for session in get_session():
        # Check product
        result = await session.execute(
            text("SELECT p.id, p.sku, p.title, p.stock FROM products p WHERE p.sku = 'FER_0009_MIN' OR p.title ILIKE '%Kawsay%' LIMIT 5")
        )
        for row in result:
            print(f"ID: {row[0]}, SKU: {row[1]}")
            print(f"Title: {row[2]}, Stock: {row[3]}")
            
            # Get tags for this product
            tags_result = await session.execute(
                text(f"SELECT t.name FROM tags t JOIN product_tags pt ON t.id = pt.tag_id WHERE pt.product_id = {row[0]}")
            )
            tags = [t[0] for t in tags_result]
            print(f"Tags: {tags}")
            print("---")
        break

asyncio.run(check())
