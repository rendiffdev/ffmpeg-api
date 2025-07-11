"""
FastAPI dependencies for authentication, database, etc.
"""
from typing import Optional, Annotated, AsyncGenerator
import ipaddress

from fastapi import Depends, HTTPException, Header, Request
from sqlalchemy.ext.asyncio import AsyncSession
import structlog

from api.config import settings
from api.models.database import get_session
from api.models.api_key import ApiKeyUser
from api.services.api_key import ApiKeyService
from api.cache import get_cached_api_key_validation, cache_api_key_validation

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
    
    # Try to get cached validation result first
    try:
        cached_result = await get_cached_api_key_validation(api_key)
        if cached_result and cached_result.get("is_valid"):
            user_data = cached_result.get("user_data")
            if user_data:
                user = ApiKeyUser(**user_data)
            else:
                user = None
        else:
            user = None
    except Exception as e:
        logger.warning(f"Cache lookup failed for API key validation: {e}")
        user = None
    
    # If not in cache or invalid, validate against database
    if user is None:
        api_key_service = ApiKeyService(db)
        user = await api_key_service.validate_api_key(api_key)
        
        # Cache the validation result
        try:
            user_data = user.dict() if user else None
            await cache_api_key_validation(api_key, user is not None, user_data)
        except Exception as e:
            logger.warning(f"Failed to cache API key validation: {e}")
    
    if not user:
        raise HTTPException(
            status_code=401,
            detail="Invalid API key",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # Check IP whitelist if enabled
    if settings.ENABLE_IP_WHITELIST:
        client_ip = request.client.host
        if not _is_ip_whitelisted(client_ip, settings.ip_whitelist_parsed):
            logger.warning(
                "IP not in whitelist",
                client_ip=client_ip,
                api_key_prefix=user.api_key_prefix,
                user_id=user.id,
            )
            raise HTTPException(
                status_code=403,
                detail="IP address not authorized",
            )
    
    return api_key


def _is_ip_whitelisted(client_ip: str, whitelist: list[str]) -> bool:
    """Check if client IP is whitelisted using proper IP network validation."""
    try:
        client_address = ipaddress.ip_address(client_ip)
        for allowed_range in whitelist:
            try:
                # Try to parse as network range (CIDR)
                if '/' in allowed_range:
                    network = ipaddress.ip_network(allowed_range, strict=False)
                    if client_address in network:
                        return True
                else:
                    # Try to parse as single IP
                    allowed_ip = ipaddress.ip_address(allowed_range)
                    if client_address == allowed_ip:
                        return True
            except ValueError:
                # If parsing fails, fall back to string comparison for backward compatibility
                if client_ip.startswith(allowed_range):
                    return True
        return False
    except ValueError:
        # If client IP is invalid, fall back to string comparison
        return any(client_ip.startswith(ip) for ip in whitelist)


async def get_current_user(
    api_key: str = Depends(require_api_key),
    db: AsyncSession = Depends(get_db),
) -> tuple[ApiKeyUser, str]:
    """Get current user from API key."""
    if api_key == "anonymous":
        # Return anonymous user for when API keys are disabled
        return (
            ApiKeyUser(
                id="anonymous",
                api_key_id=None,
                api_key_prefix="anon",
                role="user",
                max_concurrent_jobs=settings.MAX_CONCURRENT_JOBS_PER_KEY,
                monthly_quota_minutes=10000,
                is_admin=False,
                total_jobs_created=0,
                total_minutes_processed=0,
                last_used_at=None,
            ),
            "anonymous"
        )
    
    # Get user from API key
    api_key_service = ApiKeyService(db)
    user = await api_key_service.validate_api_key(api_key)
    
    if not user:
        raise HTTPException(
            status_code=401,
            detail="Invalid API key",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    return user, api_key


async def require_admin_user(
    user_data: tuple[ApiKeyUser, str] = Depends(get_current_user),
) -> ApiKeyUser:
    """Require admin user for endpoint access."""
    user, api_key = user_data
    if not user.is_admin:
        raise HTTPException(
            status_code=403,
            detail="Admin access required",
        )
    return user