"""Base repository implementation."""

from typing import TypeVar, Generic, List, Optional, Dict, Any, Type
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, delete, update
from sqlalchemy.orm import DeclarativeBase

from api.interfaces.base import BaseRepositoryInterface

T = TypeVar('T', bound=DeclarativeBase)


class BaseRepository(BaseRepositoryInterface[T], Generic[T]):
    """Base repository implementation with common CRUD operations."""
    
    def __init__(self, model: Type[T]):
        self.model = model
    
    async def create(self, session: AsyncSession, **kwargs) -> T:
        """Create a new entity."""
        instance = self.model(**kwargs)
        session.add(instance)
        await session.flush()
        await session.refresh(instance)
        return instance
    
    async def get_by_id(self, session: AsyncSession, entity_id: str) -> Optional[T]:
        """Get entity by ID."""
        stmt = select(self.model).where(self.model.id == entity_id)
        result = await session.execute(stmt)
        return result.scalar_one_or_none()
    
    async def get_all(self, session: AsyncSession, limit: int = 100, offset: int = 0) -> List[T]:
        """Get all entities with pagination."""
        stmt = select(self.model).limit(limit).offset(offset)
        result = await session.execute(stmt)
        return list(result.scalars().all())
    
    async def update(self, session: AsyncSession, entity_id: str, **kwargs) -> Optional[T]:
        """Update entity by ID."""
        stmt = update(self.model).where(self.model.id == entity_id).values(**kwargs)
        await session.execute(stmt)
        await session.flush()
        return await self.get_by_id(session, entity_id)
    
    async def delete(self, session: AsyncSession, entity_id: str) -> bool:
        """Delete entity by ID."""
        stmt = delete(self.model).where(self.model.id == entity_id)
        result = await session.execute(stmt)
        return result.rowcount > 0
    
    async def exists(self, session: AsyncSession, entity_id: str) -> bool:
        """Check if entity exists."""
        stmt = select(func.count()).select_from(self.model).where(self.model.id == entity_id)
        result = await session.execute(stmt)
        return result.scalar() > 0
    
    async def count(self, session: AsyncSession, filters: Optional[Dict[str, Any]] = None) -> int:
        """Count entities with optional filters."""
        stmt = select(func.count()).select_from(self.model)
        
        if filters:
            for key, value in filters.items():
                if hasattr(self.model, key):
                    stmt = stmt.where(getattr(self.model, key) == value)
        
        result = await session.execute(stmt)
        return result.scalar() or 0