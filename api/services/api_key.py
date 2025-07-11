"""
API Key service for managing authentication keys
"""
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any
from uuid import UUID

from sqlalchemy import select, func, and_, or_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import IntegrityError
import structlog

from api.models.api_key import ApiKey, ApiKeyStatus, ApiKeyUser, ApiKeyCreate, ApiKeyUpdateRequest
from api.utils.error_handlers import ValidationError, NotFoundError, ConflictError

logger = structlog.get_logger()


class ApiKeyService:
    """Service for managing API keys."""
    
    def __init__(self, db: AsyncSession):
        self.db = db
    
    async def create_api_key(
        self, 
        request: ApiKeyCreate, 
        created_by: Optional[str] = None
    ) -> tuple[ApiKey, str]:
        """Create a new API key.
        
        Args:
            request: API key creation request
            created_by: Who is creating this key
            
        Returns:
            tuple: (ApiKey instance, raw key string)
            
        Raises:
            ValidationError: If validation fails
            ConflictError: If key already exists (very unlikely)
        """
        try:
            # Generate the key
            full_key, prefix, key_hash = ApiKey.generate_key()
            
            # Calculate expiration if specified
            expires_at = None
            if request.expires_days:
                expires_at = datetime.utcnow() + timedelta(days=request.expires_days)
            
            # Create the API key instance
            api_key = ApiKey(
                name=request.name,
                key_hash=key_hash,
                prefix=prefix,
                status=ApiKeyStatus.ACTIVE,
                owner_name=request.owner_name,
                owner_email=request.owner_email,
                role=request.role,
                max_concurrent_jobs=request.max_concurrent_jobs,
                monthly_quota_minutes=request.monthly_quota_minutes,
                expires_at=expires_at,
                created_by=created_by,
                metadata=request.metadata,
            )
            
            # Save to database
            self.db.add(api_key)
            await self.db.commit()
            await self.db.refresh(api_key)
            
            logger.info(
                "API key created",
                key_id=str(api_key.id),
                prefix=prefix,
                name=request.name,
                created_by=created_by,
            )
            
            return api_key, full_key
            
        except IntegrityError as e:
            await self.db.rollback()
            logger.error("API key creation failed", error=str(e))
            raise ConflictError("API key already exists (hash collision)")
        except Exception as e:
            await self.db.rollback()
            logger.error("API key creation failed", error=str(e))
            raise
    
    async def get_api_key_by_id(self, key_id: UUID) -> Optional[ApiKey]:
        """Get API key by ID."""
        stmt = select(ApiKey).where(ApiKey.id == key_id)
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()
    
    async def get_api_key_by_hash(self, key_hash: str) -> Optional[ApiKey]:
        """Get API key by hash."""
        stmt = select(ApiKey).where(ApiKey.key_hash == key_hash)
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()
    
    async def validate_api_key(self, key: str) -> Optional[ApiKeyUser]:
        """Validate an API key and return user information.
        
        Args:
            key: The raw API key string
            
        Returns:
            ApiKeyUser instance if valid, None if invalid
        """
        if not key or not key.strip():
            return None
        
        # Hash the key for lookup
        key_hash = ApiKey.hash_key(key)
        
        # Find the API key
        api_key = await self.get_api_key_by_hash(key_hash)
        if not api_key:
            logger.warning("API key not found", key_prefix=key[:8])
            return None
        
        # Check if valid
        if not api_key.is_valid():
            logger.warning(
                "Invalid API key used",
                key_id=str(api_key.id),
                status=api_key.status,
                expired=api_key.is_expired(),
            )
            return None
        
        # Update last used timestamp
        api_key.update_last_used()
        await self.db.commit()
        
        # Return user information
        return ApiKeyUser(
            id=str(api_key.id),
            api_key_id=api_key.id,
            api_key_prefix=api_key.prefix,
            role=api_key.role,
            max_concurrent_jobs=api_key.max_concurrent_jobs,
            monthly_quota_minutes=api_key.monthly_quota_minutes,
            is_admin=api_key.role == "admin",
            total_jobs_created=api_key.total_jobs_created,
            total_minutes_processed=api_key.total_minutes_processed,
            last_used_at=api_key.last_used_at,
        )
    
    async def list_api_keys(
        self,
        page: int = 1,
        per_page: int = 20,
        status: Optional[ApiKeyStatus] = None,
        owner_id: Optional[str] = None,
    ) -> tuple[List[ApiKey], int]:
        """List API keys with pagination.
        
        Args:
            page: Page number (1-based)
            per_page: Items per page
            status: Filter by status
            owner_id: Filter by owner ID
            
        Returns:
            tuple: (list of ApiKey instances, total count)
        """
        # Build query
        query = select(ApiKey)
        
        # Apply filters
        conditions = []
        if status:
            conditions.append(ApiKey.status == status)
        if owner_id:
            conditions.append(ApiKey.owner_id == owner_id)
        
        if conditions:
            query = query.where(and_(*conditions))
        
        # Order by creation date (newest first)
        query = query.order_by(ApiKey.created_at.desc())
        
        # Get total count
        count_query = select(func.count(ApiKey.id))
        if conditions:
            count_query = count_query.where(and_(*conditions))
        
        total_result = await self.db.execute(count_query)
        total = total_result.scalar()
        
        # Apply pagination
        offset = (page - 1) * per_page
        query = query.offset(offset).limit(per_page)
        
        # Execute query
        result = await self.db.execute(query)
        api_keys = result.scalars().all()
        
        return list(api_keys), total
    
    async def update_api_key(
        self,
        key_id: UUID,
        request: ApiKeyUpdateRequest,
        updated_by: Optional[str] = None,
    ) -> ApiKey:
        """Update an API key.
        
        Args:
            key_id: API key ID
            request: Update request
            updated_by: Who is updating this key
            
        Returns:
            Updated ApiKey instance
            
        Raises:
            NotFoundError: If key not found
        """
        # Get existing key
        api_key = await self.get_api_key_by_id(key_id)
        if not api_key:
            raise NotFoundError(f"API key {key_id} not found")
        
        # Update fields
        if request.name is not None:
            api_key.name = request.name
        if request.status is not None:
            api_key.status = request.status
            if request.status == ApiKeyStatus.REVOKED:
                api_key.revoked_at = datetime.utcnow()
                api_key.revoked_by = updated_by
        if request.max_concurrent_jobs is not None:
            api_key.max_concurrent_jobs = request.max_concurrent_jobs
        if request.monthly_quota_minutes is not None:
            api_key.monthly_quota_minutes = request.monthly_quota_minutes
        if request.expires_days is not None:
            api_key.expires_at = datetime.utcnow() + timedelta(days=request.expires_days)
        if request.metadata is not None:
            api_key.metadata = request.metadata
        
        # Save changes
        await self.db.commit()
        await self.db.refresh(api_key)
        
        logger.info(
            "API key updated",
            key_id=str(api_key.id),
            updated_by=updated_by,
        )
        
        return api_key
    
    async def revoke_api_key(
        self,
        key_id: UUID,
        reason: Optional[str] = None,
        revoked_by: Optional[str] = None,
    ) -> ApiKey:
        """Revoke an API key.
        
        Args:
            key_id: API key ID
            reason: Reason for revocation
            revoked_by: Who is revoking this key
            
        Returns:
            Revoked ApiKey instance
            
        Raises:
            NotFoundError: If key not found
        """
        # Get existing key
        api_key = await self.get_api_key_by_id(key_id)
        if not api_key:
            raise NotFoundError(f"API key {key_id} not found")
        
        # Revoke the key
        api_key.status = ApiKeyStatus.REVOKED
        api_key.revoked_at = datetime.utcnow()
        api_key.revoked_by = revoked_by
        api_key.revocation_reason = reason
        
        # Save changes
        await self.db.commit()
        await self.db.refresh(api_key)
        
        logger.info(
            "API key revoked",
            key_id=str(api_key.id),
            reason=reason,
            revoked_by=revoked_by,
        )
        
        return api_key
    
    async def delete_api_key(self, key_id: UUID) -> None:
        """Delete an API key permanently.
        
        Args:
            key_id: API key ID
            
        Raises:
            NotFoundError: If key not found
        """
        # Get existing key
        api_key = await self.get_api_key_by_id(key_id)
        if not api_key:
            raise NotFoundError(f"API key {key_id} not found")
        
        # Delete the key
        await self.db.delete(api_key)
        await self.db.commit()
        
        logger.info("API key deleted", key_id=str(key_id))
    
    async def update_usage_stats(
        self,
        key_hash: str,
        jobs_created: int = 0,
        minutes_processed: int = 0,
    ) -> None:
        """Update usage statistics for an API key.
        
        Args:
            key_hash: API key hash
            jobs_created: Number of jobs to add
            minutes_processed: Minutes to add
        """
        api_key = await self.get_api_key_by_hash(key_hash)
        if api_key:
            api_key.total_jobs_created += jobs_created
            api_key.total_minutes_processed += minutes_processed
            await self.db.commit()
    
    async def cleanup_expired_keys(self) -> int:
        """Clean up expired API keys by marking them as expired.
        
        Returns:
            Number of keys marked as expired
        """
        now = datetime.utcnow()
        
        # Find expired keys that are still active
        stmt = select(ApiKey).where(
            and_(
                ApiKey.expires_at < now,
                ApiKey.status == ApiKeyStatus.ACTIVE,
            )
        )
        
        result = await self.db.execute(stmt)
        expired_keys = result.scalars().all()
        
        # Mark as expired
        for key in expired_keys:
            key.status = ApiKeyStatus.EXPIRED
        
        if expired_keys:
            await self.db.commit()
            logger.info("Expired API keys cleaned up", count=len(expired_keys))
        
        return len(expired_keys)