"""API Key repository implementation."""

from typing import List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_
from datetime import datetime

from .base import BaseRepository
from api.interfaces.api_key_repository import APIKeyRepositoryInterface
from api.models.api_key import APIKey


class APIKeyRepository(BaseRepository[APIKey], APIKeyRepositoryInterface):
    """API Key repository implementation."""
    
    def __init__(self):
        super().__init__(APIKey)
    
    async def get_by_key(self, session: AsyncSession, key: str) -> Optional[APIKey]:
        """Get API key by key value."""
        stmt = select(APIKey).where(APIKey.key == key)
        result = await session.execute(stmt)
        return result.scalar_one_or_none()
    
    async def get_by_user_id(self, session: AsyncSession, user_id: str) -> List[APIKey]:
        """Get API keys by user ID."""
        stmt = select(APIKey).where(APIKey.user_id == user_id).order_by(APIKey.created_at.desc())
        result = await session.execute(stmt)
        return list(result.scalars().all())
    
    async def get_active_keys(self, session: AsyncSession) -> List[APIKey]:
        """Get all active API keys."""
        now = datetime.utcnow()
        stmt = (
            select(APIKey)
            .where(
                and_(
                    APIKey.is_active == True,
                    or_(APIKey.expires_at.is_(None), APIKey.expires_at > now)
                )
            )
            .order_by(APIKey.created_at.desc())
        )
        result = await session.execute(stmt)
        return list(result.scalars().all())
    
    async def get_expired_keys(self, session: AsyncSession) -> List[APIKey]:
        """Get expired API keys."""
        now = datetime.utcnow()
        stmt = (
            select(APIKey)
            .where(
                and_(
                    APIKey.expires_at.isnot(None),
                    APIKey.expires_at <= now
                )
            )
            .order_by(APIKey.expires_at.desc())
        )
        result = await session.execute(stmt)
        return list(result.scalars().all())
    
    async def revoke_key(self, session: AsyncSession, key_id: str) -> bool:
        """Revoke an API key."""
        result = await self.update(session, key_id, is_active=False, revoked_at=datetime.utcnow())
        return result is not None
    
    async def activate_key(self, session: AsyncSession, key_id: str) -> Optional[APIKey]:
        """Activate an API key."""
        return await self.update(session, key_id, is_active=True, revoked_at=None)
    
    async def update_last_used(self, session: AsyncSession, key: str) -> Optional[APIKey]:
        """Update last used timestamp for a key."""
        api_key = await self.get_by_key(session, key)
        if api_key:
            return await self.update(session, api_key.id, last_used_at=datetime.utcnow())
        return None