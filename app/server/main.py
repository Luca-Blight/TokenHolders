from fastapi import FastAPI, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from typing import Optional
from contextlib import asynccontextmanager
from sqlalchemy.orm import sessionmaker
from app.models import TokenHolder
from database.main import async_engine
from aiocache import cached
import uvicorn


app = FastAPI()



### Add caching

@asynccontextmanager
async def get_async_session() -> AsyncSession:
    async_session = sessionmaker(
        bind=async_engine, class_=AsyncSession, expire_on_commit=False
    )

    session = async_session()

    try:
        yield session
    finally:
        await session.close()
        

@app.get("/token_holders")
async def get_token_holders(
    db: AsyncSession = Depends(get_async_session),
    top_token_holders: Optional[int] = None,
    limit: Optional[int] = 100,
    order_by: Optional[str] = "desc",
):
    query = select(TokenHolder)

    if top_token_holders:
        limit = top_token_holders

    if order_by.lower() == "desc":
        query = query.order_by(TokenHolder.balance.desc())
    elif order_by.lower() == "asc":
        query = query.order_by(TokenHolder.balance.asc())
    else:
        raise HTTPException(status_code=400, detail="Invalid order_by value. Use 'asc' or 'desc'.")

    query = query.limit(limit)
    result = await db.execute(query)
    results = result.fetchall()

    token_holders = [
        {
            "address": holder.address,
            "balance": holder.balance,
            "total_supply": holder.total_supply,
            "total_supply_percentage": holder.total_supply_percentage,
            "weekly_balance_change": holder.weekly_balance_change,
            "last_updated": holder.last_updated,
        }
        for holder in results
    ]

    return {"token_holders": token_holders}


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)