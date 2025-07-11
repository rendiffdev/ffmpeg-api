"""Base repository interface."""

from abc import ABC, abstractmethod
from typing import TypeVar, Generic, List, Optional, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession

T = TypeVar('T')


class BaseRepositoryInterface(ABC, Generic[T]):
    """Base repository interface defining common CRUD operations."""
    
    @abstractmethod
    async def create(self, session: AsyncSession, **kwargs) -> T:
        """Create a new entity."""
        pass
    
    @abstractmethod
    async def get_by_id(self, session: AsyncSession, entity_id: str) -> Optional[T]:
        """Get entity by ID."""
        pass
    
    @abstractmethod
    async def get_all(self, session: AsyncSession, limit: int = 100, offset: int = 0) -> List[T]:
        """Get all entities with pagination."""
        pass
    
    @abstractmethod
    async def update(self, session: AsyncSession, entity_id: str, **kwargs) -> Optional[T]:
        """Update entity by ID."""
        pass
    
    @abstractmethod
    async def delete(self, session: AsyncSession, entity_id: str) -> bool:
        """Delete entity by ID."""
        pass
    
    @abstractmethod
    async def exists(self, session: AsyncSession, entity_id: str) -> bool:
        """Check if entity exists."""
        pass
    
    @abstractmethod
    async def count(self, session: AsyncSession, filters: Optional[Dict[str, Any]] = None) -> int:
        """Count entities with optional filters."""
        pass