from app.models.TokenHolder import TokenHolder
from sqlalchemy import create_engine
from app.config.settings import (
    PG_USER,
    PG_PASSWORD,
    PG_HOST,
    PG_PORT,
    PG_NAME,
    POOL_MIN_SIZE,
    POOL_MAX_SIZE,
)
from sqlalchemy.ext.asyncio import create_async_engine
from dotenv import load_dotenv
import asyncio

load_dotenv()

PG_URL = f"postgresql://{PG_USER}:{PG_PASSWORD}@{PG_HOST}:{PG_PORT}/{PG_NAME}"

engine = create_engine(PG_URL, echo=True)

ASYNC_PG_URL = (
    f"postgresql+asyncpg://{PG_USER}:{PG_PASSWORD}@{PG_HOST}:{PG_PORT}/{PG_NAME}"
)


async_engine = create_async_engine(
    ASYNC_PG_URL, echo=True, pool_size=POOL_MIN_SIZE, max_overflow=POOL_MAX_SIZE
)


async def create_tables():
    async with async_engine.begin() as conn:
        await conn.run_sync(TokenHolder.metadata.create_all)


async def main():
    await create_tables()


if __name__ == "__main__":
    asyncio.run(main())
