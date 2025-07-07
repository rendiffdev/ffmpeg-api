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
    
    # In production, validate against database
    # For now, accept any non-empty key
    if not api_key.strip():
        raise HTTPException(
            status_code=401,
            detail="Invalid API key",
        )
    
    # Check IP whitelist if enabled
    if settings.ENABLE_IP_WHITELIST:
        client_ip = request.client.host
        if not any(client_ip.startswith(ip) for ip in settings.ip_whitelist_parsed):
            logger.warning(
                "IP not in whitelist",
                client_ip=client_ip,
                api_key=api_key[:8] + "...",
            )
            raise HTTPException(
                status_code=403,
                detail="IP address not authorized",
            )
    
    return api_key


async def get_current_user(
    api_key: str = Depends(require_api_key),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Get current user from API key."""
    # In production, look up user from database
    # For now, return mock user
    return {
        "id": "user_123",
        "api_key": api_key,
        "role": "user",
        "quota": {
            "concurrent_jobs": settings.MAX_CONCURRENT_JOBS_PER_KEY,
            "monthly_minutes": 10000,
        },
    }