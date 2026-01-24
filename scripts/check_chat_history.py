#!/usr/bin/env python
import asyncio
import sys
if sys.platform == 'win32':
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
import os
from dotenv import load_dotenv
load_dotenv()

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy import select, desc
from db.models import ChatMessage

async def check():
    db_url = os.getenv('DB_URL').replace('postgresql:', 'postgresql+asyncpg:')
    eng = create_async_engine(db_url)
    async_session = sessionmaker(eng, class_=AsyncSession, expire_on_commit=False)
    async with async_session() as s:
        stmt = select(ChatMessage).where(ChatMessage.session_id == 'telegram:328588157').order_by(desc(ChatMessage.created_at)).limit(15)
        result = await s.execute(stmt)
        msgs = result.scalars().all()
        print(f"Ultimos {len(msgs)} mensajes de telegram:328588157:\n")
        for m in reversed(msgs):
            time_str = m.created_at.strftime("%H:%M:%S")
            content_preview = m.content[:100] + "..." if len(m.content) > 100 else m.content
            print(f"  {time_str} [{m.role:9}] {content_preview}")
    await eng.dispose()

asyncio.run(check())
