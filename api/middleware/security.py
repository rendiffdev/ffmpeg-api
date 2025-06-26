"""
Security middleware for API protection
"""
from typing import Callable
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response
from starlette.types import ASGIApp


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


class RateLimitMiddleware(BaseHTTPMiddleware):
    """
    Simple rate limiting middleware for additional protection.
    Note: Primary rate limiting is handled by KrakenD API Gateway.
    """
    
    def __init__(
        self,
        app: ASGIApp,
        calls: int = 1000,
        period: int = 3600,  # 1 hour
        enabled: bool = True,
    ):
        super().__init__(app)
        self.calls = calls
        self.period = period
        self.enabled = enabled
        self.clients = {}  # Simple in-memory store (use Redis in production)
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Apply rate limiting based on client IP."""
        if not self.enabled:
            return await call_next(request)
        
        # Get client IP
        client_ip = request.client.host
        if "X-Forwarded-For" in request.headers:
            client_ip = request.headers["X-Forwarded-For"].split(",")[0].strip()
        
        # Simple rate limiting logic (in production, use Redis)
        import time
        current_time = time.time()
        
        # Clean old entries (simple cleanup)
        self.clients = {
            ip: data for ip, data in self.clients.items()
            if current_time - data["window_start"] < self.period
        }
        
        # Check rate limit
        if client_ip in self.clients:
            client_data = self.clients[client_ip]
            if current_time - client_data["window_start"] < self.period:
                if client_data["requests"] >= self.calls:
                    from starlette.responses import JSONResponse
                    return JSONResponse(
                        status_code=429,
                        content={
                            "error": {
                                "code": "RATE_LIMIT_EXCEEDED",
                                "message": f"Rate limit exceeded. Maximum {self.calls} requests per hour.",
                                "type": "RateLimitError"
                            }
                        }
                    )
                client_data["requests"] += 1
            else:
                # Reset window
                self.clients[client_ip] = {
                    "requests": 1,
                    "window_start": current_time
                }
        else:
            # New client
            self.clients[client_ip] = {
                "requests": 1,
                "window_start": current_time
            }
        
        return await call_next(request)