import asyncio
from sqlalchemy import Column, Integer, BigInteger
from sqlalchemy.orm import sessionmaker, declarative_base
from sqlalchemy.future import select
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from discord.ext import commands
import aiosqlite

Base = declarative_base()

class Level(Base):
    __tablename__ = 'levels'

    guild_id = Column(BigInteger, primary_key=True)
    user_id = Column(BigInteger, primary_key=True)
    xp = Column(Integer, default=0)
    level = Column(Integer, default=1)

DATABASE_URL = 'sqlite+aiosqlite:///levels.db'

engine = create_async_engine(DATABASE_URL, future=True)
SessionLocal = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False, future=True)

async def init_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

async def get_user_data(guild_id, user_id):
    async with SessionLocal() as session:
        stmt = select(Level).filter(Level.guild_id == guild_id, Level.user_id == user_id)
        result = await session.execute(stmt)
        user_data = result.scalars().first()
        return user_data if user_data else Level(guild_id=guild_id, user_id=user_id)

async def update_user_data(guild_id, user_id, xp, level):
    async with SessionLocal() as session:
        user_data = await get_user_data(guild_id, user_id)
        user_data.xp = xp
        user_data.level = level
        session.add(user_data)
        await session.commit()
