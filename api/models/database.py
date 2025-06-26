"""
Database initialization and session management
"""
from typing import AsyncGenerator
import os
from pathlib import Path

from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.pool import NullPool, StaticPool

from api.config import settings
from api.models.job import Base
from api.utils.database import set_sqlite_pragma

# Configure engine based on database type
if "sqlite" in settings.database_url_async:
    # SQLite specific configuration
    connect_args = {"check_same_thread": False}
    poolclass = StaticPool if ":memory:" in settings.database_url_async else NullPool
    engine = create_async_engine(
        settings.database_url_async,
        connect_args=connect_args,
        poolclass=poolclass,
    )
else:
    # PostgreSQL configuration (kept for compatibility)
    engine = create_async_engine(
        settings.database_url_async,
        pool_pre_ping=True,
        pool_size=settings.DATABASE_POOL_SIZE,
        max_overflow=settings.DATABASE_MAX_OVERFLOW,
        poolclass=NullPool if settings.TESTING else None,
    )

# Create session factory
AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


async def init_db() -> None:
    """Initialize database tables."""
    # For SQLite, ensure the directory exists
    if "sqlite" in settings.database_url_async:
        db_path = settings.DATABASE_URL.replace("sqlite:///", "")
        db_dir = os.path.dirname(db_path)
        if db_dir:
            Path(db_dir).mkdir(parents=True, exist_ok=True)
    
    async with engine.begin() as conn:
        # Create all tables
        await conn.run_sync(Base.metadata.create_all)


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """Get database session."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()