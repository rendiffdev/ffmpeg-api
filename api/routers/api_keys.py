"""
API Key management endpoints
"""
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from api.dependencies import get_db, require_admin_user
from api.models.api_key import (
    ApiKeyCreate,
    ApiKeyCreateResponse,
    ApiKeyResponse,
    ApiKeyListResponse,
    ApiKeyUpdateRequest,
    ApiKeyStatus,
    ApiKeyUser,
)
from api.services.api_key import ApiKeyService
from api.utils.error_handlers import handle_service_errors

router = APIRouter(prefix="/api/v1/admin/api-keys", tags=["API Keys"])


@router.post("/", response_model=ApiKeyCreateResponse)
async def create_api_key(
    request: ApiKeyCreate,
    db: AsyncSession = Depends(get_db),
    admin_user: ApiKeyUser = Depends(require_admin_user),
):
    """Create a new API key (admin only)."""
    try:
        service = ApiKeyService(db)
        api_key, full_key = await service.create_api_key(
            request=request,
            created_by=admin_user.id,
        )
        
        return ApiKeyCreateResponse(
            api_key=ApiKeyResponse.model_validate(api_key),
            key=full_key,
        )
    except Exception as e:
        handle_service_errors(e)


@router.get("/", response_model=ApiKeyListResponse)
async def list_api_keys(
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    status: Optional[ApiKeyStatus] = Query(None),
    owner_id: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
    admin_user: ApiKeyUser = Depends(require_admin_user),
):
    """List API keys (admin only)."""
    try:
        service = ApiKeyService(db)
        api_keys, total = await service.list_api_keys(
            page=page,
            per_page=per_page,
            status=status,
            owner_id=owner_id,
        )
        
        return ApiKeyListResponse(
            api_keys=[ApiKeyResponse.model_validate(key) for key in api_keys],
            total=total,
            page=page,
            per_page=per_page,
            has_next=page * per_page < total,
            has_prev=page > 1,
        )
    except Exception as e:
        handle_service_errors(e)


@router.get("/{key_id}", response_model=ApiKeyResponse)
async def get_api_key(
    key_id: UUID,
    db: AsyncSession = Depends(get_db),
    admin_user: ApiKeyUser = Depends(require_admin_user),
):
    """Get API key by ID (admin only)."""
    try:
        service = ApiKeyService(db)
        api_key = await service.get_api_key_by_id(key_id)
        
        if not api_key:
            raise HTTPException(status_code=404, detail="API key not found")
        
        return ApiKeyResponse.model_validate(api_key)
    except HTTPException:
        raise
    except Exception as e:
        handle_service_errors(e)


@router.put("/{key_id}", response_model=ApiKeyResponse)
async def update_api_key(
    key_id: UUID,
    request: ApiKeyUpdateRequest,
    db: AsyncSession = Depends(get_db),
    admin_user: ApiKeyUser = Depends(require_admin_user),
):
    """Update API key (admin only)."""
    try:
        service = ApiKeyService(db)
        api_key = await service.update_api_key(
            key_id=key_id,
            request=request,
            updated_by=admin_user.id,
        )
        
        return ApiKeyResponse.model_validate(api_key)
    except Exception as e:
        handle_service_errors(e)


@router.post("/{key_id}/revoke", response_model=ApiKeyResponse)
async def revoke_api_key(
    key_id: UUID,
    reason: Optional[str] = Query(None, max_length=500),
    db: AsyncSession = Depends(get_db),
    admin_user: ApiKeyUser = Depends(require_admin_user),
):
    """Revoke API key (admin only)."""
    try:
        service = ApiKeyService(db)
        api_key = await service.revoke_api_key(
            key_id=key_id,
            reason=reason,
            revoked_by=admin_user.id,
        )
        
        return ApiKeyResponse.model_validate(api_key)
    except Exception as e:
        handle_service_errors(e)


@router.delete("/{key_id}", status_code=204)
async def delete_api_key(
    key_id: UUID,
    db: AsyncSession = Depends(get_db),
    admin_user: ApiKeyUser = Depends(require_admin_user),
):
    """Delete API key permanently (admin only)."""
    try:
        service = ApiKeyService(db)
        await service.delete_api_key(key_id)
    except Exception as e:
        handle_service_errors(e)


@router.post("/cleanup-expired", response_model=dict)
async def cleanup_expired_keys(
    db: AsyncSession = Depends(get_db),
    admin_user: ApiKeyUser = Depends(require_admin_user),
):
    """Clean up expired API keys (admin only)."""
    try:
        service = ApiKeyService(db)
        count = await service.cleanup_expired_keys()
        
        return {"message": f"Cleaned up {count} expired API keys"}
    except Exception as e:
        handle_service_errors(e)