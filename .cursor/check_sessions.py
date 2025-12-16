import asyncio
from sqlalchemy import select, func
from db.session import SessionLocal
from db.models import ChatSession

async def check():
    async with SessionLocal() as db:
        total = await db.execute(select(func.count(ChatSession.session_id)))
        print('Total sesiones:', total.scalar_one())
        
        telegram = await db.execute(select(func.count(ChatSession.session_id)).where(ChatSession.session_id.like('telegram:%')))
        print('Sesiones Telegram:', telegram.scalar_one())
        
        web = await db.execute(select(func.count(ChatSession.session_id)).where(ChatSession.session_id.like('web:%')))
        print('Sesiones Web:', web.scalar_one())
        
        # Mostrar algunas sesiones de ejemplo
        samples = await db.execute(select(ChatSession).limit(5))
        for s in samples.scalars().all():
            print(f"  - {s.session_id[:50]}... | user: {s.user_identifier[:30] if s.user_identifier else 'None'} | status: {s.status}")

asyncio.run(check())

