from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from config.settings import DATABASE_URL
from database.models import Base

engine = create_async_engine(
    DATABASE_URL,
    echo=False,
)

AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    expire_on_commit=False,
)


async def init_db():
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)


async def close_db():
    await engine.dispose()
