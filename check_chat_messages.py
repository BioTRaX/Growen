#!/usr/bin/env python
"""Script temporal para verificar mensajes en chat_messages."""
import asyncio
import sys
from db.session import get_db
from sqlalchemy import text

# Fix para Windows
if sys.platform == 'win32':
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

async def check_messages():
    async for db in get_db():
        result = await db.execute(
            text("SELECT session_id, role, LEFT(content, 80) as content, created_at FROM chat_messages ORDER BY created_at DESC LIMIT 10")
        )
        rows = result.fetchall()
        
        if not rows:
            print("No hay mensajes guardados en chat_messages")
        else:
            print(f"Últimos {len(rows)} mensajes:")
            print("-" * 100)
            for r in rows:
                print(f"Session: {r[0]} | Role: {r[1]:10} | Content: {r[2]:60} | At: {r[3]}")
        break

if __name__ == "__main__":
    asyncio.run(check_messages())
