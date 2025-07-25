"""
FastAPI dependencies for authentication, database, etc.
"""
from typing import Optional, Annotated, AsyncGenerator

from fastapi import Depends, HTTPException, Header, Request
from sqlalchemy.ext.asyncio import AsyncSession
import structlog

from api.config import settings
from api.models.database import get_session

logger = structlog.get_logger()


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Get database session dependency."""
    async for session in get_session():
        yield session


async def get_api_key(
    x_api_key: Annotated[Optional[str], Header()] = None,
    authorization: Annotated[Optional[str], Header()] = None,
) -> Optional[str]:
    """Extract API key from headers."""
    if x_api_key:
        return x_api_key
    
    if authorization and authorization.startswith("Bearer "):
        return authorization[7:]
    
    return None


async def require_api_key(
    request: Request,
    api_key: Optional[str] = Depends(get_api_key),
    db: AsyncSession = Depends(get_db),
) -> str:
    """Require valid API key for endpoint access."""
    if not settings.ENABLE_API_KEYS:
        return "anonymous"
    
    if not api_key:
        raise HTTPException(
            status_code=401,
            detail="API key required",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # Validate API key against database
    from api.services.api_key import APIKeyService
    
    api_key_model = await APIKeyService.validate_api_key(
        db, api_key, update_usage=True
    )
    
    if not api_key_model:
        logger.warning(
            "Invalid API key attempted",
            api_key_prefix=api_key[:8] + "..." if len(api_key) > 8 else api_key,
            client_ip=request.client.host,
        )
        raise HTTPException(
            status_code=401,
            detail="Invalid API key",
        )
    
    # Check IP whitelist if enabled
    if settings.ENABLE_IP_WHITELIST:
        import ipaddress
        client_ip = request.client.host
        
        # Validate client IP against CIDR ranges
        client_ip_obj = ipaddress.ip_address(client_ip)
        allowed = False
        
        for allowed_range in settings.ip_whitelist_parsed:
            try:
                if client_ip_obj in ipaddress.ip_network(allowed_range, strict=False):
                    allowed = True
                    break
            except (ipaddress.AddressValueError, ipaddress.NetmaskValueError):
                # Fallback to string comparison for invalid CIDR
                if client_ip.startswith(allowed_range):
                    allowed = True
                    break
        
        if not allowed:
            logger.warning(
                "IP not in whitelist",
                client_ip=client_ip,
                api_key_id=str(api_key_model.id),
                user_id=api_key_model.user_id,
            )
            raise HTTPException(
                status_code=403,
                detail="IP address not authorized",
            )
    
    # Store API key model in request state for other endpoints
    request.state.api_key_model = api_key_model
    
    return api_key


async def get_current_user(
    request: Request,
    api_key: str = Depends(require_api_key),
) -> dict:
    """Get current user from validated API key."""
    # Get API key model from request state (set by require_api_key)
    api_key_model = getattr(request.state, 'api_key_model', None)
    
    if not api_key_model:
        # Fallback for anonymous access
        return {
            "id": "anonymous",
            "api_key": api_key,
            "role": "anonymous",
            "quota": {
                "concurrent_jobs": 1,
                "monthly_minutes": 100,
            },
        }
    
    return {
        "id": api_key_model.user_id or f"api_key_{api_key_model.id}",
        "api_key_id": str(api_key_model.id),
        "api_key": api_key,
        "name": api_key_model.name,
        "organization": api_key_model.organization,
        "role": "admin" if api_key_model.is_admin else "user",
        "quota": {
            "concurrent_jobs": api_key_model.max_concurrent_jobs,
            "monthly_minutes": api_key_model.monthly_limit_minutes,
        },
        "usage": {
            "total_requests": api_key_model.total_requests,
            "last_used_at": api_key_model.last_used_at.isoformat() if api_key_model.last_used_at else None,
        },
        "expires_at": api_key_model.expires_at.isoformat() if api_key_model.expires_at else None,
        "is_admin": api_key_model.is_admin,
    }