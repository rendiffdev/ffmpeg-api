"""
API Key service for authentication and key management.
"""
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any
from uuid import UUID

from sqlalchemy import select, func, and_, or_
from sqlalchemy.ext.asyncio import AsyncSession
import structlog

from api.models.api_key import APIKey

logger = structlog.get_logger()


class APIKeyService:
    """Service for managing API keys."""
    
    @staticmethod
    async def create_api_key(
        session: AsyncSession,
        name: str,
        user_id: Optional[str] = None,
        organization: Optional[str] = None,
        description: Optional[str] = None,
        expires_in_days: Optional[int] = None,
        max_concurrent_jobs: int = 5,
        monthly_limit_minutes: int = 10000,
        is_admin: bool = False,
        created_by: Optional[str] = None,
    ) -> tuple[APIKey, str]:
        """
        Create a new API key.
        
        Returns:
            tuple: (api_key_model, raw_key) - raw_key should be shown to user only once
        """
        # Generate key
        raw_key, key_hash, key_prefix = APIKey.generate_key()
        
        # Calculate expiry
        expires_at = None
        if expires_in_days:
            expires_at = datetime.utcnow() + timedelta(days=expires_in_days)
        
        # Create API key model
        api_key = APIKey(
            name=name,
            key_hash=key_hash,
            key_prefix=key_prefix,
            user_id=user_id,
            organization=organization,
            description=description,
            expires_at=expires_at,
            max_concurrent_jobs=max_concurrent_jobs,
            monthly_limit_minutes=monthly_limit_minutes,
            is_admin=is_admin,
            created_by=created_by,
        )
        
        session.add(api_key)
        await session.commit()
        await session.refresh(api_key)
        
        logger.info(
            "API key created",
            key_id=str(api_key.id),
            name=name,
            user_id=user_id,
            organization=organization,
            expires_at=expires_at,
        )
        
        return api_key, raw_key
    
    @staticmethod
    async def validate_api_key(
        session: AsyncSession,
        raw_key: str,
        update_usage: bool = True,
    ) -> Optional[APIKey]:
        """
        Validate an API key and optionally update usage stats.
        
        Args:
            session: Database session
            raw_key: The raw API key to validate
            update_usage: Whether to update last_used_at and request count
            
        Returns:
            APIKey model if valid, None if invalid
        """
        if not raw_key or not raw_key.strip():
            return None
        
        # Hash the key for lookup
        key_hash = APIKey.hash_key(raw_key)
        
        # Find API key by hash
        stmt = select(APIKey).where(APIKey.key_hash == key_hash)
        result = await session.execute(stmt)
        api_key = result.scalar_one_or_none()
        
        if not api_key:
            logger.warning("API key not found", key_prefix=raw_key[:8])
            return None
        
        # Check if key is valid
        if not api_key.is_valid():
            logger.warning(
                "Invalid API key used",
                key_id=str(api_key.id),
                is_active=api_key.is_active,
                is_expired=api_key.is_expired(),
                revoked_at=api_key.revoked_at,
            )
            return None
        
        # Update usage if requested
        if update_usage:
            api_key.update_last_used()
            await session.commit()
        
        logger.info(
            "API key validated successfully",
            key_id=str(api_key.id),
            name=api_key.name,
            user_id=api_key.user_id,
        )
        
        return api_key
    
    @staticmethod
    async def get_api_key_by_id(
        session: AsyncSession,
        key_id: UUID,
    ) -> Optional[APIKey]:
        """Get API key by ID."""
        stmt = select(APIKey).where(APIKey.id == key_id)
        result = await session.execute(stmt)
        return result.scalar_one_or_none()
    
    @staticmethod
    async def get_api_keys_for_user(
        session: AsyncSession,
        user_id: str,
        include_revoked: bool = False,
    ) -> List[APIKey]:
        """Get all API keys for a user."""
        stmt = select(APIKey).where(APIKey.user_id == user_id)
        
        if not include_revoked:
            stmt = stmt.where(APIKey.revoked_at.is_(None))
        
        stmt = stmt.order_by(APIKey.created_at.desc())
        
        result = await session.execute(stmt)
        return list(result.scalars().all())
    
    @staticmethod
    async def get_api_keys_for_organization(
        session: AsyncSession,
        organization: str,
        include_revoked: bool = False,
    ) -> List[APIKey]:
        """Get all API keys for an organization."""
        stmt = select(APIKey).where(APIKey.organization == organization)
        
        if not include_revoked:
            stmt = stmt.where(APIKey.revoked_at.is_(None))
        
        stmt = stmt.order_by(APIKey.created_at.desc())
        
        result = await session.execute(stmt)
        return list(result.scalars().all())
    
    @staticmethod
    async def list_api_keys(
        session: AsyncSession,
        limit: int = 100,
        offset: int = 0,
        active_only: bool = True,
        search: Optional[str] = None,
    ) -> tuple[List[APIKey], int]:
        """
        List API keys with pagination and filtering.
        
        Returns:
            tuple: (api_keys, total_count)
        """
        # Build base query
        stmt = select(APIKey)
        count_stmt = select(func.count(APIKey.id))
        
        # Apply filters
        if active_only:
            stmt = stmt.where(
                and_(
                    APIKey.is_active == True,
                    APIKey.revoked_at.is_(None)
                )
            )
            count_stmt = count_stmt.where(
                and_(
                    APIKey.is_active == True,
                    APIKey.revoked_at.is_(None)
                )
            )
        
        if search:
            search_filter = or_(
                APIKey.name.ilike(f"%{search}%"),
                APIKey.user_id.ilike(f"%{search}%"),
                APIKey.organization.ilike(f"%{search}%"),
                APIKey.description.ilike(f"%{search}%"),
            )
            stmt = stmt.where(search_filter)
            count_stmt = count_stmt.where(search_filter)
        
        # Apply pagination
        stmt = stmt.order_by(APIKey.created_at.desc()).limit(limit).offset(offset)
        
        # Execute queries
        result = await session.execute(stmt)
        count_result = await session.execute(count_stmt)
        
        api_keys = list(result.scalars().all())
        total_count = count_result.scalar()
        
        return api_keys, total_count
    
    @staticmethod
    async def revoke_api_key(
        session: AsyncSession,
        key_id: UUID,
        revoked_by: Optional[str] = None,
    ) -> Optional[APIKey]:
        """Revoke an API key."""
        api_key = await APIKeyService.get_api_key_by_id(session, key_id)
        
        if not api_key:
            return None
        
        if api_key.revoked_at:
            return api_key  # Already revoked
        
        api_key.revoke()
        await session.commit()
        
        logger.info(
            "API key revoked",
            key_id=str(api_key.id),
            name=api_key.name,
            revoked_by=revoked_by,
        )
        
        return api_key
    
    @staticmethod
    async def extend_api_key_expiry(
        session: AsyncSession,
        key_id: UUID,
        additional_days: int,
    ) -> Optional[APIKey]:
        """Extend API key expiry."""
        api_key = await APIKeyService.get_api_key_by_id(session, key_id)
        
        if not api_key:
            return None
        
        old_expiry = api_key.expires_at
        api_key.extend_expiry(additional_days)
        await session.commit()
        
        logger.info(
            "API key expiry extended",
            key_id=str(api_key.id),
            name=api_key.name,
            old_expiry=old_expiry,
            new_expiry=api_key.expires_at,
            additional_days=additional_days,
        )
        
        return api_key
    
    @staticmethod
    async def update_api_key(
        session: AsyncSession,
        key_id: UUID,
        updates: Dict[str, Any],
    ) -> Optional[APIKey]:
        """Update API key properties."""
        api_key = await APIKeyService.get_api_key_by_id(session, key_id)
        
        if not api_key:
            return None
        
        # Apply updates
        allowed_fields = {
            "name", "description", "max_concurrent_jobs", 
            "monthly_limit_minutes", "is_active"
        }
        
        for field, value in updates.items():
            if field in allowed_fields and hasattr(api_key, field):
                setattr(api_key, field, value)
        
        await session.commit()
        
        logger.info(
            "API key updated",
            key_id=str(api_key.id),
            name=api_key.name,
            updates=updates,
        )
        
        return api_key
    
    @staticmethod
    async def get_usage_stats(
        session: AsyncSession,
        key_id: Optional[UUID] = None,
        user_id: Optional[str] = None,
        organization: Optional[str] = None,
        days: int = 30,
    ) -> Dict[str, Any]:
        """Get usage statistics for API keys."""
        # This would typically query a separate usage/metrics table
        # For now, return basic stats from the API key table
        
        stmt = select(APIKey)
        
        if key_id:
            stmt = stmt.where(APIKey.id == key_id)
        elif user_id:
            stmt = stmt.where(APIKey.user_id == user_id)
        elif organization:
            stmt = stmt.where(APIKey.organization == organization)
        
        result = await session.execute(stmt)
        api_keys = list(result.scalars().all())
        
        total_requests = sum(key.total_requests for key in api_keys)
        active_keys = sum(1 for key in api_keys if key.is_valid())
        
        return {
            "total_keys": len(api_keys),
            "active_keys": active_keys,
            "total_requests": total_requests,
            "period_days": days,
            "api_keys": [key.to_dict() for key in api_keys],
        }