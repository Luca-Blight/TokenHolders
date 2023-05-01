from fastapi import FastAPI, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import func

from typing import Optional
from contextlib import asynccontextmanager
from sqlalchemy.orm import sessionmaker
from app.models.TokenHolder import TokenHolder
from app.database.main import async_engine
from aiocache import cached, SimpleMemoryCache

import uvicorn
import ujson

app = FastAPI()
cache = SimpleMemoryCache()


@asynccontextmanager
async def get_async_session() -> AsyncSession:
    async_session = sessionmaker(
        bind=async_engine, class_=AsyncSession, expire_on_commit=False
    )

    session = async_session()
    await session.begin()

    try:
        yield session
    finally:
        await session.close()


@app.get("/")
async def get_root():
    return ujson.dumps({"message": "Hello World"})


@app.get("/token_holders")
@cached(ttl=3600)
async def get_token_holders(
    limit: Optional[int] = 100,
    order_by: Optional[str] = "desc",
):
    async with get_async_session() as db:
        subquery = (
            select(
                TokenHolder.address,
                func.max(TokenHolder.block_date).label("max_timestamp"),
            )
            .group_by(TokenHolder.address)
            .subquery()
        )

        query = select(TokenHolder).join(
            subquery,
            (TokenHolder.address == subquery.c.address)
            & (TokenHolder.block_date == subquery.c.max_timestamp),
        )

        if order_by.lower() == "desc":
            query = query.order_by(TokenHolder.balance.desc())
        elif order_by.lower() == "asc":
            query = query.order_by(TokenHolder.balance.asc())
        else:
            raise HTTPException(
                status_code=400, detail="Invalid order_by value. Use 'asc' or 'desc'."
            )

        query = query.limit(limit)
        result = await db.execute(query)
        results = result.fetchall()

        token_holders = [
            {
                "address": holder[0].address,
                "balance": holder[0].balance,
                "total_supply_percentage": holder[0].total_supply_percentage,
                "weekly_balance_change": holder[0].weekly_balance_change,
                "last_updated": holder[0].block_date.isoformat(),
            }
            for holder in results
        ]

    return ujson.dumps({"token_holders": token_holders})


@app.get("/token_holders/{token_holder_address}")
@cached(ttl=3600)
async def get_token_holders(
    token_holder_address: str = None,
    balance: bool = False,
    weekly_balance_change: bool = False,
):
    async with get_async_session() as db:

        if balance == True & weekly_balance_change == True:
            query = (
                select(
                    TokenHolder.address,
                    TokenHolder.balance,
                    TokenHolder.weekly_balance_change,
                    TokenHolder.block_date,
                )
                .where(TokenHolder.address == token_holder_address)
                .order_by(TokenHolder.block_date.desc())
                .limit(1)
            )

            result = await db.execute(query)
            results = result.fetchall()

            token_holder = [
                {
                    "address": holder.address,
                    "balance": holder.balance,
                    "weekly_balance_change": holder.weekly_balance_change,
                }
                for holder in results
            ]
            return ujson.dumps({"token_holder": token_holder})
        elif balance == True & weekly_balance_change == False:

            query = (
                select(TokenHolder.address, TokenHolder.balance, TokenHolder.block_date)
                .where(TokenHolder.address == token_holder_address)
                .order_by(TokenHolder.block_date.desc())
                .limit(1)
            )

            result = await db.execute(query)
            results = result.fetchall()
            token_holder = [
                {
                    "address": holder.address,
                    "balance": holder.balance,
                }
                for holder in results
            ]
            return ujson.dumps({"token_holder": token_holder})

        else:

            query = (
                select(
                    TokenHolder.address,
                    TokenHolder.weekly_balance_change,
                    TokenHolder.block_date,
                )
                .where(TokenHolder.address == token_holder_address)
                .order_by(TokenHolder.block_date.desc())
                .limit(1)
            )

            result = await db.execute(query)
            results = result.fetchall()

            token_holder = [
                {
                    "address": holder.address,
                    "weekly_balance_change": holder.weekly_balance_change,
                }
                for holder in results
            ]

            return ujson.dumps({"token_holder": token_holder})


if __name__ == "__main__":
    
    server = uvicorn.Server(uvicorn.Config("main:app", host="127.0.0.1", port=8000, reload=True))

    try:
        server.run()
    except KeyboardInterrupt:
        server.shutdown()
        print("Shutting down...")