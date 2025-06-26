"""
Comprehensive error handling utilities for Rendiff API
"""
import traceback
from typing import Dict, Any, Optional
from fastapi import HTTPException, Request
from fastapi.responses import JSONResponse
import structlog

logger = structlog.get_logger()

class RendiffError(Exception):
    """Base exception for Rendiff-specific errors."""
    
    def __init__(self, message: str, code: str = "RENDIFF_ERROR", status_code: int = 500):
        self.message = message
        self.code = code
        self.status_code = status_code
        super().__init__(message)

class StorageError(RendiffError):
    """Storage-related errors."""
    
    def __init__(self, message: str, backend: str = None):
        self.backend = backend
        super().__init__(message, "STORAGE_ERROR", 500)

class ProcessingError(RendiffError):
    """Video processing errors."""
    
    def __init__(self, message: str, job_id: str = None):
        self.job_id = job_id
        super().__init__(message, "PROCESSING_ERROR", 500)

class ValidationError(RendiffError):
    """Input validation errors."""
    
    def __init__(self, message: str, field: str = None):
        self.field = field
        super().__init__(message, "VALIDATION_ERROR", 400)

class AuthenticationError(RendiffError):
    """Authentication errors."""
    
    def __init__(self, message: str = "Authentication required"):
        super().__init__(message, "AUTH_ERROR", 401)

class AuthorizationError(RendiffError):
    """Authorization errors."""
    
    def __init__(self, message: str = "Insufficient permissions"):
        super().__init__(message, "AUTHZ_ERROR", 403)

class RateLimitError(RendiffError):
    """Rate limiting errors."""
    
    def __init__(self, message: str = "Rate limit exceeded"):
        super().__init__(message, "RATE_LIMIT_ERROR", 429)

class ResourceError(RendiffError):
    """Resource-related errors."""
    
    def __init__(self, message: str, resource_type: str = None):
        self.resource_type = resource_type
        super().__init__(message, "RESOURCE_ERROR", 500)

async def rendiff_exception_handler(request: Request, exc: RendiffError):
    """Handle Rendiff-specific exceptions."""
    logger.error(
        "Rendiff error",
        error_code=exc.code,
        error_message=exc.message,
        path=request.url.path,
        method=request.method,
        status_code=exc.status_code
    )
    
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": {
                "code": exc.code,
                "message": exc.message,
                "type": type(exc).__name__,
                "path": str(request.url.path),
                "timestamp": logger._context.get("timestamp", "")
            }
        }
    )

async def validation_exception_handler(request: Request, exc: Exception):
    """Handle validation exceptions."""
    logger.warning(
        "Validation error",
        error_message=str(exc),
        path=request.url.path,
        method=request.method
    )
    
    return JSONResponse(
        status_code=422,
        content={
            "error": {
                "code": "VALIDATION_ERROR",
                "message": "Input validation failed",
                "details": str(exc),
                "path": str(request.url.path)
            }
        }
    )

async def http_exception_handler(request: Request, exc: HTTPException):
    """Enhanced HTTP exception handler."""
    logger.warning(
        "HTTP error",
        status_code=exc.status_code,
        detail=exc.detail,
        path=request.url.path,
        method=request.method
    )
    
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": {
                "code": f"HTTP_{exc.status_code}",
                "message": exc.detail,
                "status_code": exc.status_code,
                "path": str(request.url.path)
            }
        }
    )

async def general_exception_handler(request: Request, exc: Exception):
    """Handle unexpected exceptions."""
    tb = traceback.format_exc()
    
    logger.error(
        "Unhandled exception",
        exc_type=type(exc).__name__,
        exc_message=str(exc),
        traceback=tb,
        path=request.url.path,
        method=request.method
    )
    
    # Don't expose internal details in production
    message = "An internal error occurred"
    details = None
    
    # In development, show more details
    try:
        from api.config import settings
        if settings.DEBUG:
            message = str(exc)
            details = tb
    except:
        pass
    
    return JSONResponse(
        status_code=500,
        content={
            "error": {
                "code": "INTERNAL_ERROR",
                "message": message,
                "type": type(exc).__name__,
                "path": str(request.url.path),
                "details": details
            }
        }
    )

def safe_execute(func, *args, error_msg: str = "Operation failed", **kwargs):
    """Safely execute a function with error handling."""
    try:
        return func(*args, **kwargs)
    except Exception as e:
        logger.error(f"{error_msg}: {e}", exc_info=True)
        raise RendiffError(f"{error_msg}: {str(e)}")

async def safe_execute_async(func, *args, error_msg: str = "Operation failed", **kwargs):
    """Safely execute an async function with error handling."""
    try:
        return await func(*args, **kwargs)
    except Exception as e:
        logger.error(f"{error_msg}: {e}", exc_info=True)
        raise RendiffError(f"{error_msg}: {str(e)}")

def error_context(operation: str, **context):
    """Context manager for error handling with additional context."""
    class ErrorContext:
        def __init__(self, operation: str, **context):
            self.operation = operation
            self.context = context
        
        def __enter__(self):
            return self
        
        def __exit__(self, exc_type, exc_val, exc_tb):
            if exc_type:
                logger.error(
                    f"Error in {self.operation}",
                    exc_type=exc_type.__name__,
                    exc_message=str(exc_val),
                    **self.context
                )
            return False  # Don't suppress the exception
    
    return ErrorContext(operation, **context)

def validate_file_type(filename: str, allowed_types: list) -> bool:
    """Validate file type based on extension."""
    if not filename:
        raise ValidationError("Filename is required")
    
    file_ext = filename.lower().split('.')[-1]
    if file_ext not in allowed_types:
        raise ValidationError(
            f"File type '{file_ext}' not allowed. Allowed types: {', '.join(allowed_types)}",
            field="filename"
        )
    
    return True

def validate_file_size(size: int, max_size: int) -> bool:
    """Validate file size."""
    if size > max_size:
        raise ValidationError(
            f"File size {size} bytes exceeds maximum allowed size {max_size} bytes",
            field="file_size"
        )
    
    return True

def format_error_response(error: Exception, request_id: str = None) -> Dict[str, Any]:
    """Format error response consistently."""
    if isinstance(error, RendiffError):
        return {
            "error": {
                "code": error.code,
                "message": error.message,
                "type": type(error).__name__,
                "request_id": request_id
            }
        }
    
    return {
        "error": {
            "code": "UNKNOWN_ERROR",
            "message": str(error),
            "type": type(error).__name__,
            "request_id": request_id
        }
    }