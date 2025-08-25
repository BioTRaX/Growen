from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from db.session import get_db

router = APIRouter(prefix="/healthz", tags=["health"])

@router.get("/db")
async def health_db(db: AsyncSession = Depends(get_db)):
    await db.execute(text("SELECT 1"))
    return {"db": "ok"}
