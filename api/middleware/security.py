"""
Security middleware for API protection
"""
import time
import hashlib
import hmac
import json
from typing import Callable, Dict, Set, Optional
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response, JSONResponse
from starlette.types import ASGIApp
import structlog

logger = structlog.get_logger()


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """
    Adds security headers to all responses to protect against common vulnerabilities.
    """
    
    def __init__(
        self,
        app: ASGIApp,
        csp_policy: str = "default-src 'self'",
        hsts_max_age: int = 31536000,
        enable_hsts: bool = True,
        enable_nosniff: bool = True,
        enable_xss_protection: bool = True,
        enable_frame_options: bool = True,
        frame_options: str = "DENY",
    ):
        super().__init__(app)
        self.csp_policy = csp_policy
        self.hsts_max_age = hsts_max_age
        self.enable_hsts = enable_hsts
        self.enable_nosniff = enable_nosniff
        self.enable_xss_protection = enable_xss_protection
        self.enable_frame_options = enable_frame_options
        self.frame_options = frame_options

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Add security headers to response."""
        response = await call_next(request)
        
        # Content Security Policy
        if self.csp_policy:
            response.headers["Content-Security-Policy"] = self.csp_policy
        
        # Prevent MIME type sniffing
        if self.enable_nosniff:
            response.headers["X-Content-Type-Options"] = "nosniff"
        
        # Prevent clickjacking
        if self.enable_frame_options:
            response.headers["X-Frame-Options"] = self.frame_options
        
        # XSS Protection (legacy but still useful)
        if self.enable_xss_protection:
            response.headers["X-XSS-Protection"] = "1; mode=block"
        
        # HTTP Strict Transport Security (only for HTTPS)
        if self.enable_hsts and request.url.scheme == "https":
            response.headers["Strict-Transport-Security"] = f"max-age={self.hsts_max_age}; includeSubDomains"
        
        # Referrer Policy
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        
        # Permissions Policy (Feature Policy successor)
        response.headers["Permissions-Policy"] = "geolocation=(), microphone=(), camera=()"
        
        return response


class APIKeyQuota:
    """API Key quota configuration."""
    def __init__(self, calls_per_hour: int = 1000, calls_per_day: int = 10000, 
                 max_concurrent_jobs: int = 5, max_file_size_mb: int = 1000):
        self.calls_per_hour = calls_per_hour
        self.calls_per_day = calls_per_day
        self.max_concurrent_jobs = max_concurrent_jobs
        self.max_file_size_mb = max_file_size_mb


class RateLimitMiddleware(BaseHTTPMiddleware):
    """
    Enhanced rate limiting middleware with API key quotas.
    """
    
    def __init__(
        self,
        app: ASGIApp,
        calls: int = 1000,
        period: int = 3600,  # 1 hour
        enabled: bool = True,
        redis_client = None,  # Redis client for distributed rate limiting
    ):
        super().__init__(app)
        self.calls = calls
        self.period = period
        self.enabled = enabled
        self.redis_client = redis_client
        self.clients = {}  # Fallback in-memory store
        
        # Default quotas for different API key tiers
        self.default_quotas = {
            'free': APIKeyQuota(calls_per_hour=100, calls_per_day=1000, max_concurrent_jobs=2, max_file_size_mb=100),
            'basic': APIKeyQuota(calls_per_hour=500, calls_per_day=5000, max_concurrent_jobs=5, max_file_size_mb=500),
            'premium': APIKeyQuota(calls_per_hour=2000, calls_per_day=20000, max_concurrent_jobs=10, max_file_size_mb=2000),
            'enterprise': APIKeyQuota(calls_per_hour=10000, calls_per_day=100000, max_concurrent_jobs=50, max_file_size_mb=10000)
        }
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Apply enhanced rate limiting with API key quotas."""
        if not self.enabled:
            return await call_next(request)
        
        # Get client identifier (IP + API key if available)
        client_ip = request.client.host
        if "X-Forwarded-For" in request.headers:
            client_ip = request.headers["X-Forwarded-For"].split(",")[0].strip()
        
        api_key = request.headers.get("X-API-Key") or request.query_params.get("api_key")
        client_id = f"{client_ip}:{api_key}" if api_key else client_ip
        
        # Get appropriate quota limits
        quota = await self._get_client_quota(api_key)
        
        import time
        current_time = time.time()
        hour_key = f"{client_id}:hour:{int(current_time // 3600)}"
        day_key = f"{client_id}:day:{int(current_time // 86400)}"
        
        # Use Redis for distributed rate limiting if available
        if self.redis_client:
            try:
                # Check hourly limit
                hourly_count = await self.redis_client.get(hour_key) or 0
                daily_count = await self.redis_client.get(day_key) or 0
                
                hourly_count = int(hourly_count)
                daily_count = int(daily_count)
                
                # Check limits
                if hourly_count >= quota.calls_per_hour:
                    return self._rate_limit_response(quota.calls_per_hour, "hour", hourly_count)
                
                if daily_count >= quota.calls_per_day:
                    return self._rate_limit_response(quota.calls_per_day, "day", daily_count)
                
                # Increment counters
                await self.redis_client.incr(hour_key)
                await self.redis_client.expire(hour_key, 3600)  # 1 hour TTL
                await self.redis_client.incr(day_key)
                await self.redis_client.expire(day_key, 86400)  # 1 day TTL
                
            except Exception as e:
                # Fall back to in-memory if Redis fails
                import structlog
                logger = structlog.get_logger()
                logger.warning("Redis rate limiting failed, using fallback", error=str(e))
                return await self._fallback_rate_limiting(client_id, quota, current_time, call_next, request)
        else:
            # Use in-memory fallback
            return await self._fallback_rate_limiting(client_id, quota, current_time, call_next, request)
        
        # Add rate limit headers
        response = await call_next(request)
        response.headers["X-RateLimit-Limit-Hour"] = str(quota.calls_per_hour)
        response.headers["X-RateLimit-Limit-Day"] = str(quota.calls_per_day)
        response.headers["X-RateLimit-Remaining-Hour"] = str(max(0, quota.calls_per_hour - hourly_count - 1))
        response.headers["X-RateLimit-Remaining-Day"] = str(max(0, quota.calls_per_day - daily_count - 1))
        
        return response
    
    async def _get_client_quota(self, api_key: str = None) -> APIKeyQuota:
        """Get quota configuration for client based on API key tier."""
        if not api_key:
            return self.default_quotas['free']
        
        # In production, look up API key tier from database
        # For now, return based on key prefix or default to basic
        if api_key.startswith('ent_'):
            return self.default_quotas['enterprise']
        elif api_key.startswith('prem_'):
            return self.default_quotas['premium']
        elif api_key.startswith('basic_'):
            return self.default_quotas['basic']
        else:
            return self.default_quotas['basic']  # Default for unknown keys
    
    def _rate_limit_response(self, limit: int, period: str, current_count: int):
        """Create rate limit exceeded response."""
        from starlette.responses import JSONResponse
        return JSONResponse(
            status_code=429,
            content={
                "error": {
                    "code": "RATE_LIMIT_EXCEEDED",
                    "message": f"Rate limit exceeded. Maximum {limit} requests per {period}.",
                    "type": "RateLimitError",
                    "limit": limit,
                    "period": period,
                    "current_usage": current_count
                }
            },
            headers={
                f"X-RateLimit-Limit-{period.title()}": str(limit),
                f"X-RateLimit-Remaining-{period.title()}": "0",
                "Retry-After": "3600" if period == "hour" else "86400"
            }
        )
    
    async def _fallback_rate_limiting(self, client_id: str, quota: APIKeyQuota, 
                                    current_time: float, call_next: Callable, request: Request):
        """Fallback in-memory rate limiting when Redis is unavailable."""
        # Clean old entries
        self.clients = {
            cid: data for cid, data in self.clients.items()
            if current_time - data["window_start"] < self.period
        }
        
        # Check rate limit (simplified to hourly only for fallback)
        if client_id in self.clients:
            client_data = self.clients[client_id]
            if current_time - client_data["window_start"] < self.period:
                if client_data["requests"] >= quota.calls_per_hour:
                    return self._rate_limit_response(quota.calls_per_hour, "hour", client_data["requests"])
                client_data["requests"] += 1
            else:
                # Reset window
                self.clients[client_id] = {
                    "requests": 1,
                    "window_start": current_time
                }
        else:
            # New client
            self.clients[client_id] = {
                "requests": 1,
                "window_start": current_time
            }
        
        return await call_next(request)


class InputSanitizationMiddleware(BaseHTTPMiddleware):
    """Middleware for sanitizing and validating input data."""
    
    def __init__(self, app: ASGIApp, max_body_size: int = 100 * 1024 * 1024):  # 100MB default
        super().__init__(app)
        self.max_body_size = max_body_size
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Sanitize request data."""
        try:
            # Check content length
            content_length = request.headers.get('content-length')
            if content_length and int(content_length) > self.max_body_size:
                return JSONResponse(
                    status_code=413,
                    content={
                        "error": {
                            "code": "PAYLOAD_TOO_LARGE",
                            "message": f"Request body too large. Maximum size: {self.max_body_size} bytes",
                            "type": "RequestError"
                        }
                    }
                )
            
            # Validate Content-Type for POST/PUT requests
            if request.method in ['POST', 'PUT', 'PATCH']:
                content_type = request.headers.get('content-type', '')
                if not content_type.startswith(('application/json', 'multipart/form-data', 'application/x-www-form-urlencoded')):
                    return JSONResponse(
                        status_code=415,
                        content={
                            "error": {
                                "code": "UNSUPPORTED_MEDIA_TYPE",
                                "message": "Unsupported media type",
                                "type": "RequestError"
                            }
                        }
                    )
            
            return await call_next(request)
            
        except Exception as e:
            logger.error("Input sanitization failed", error=str(e))
            return JSONResponse(
                status_code=400,
                content={
                    "error": {
                        "code": "BAD_REQUEST",
                        "message": "Invalid request format",
                        "type": "RequestError"
                    }
                }
            )


class SecurityAuditMiddleware(BaseHTTPMiddleware):
    """Middleware for security auditing and monitoring."""
    
    def __init__(self, app: ASGIApp, log_suspicious_activity: bool = True):
        super().__init__(app)
        self.log_suspicious_activity = log_suspicious_activity
        self.suspicious_patterns = [
            r'\.\./',  # Directory traversal
            r'<script',  # XSS attempts
            r'union\s+select',  # SQL injection
            r'javascript:',  # XSS
            r'eval\s*\(',  # Code injection
            r'/etc/passwd',  # File access attempts
        ]
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Monitor and audit security events."""
        start_time = time.time()
        
        # Check for suspicious patterns
        if self.log_suspicious_activity:
            self._check_for_suspicious_activity(request)
        
        response = await call_next(request)
        
        # Log security events
        processing_time = time.time() - start_time
        
        if processing_time > 30:  # Slow request detection
            logger.warning(
                "Slow request detected",
                path=request.url.path,
                processing_time=processing_time,
                client_ip=self._get_client_ip(request)
            )
        
        if response.status_code == 401:
            logger.warning(
                "Authentication failed",
                path=request.url.path,
                client_ip=self._get_client_ip(request)
            )
        
        return response
    
    def _check_for_suspicious_activity(self, request: Request):
        """Check for suspicious patterns in the request."""
        import re
        
        # Check URL path
        for pattern in self.suspicious_patterns:
            if re.search(pattern, request.url.path, re.IGNORECASE):
                logger.warning(
                    "Suspicious pattern in URL",
                    pattern=pattern,
                    url=request.url.path,
                    client_ip=self._get_client_ip(request)
                )
    
    def _get_client_ip(self, request: Request) -> str:
        """Get client IP address."""
        forwarded_for = request.headers.get('x-forwarded-for')
        if forwarded_for:
            return forwarded_for.split(',')[0].strip()
        return request.client.host if request.client else 'unknown'