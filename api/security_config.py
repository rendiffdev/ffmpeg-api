"""
Security configuration and setup for FFmpeg API
"""
import os
from typing import Dict, Any, List
from fastapi import FastAPI, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware

from api.middleware.security import (
    SecurityHeadersMiddleware,
    RateLimitMiddleware,
    InputSanitizationMiddleware,
    SecurityAuditMiddleware
)
from api.utils.error_handler import (
    ProductionErrorHandler,
    ErrorLevel,
    set_debug_mode
)
from api.utils.validators import SecurityError
import structlog

logger = structlog.get_logger()


class SecurityConfig:
    """Central security configuration for the API."""
    
    def __init__(self):
        # Environment-based settings
        self.debug_mode = os.getenv('DEBUG', 'false').lower() == 'true'
        self.environment = os.getenv('ENVIRONMENT', 'production')
        
        # Rate limiting settings
        self.rate_limit_enabled = os.getenv('RATE_LIMIT_ENABLED', 'true').lower() == 'true'
        self.rate_limit_calls = int(os.getenv('RATE_LIMIT_CALLS', '1000'))
        self.rate_limit_period = int(os.getenv('RATE_LIMIT_PERIOD', '3600'))
        
        # Security headers settings
        self.csp_policy = os.getenv(
            'CSP_POLICY', 
            "default-src 'self'; script-src 'self'; object-src 'none';"
        )
        self.hsts_max_age = int(os.getenv('HSTS_MAX_AGE', '31536000'))
        
        # Input validation settings
        self.max_body_size = int(os.getenv('MAX_BODY_SIZE', str(100 * 1024 * 1024)))  # 100MB
        
        # CORS settings
        self.cors_origins = os.getenv('CORS_ORIGINS', '').split(',') if os.getenv('CORS_ORIGINS') else ['*']
        self.cors_allow_credentials = os.getenv('CORS_ALLOW_CREDENTIALS', 'false').lower() == 'true'
        
        # Error handling
        self.error_handler = ProductionErrorHandler(debug_mode=self.debug_mode)
        set_debug_mode(self.debug_mode)
        
        logger.info("Security configuration initialized", 
                   debug_mode=self.debug_mode,
                   environment=self.environment)
    
    def configure_app(self, app: FastAPI) -> FastAPI:
        """Apply all security configurations to the FastAPI app."""
        
        # Add security middleware in correct order (reverse order of execution)
        
        # 1. Security audit middleware (outermost - logs everything)
        app.add_middleware(
            SecurityAuditMiddleware,
            log_suspicious_activity=True
        )
        
        # 2. Rate limiting middleware
        if self.rate_limit_enabled:
            app.add_middleware(
                RateLimitMiddleware,
                calls=self.rate_limit_calls,
                period=self.rate_limit_period,
                enabled=True
            )
        
        # 3. Input sanitization middleware
        app.add_middleware(
            InputSanitizationMiddleware,
            max_body_size=self.max_body_size
        )
        
        # 4. Security headers middleware
        app.add_middleware(
            SecurityHeadersMiddleware,
            csp_policy=self.csp_policy,
            hsts_max_age=self.hsts_max_age,
            enable_hsts=True,
            enable_nosniff=True,
            enable_xss_protection=True,
            enable_frame_options=True
        )
        
        # 5. CORS middleware (innermost)
        if self.cors_origins:
            app.add_middleware(
                CORSMiddleware,
                allow_origins=self.cors_origins,
                allow_credentials=self.cors_allow_credentials,
                allow_methods=["GET", "POST", "PUT", "DELETE"],
                allow_headers=["*"],
            )
        
        # Add global exception handlers
        self._add_exception_handlers(app)
        
        logger.info("Security middleware configured successfully")
        return app
    
    def _add_exception_handlers(self, app: FastAPI):
        """Add global exception handlers with proper error sanitization."""
        
        @app.exception_handler(SecurityError)
        async def security_error_handler(request: Request, exc: SecurityError):
            """Handle security violations."""
            error_response = self.error_handler.sanitize_error_message(exc, ErrorLevel.HIGH)
            
            # Log security incident
            logger.error(
                "Security violation",
                error=str(exc),
                path=request.url.path,
                method=request.method,
                client_ip=self._get_client_ip(request),
                user_agent=request.headers.get('user-agent', 'Unknown')
            )
            
            from fastapi.responses import JSONResponse
            return JSONResponse(
                status_code=403,
                content=error_response
            )
        
        @app.exception_handler(ValueError)
        async def validation_error_handler(request: Request, exc: ValueError):
            """Handle validation errors."""
            error_response = self.error_handler.sanitize_error_message(exc, ErrorLevel.LOW)
            
            from fastapi.responses import JSONResponse
            return JSONResponse(
                status_code=400,
                content=error_response
            )
        
        @app.exception_handler(HTTPException)
        async def http_exception_handler(request: Request, exc: HTTPException):
            """Handle HTTP exceptions."""
            error_response = self.error_handler.handle_http_exception(
                exc.status_code, 
                exc.detail
            )
            
            from fastapi.responses import JSONResponse
            return JSONResponse(
                status_code=exc.status_code,
                content=error_response
            )
        
        @app.exception_handler(Exception)
        async def general_exception_handler(request: Request, exc: Exception):
            """Handle all other exceptions."""
            error_response = self.error_handler.sanitize_error_message(exc, ErrorLevel.HIGH)
            
            # Log unexpected errors
            logger.error(
                "Unexpected error",
                error=str(exc),
                error_type=type(exc).__name__,
                path=request.url.path,
                method=request.method
            )
            
            from fastapi.responses import JSONResponse
            return JSONResponse(
                status_code=500,
                content=error_response
            )
    
    def _get_client_ip(self, request: Request) -> str:
        """Get client IP address."""
        forwarded_for = request.headers.get('x-forwarded-for')
        if forwarded_for:
            return forwarded_for.split(',')[0].strip()
        return request.client.host if request.client else 'unknown'
    
    def get_security_headers(self) -> Dict[str, str]:
        """Get recommended security headers for manual application."""
        return {
            "X-Content-Type-Options": "nosniff",
            "X-Frame-Options": "DENY",
            "X-XSS-Protection": "1; mode=block",
            "Strict-Transport-Security": f"max-age={self.hsts_max_age}; includeSubDomains",
            "Content-Security-Policy": self.csp_policy,
            "Referrer-Policy": "strict-origin-when-cross-origin",
            "Permissions-Policy": "geolocation=(), microphone=(), camera=()"
        }
    
    def validate_api_request(self, request_data: Dict[str, Any]) -> Dict[str, Any]:
        """Validate API request data with security checks."""
        from api.utils.validators import validate_operations, validate_secure_path
        
        validated_data = {}
        
        # Validate required fields
        if 'input_path' not in request_data:
            raise ValueError("Missing required field: input_path")
        
        if 'operations' not in request_data:
            raise ValueError("Missing required field: operations")
        
        # Validate input path
        try:
            validated_data['input_path'] = validate_secure_path(request_data['input_path'])
        except SecurityError as e:
            raise SecurityError(f"Invalid input path: {e}")
        
        # Validate output path if provided
        if 'output_path' in request_data:
            try:
                validated_data['output_path'] = validate_secure_path(request_data['output_path'])
            except SecurityError as e:
                raise SecurityError(f"Invalid output path: {e}")
        
        # Validate operations
        try:
            validated_data['operations'] = validate_operations(request_data['operations'])
        except (ValueError, SecurityError) as e:
            raise ValueError(f"Invalid operations: {e}")
        
        # Validate optional fields
        if 'options' in request_data:
            if not isinstance(request_data['options'], dict):
                raise ValueError("Options must be a dictionary")
            validated_data['options'] = request_data['options']
        
        return validated_data


# Global security configuration instance
security_config = SecurityConfig()


def apply_security_to_app(app: FastAPI) -> FastAPI:
    """Apply comprehensive security configuration to FastAPI app."""
    return security_config.configure_app(app)


def validate_request_data(data: Dict[str, Any]) -> Dict[str, Any]:
    """Validate request data using security configuration."""
    return security_config.validate_api_request(data)


def get_security_info() -> Dict[str, Any]:
    """Get current security configuration information."""
    return {
        "security_enabled": True,
        "rate_limiting": security_config.rate_limit_enabled,
        "input_validation": True,
        "error_sanitization": True,
        "security_headers": True,
        "audit_logging": True,
        "debug_mode": security_config.debug_mode,
        "environment": security_config.environment,
        "max_body_size": security_config.max_body_size,
        "rate_limit_calls": security_config.rate_limit_calls,
        "rate_limit_period": security_config.rate_limit_period
    }