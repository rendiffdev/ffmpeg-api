"""API Key repository interface."""

from abc import abstractmethod
from typing import List, Optional
from sqlalchemy.ext.asyncio import AsyncSession

from .base import BaseRepositoryInterface
from api.models.api_key import APIKey


class APIKeyRepositoryInterface(BaseRepositoryInterface[APIKey]):
    """API Key repository interface with key-specific operations."""
    
    @abstractmethod
    async def get_by_key(self, session: AsyncSession, key: str) -> Optional[APIKey]:
        """Get API key by key value."""
        pass
    
    @abstractmethod
    async def get_by_user_id(self, session: AsyncSession, user_id: str) -> List[APIKey]:
        """Get API keys by user ID."""
        pass
    
    @abstractmethod
    async def get_active_keys(self, session: AsyncSession) -> List[APIKey]:
        """Get all active API keys."""
        pass
    
    @abstractmethod
    async def get_expired_keys(self, session: AsyncSession) -> List[APIKey]:
        """Get expired API keys."""
        pass
    
    @abstractmethod
    async def revoke_key(self, session: AsyncSession, key_id: str) -> bool:
        """Revoke an API key."""
        pass
    
    @abstractmethod
    async def activate_key(self, session: AsyncSession, key_id: str) -> Optional[APIKey]:
        """Activate an API key."""
        pass
    
    @abstractmethod
    async def update_last_used(self, session: AsyncSession, key: str) -> Optional[APIKey]:
        """Update last used timestamp for a key."""
        pass