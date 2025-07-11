"""
API Keys management endpoints.
"""
from datetime import datetime
from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, Query
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession
import structlog

from api.dependencies import get_db, require_api_key, get_current_user
from api.services.api_key import APIKeyService

router = APIRouter(prefix="/api-keys", tags=["API Keys"])
logger = structlog.get_logger()


class CreateAPIKeyRequest(BaseModel):
    """Request model for creating API keys."""
    name: str = Field(..., min_length=1, max_length=255, description="Name for the API key")
    description: Optional[str] = Field(None, max_length=1000, description="Description of the API key purpose")
    expires_in_days: Optional[int] = Field(None, ge=1, le=3650, description="Number of days until expiry (max 10 years)")
    max_concurrent_jobs: int = Field(5, ge=1, le=100, description="Maximum concurrent jobs")
    monthly_limit_minutes: int = Field(10000, ge=100, le=1000000, description="Monthly processing limit in minutes")
    user_id: Optional[str] = Field(None, max_length=255, description="User ID to associate with this key")
    organization: Optional[str] = Field(None, max_length=255, description="Organization name")


class CreateAPIKeyResponse(BaseModel):
    """Response model for created API keys."""
    id: str
    name: str
    api_key: str = Field(..., description="The actual API key - save this securely, it won't be shown again")
    key_prefix: str
    expires_at: Optional[datetime]
    max_concurrent_jobs: int
    monthly_limit_minutes: int
    created_at: datetime


class APIKeyInfo(BaseModel):
    """API key information (without the actual key)."""
    id: str
    name: str
    key_prefix: str
    user_id: Optional[str]
    organization: Optional[str]
    is_active: bool
    is_admin: bool
    max_concurrent_jobs: int
    monthly_limit_minutes: int
    total_requests: int
    last_used_at: Optional[datetime]
    created_at: datetime
    expires_at: Optional[datetime]
    revoked_at: Optional[datetime]
    description: Optional[str]
    created_by: Optional[str]
    is_expired: bool
    days_until_expiry: Optional[int]


class UpdateAPIKeyRequest(BaseModel):
    """Request model for updating API keys."""
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = Field(None, max_length=1000)
    max_concurrent_jobs: Optional[int] = Field(None, ge=1, le=100)
    monthly_limit_minutes: Optional[int] = Field(None, ge=100, le=1000000)
    is_active: Optional[bool] = None


class APIKeyListResponse(BaseModel):
    """Response model for listing API keys."""
    api_keys: List[APIKeyInfo]
    total_count: int
    page: int
    page_size: int
    has_next: bool


@router.post("/", response_model=CreateAPIKeyResponse)
async def create_api_key(
    request: CreateAPIKeyRequest,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Create a new API key.
    
    **Note**: The API key will only be displayed once in the response.
    Make sure to save it securely.
    """
    # Check if user has admin privileges for certain operations
    is_admin = current_user.get("is_admin", False)
    
    # Non-admin users can only create keys for themselves
    user_id = request.user_id
    if not is_admin and user_id and user_id != current_user.get("id"):
        raise HTTPException(
            status_code=403,
            detail="You can only create API keys for yourself"
        )
    
    # Default to current user if no user_id specified
    if not user_id:
        user_id = current_user.get("id")
    
    try:
        api_key_model, raw_key = await APIKeyService.create_api_key(
            session=db,
            name=request.name,
            user_id=user_id,
            organization=request.organization,
            description=request.description,
            expires_in_days=request.expires_in_days,
            max_concurrent_jobs=request.max_concurrent_jobs,
            monthly_limit_minutes=request.monthly_limit_minutes,
            created_by=current_user.get("id"),
        )
        
        logger.info(
            "API key created",
            key_id=str(api_key_model.id),
            name=request.name,
            created_by=current_user.get("id"),
            user_id=user_id,
        )
        
        return CreateAPIKeyResponse(
            id=str(api_key_model.id),
            name=api_key_model.name,
            api_key=raw_key,
            key_prefix=api_key_model.key_prefix,
            expires_at=api_key_model.expires_at,
            max_concurrent_jobs=api_key_model.max_concurrent_jobs,
            monthly_limit_minutes=api_key_model.monthly_limit_minutes,
            created_at=api_key_model.created_at,
        )
        
    except Exception as e:
        logger.error("Failed to create API key", error=str(e))
        raise HTTPException(status_code=500, detail="Failed to create API key")


@router.get("/", response_model=APIKeyListResponse)
async def list_api_keys(
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page"),
    search: Optional[str] = Query(None, description="Search in name, user_id, organization"),
    active_only: bool = Query(True, description="Show only active keys"),
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List API keys with pagination and filtering."""
    is_admin = current_user.get("is_admin", False)
    
    offset = (page - 1) * page_size
    
    try:
        if is_admin:
            # Admin can see all keys
            api_keys, total_count = await APIKeyService.list_api_keys(
                session=db,
                limit=page_size,
                offset=offset,
                active_only=active_only,
                search=search,
            )
        else:
            # Regular users can only see their own keys
            user_id = current_user.get("id")
            if not user_id:
                raise HTTPException(status_code=403, detail="Access denied")
            
            api_keys = await APIKeyService.get_api_keys_for_user(
                session=db,
                user_id=user_id,
                include_revoked=not active_only,
            )
            
            # Apply search filter if specified
            if search:
                search_lower = search.lower()
                api_keys = [
                    key for key in api_keys
                    if (search_lower in key.name.lower() or
                        (key.description and search_lower in key.description.lower()) or
                        (key.organization and search_lower in key.organization.lower()))
                ]
            
            total_count = len(api_keys)
            
            # Apply pagination
            api_keys = api_keys[offset:offset + page_size]
        
        # Convert to response models
        api_key_infos = [APIKeyInfo(**key.to_dict()) for key in api_keys]
        
        return APIKeyListResponse(
            api_keys=api_key_infos,
            total_count=total_count,
            page=page,
            page_size=page_size,
            has_next=offset + page_size < total_count,
        )
        
    except Exception as e:
        logger.error("Failed to list API keys", error=str(e))
        raise HTTPException(status_code=500, detail="Failed to list API keys")


@router.get("/{key_id}", response_model=APIKeyInfo)
async def get_api_key(
    key_id: UUID,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get API key details by ID."""
    is_admin = current_user.get("is_admin", False)
    
    try:
        api_key = await APIKeyService.get_api_key_by_id(db, key_id)
        
        if not api_key:
            raise HTTPException(status_code=404, detail="API key not found")
        
        # Check permissions
        if not is_admin and api_key.user_id != current_user.get("id"):
            raise HTTPException(status_code=403, detail="Access denied")
        
        return APIKeyInfo(**api_key.to_dict())
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to get API key", error=str(e), key_id=str(key_id))
        raise HTTPException(status_code=500, detail="Failed to get API key")


@router.patch("/{key_id}", response_model=APIKeyInfo)
async def update_api_key(
    key_id: UUID,
    request: UpdateAPIKeyRequest,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Update API key settings."""
    is_admin = current_user.get("is_admin", False)
    
    try:
        # Get existing key
        api_key = await APIKeyService.get_api_key_by_id(db, key_id)
        
        if not api_key:
            raise HTTPException(status_code=404, detail="API key not found")
        
        # Check permissions
        if not is_admin and api_key.user_id != current_user.get("id"):
            raise HTTPException(status_code=403, detail="Access denied")
        
        # Prepare updates
        updates = {}
        if request.name is not None:
            updates["name"] = request.name
        if request.description is not None:
            updates["description"] = request.description
        if request.max_concurrent_jobs is not None:
            updates["max_concurrent_jobs"] = request.max_concurrent_jobs
        if request.monthly_limit_minutes is not None:
            updates["monthly_limit_minutes"] = request.monthly_limit_minutes
        if request.is_active is not None:
            updates["is_active"] = request.is_active
        
        if not updates:
            # No changes requested
            return APIKeyInfo(**api_key.to_dict())
        
        # Update the key
        updated_key = await APIKeyService.update_api_key(db, key_id, updates)
        
        logger.info(
            "API key updated",
            key_id=str(key_id),
            updates=updates,
            updated_by=current_user.get("id"),
        )
        
        return APIKeyInfo(**updated_key.to_dict())
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to update API key", error=str(e), key_id=str(key_id))
        raise HTTPException(status_code=500, detail="Failed to update API key")


@router.post("/{key_id}/revoke", response_model=APIKeyInfo)
async def revoke_api_key(
    key_id: UUID,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Revoke an API key (permanently disable it)."""
    is_admin = current_user.get("is_admin", False)
    
    try:
        # Get existing key
        api_key = await APIKeyService.get_api_key_by_id(db, key_id)
        
        if not api_key:
            raise HTTPException(status_code=404, detail="API key not found")
        
        # Check permissions
        if not is_admin and api_key.user_id != current_user.get("id"):
            raise HTTPException(status_code=403, detail="Access denied")
        
        if api_key.revoked_at:
            raise HTTPException(status_code=400, detail="API key is already revoked")
        
        # Revoke the key
        revoked_key = await APIKeyService.revoke_api_key(
            db, key_id, revoked_by=current_user.get("id")
        )
        
        logger.info(
            "API key revoked",
            key_id=str(key_id),
            revoked_by=current_user.get("id"),
        )
        
        return APIKeyInfo(**revoked_key.to_dict())
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to revoke API key", error=str(e), key_id=str(key_id))
        raise HTTPException(status_code=500, detail="Failed to revoke API key")


@router.post("/{key_id}/extend", response_model=APIKeyInfo)
async def extend_api_key_expiry(
    key_id: UUID,
    additional_days: int = Query(..., ge=1, le=3650, description="Days to extend expiry"),
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Extend API key expiry date."""
    is_admin = current_user.get("is_admin", False)
    
    try:
        # Get existing key
        api_key = await APIKeyService.get_api_key_by_id(db, key_id)
        
        if not api_key:
            raise HTTPException(status_code=404, detail="API key not found")
        
        # Check permissions
        if not is_admin and api_key.user_id != current_user.get("id"):
            raise HTTPException(status_code=403, detail="Access denied")
        
        if api_key.revoked_at:
            raise HTTPException(status_code=400, detail="Cannot extend revoked API key")
        
        # Extend the key
        extended_key = await APIKeyService.extend_api_key_expiry(
            db, key_id, additional_days
        )
        
        logger.info(
            "API key expiry extended",
            key_id=str(key_id),
            additional_days=additional_days,
            extended_by=current_user.get("id"),
        )
        
        return APIKeyInfo(**extended_key.to_dict())
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to extend API key", error=str(e), key_id=str(key_id))
        raise HTTPException(status_code=500, detail="Failed to extend API key")


@router.get("/{key_id}/usage", response_model=dict)
async def get_api_key_usage(
    key_id: UUID,
    days: int = Query(30, ge=1, le=365, description="Number of days to analyze"),
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get usage statistics for an API key."""
    is_admin = current_user.get("is_admin", False)
    
    try:
        # Get existing key
        api_key = await APIKeyService.get_api_key_by_id(db, key_id)
        
        if not api_key:
            raise HTTPException(status_code=404, detail="API key not found")
        
        # Check permissions
        if not is_admin and api_key.user_id != current_user.get("id"):
            raise HTTPException(status_code=403, detail="Access denied")
        
        # Get usage stats
        usage_stats = await APIKeyService.get_usage_stats(
            db, key_id=key_id, days=days
        )
        
        return usage_stats
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to get usage stats", error=str(e), key_id=str(key_id))
        raise HTTPException(status_code=500, detail="Failed to get usage statistics")