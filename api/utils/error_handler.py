"""
Production-safe error handling and message sanitization
"""
import re
import traceback
from typing import Dict, Any, Optional
from enum import Enum
import structlog

logger = structlog.get_logger()


class ErrorLevel(Enum):
    """Error severity levels"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class ProductionErrorHandler:
    """Handles error sanitization for production environments"""
    
    # Patterns that should be removed from error messages
    SENSITIVE_PATTERNS = [
        r'/[a-zA-Z0-9_\-\.]+/[a-zA-Z0-9_\-\.]+/[a-zA-Z0-9_\-\.]+',  # File paths
        r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}',  # Email addresses
        r'(?:password|secret|key|token)[\s=:]+[^\s]+',  # Credentials
        r'[A-Za-z0-9_]{32,}',  # Long tokens/hashes
        r'(?:https?://)[^\s]+',  # URLs
        r'(?:mongodb://|postgresql://|redis://)[^\s]+',  # Database URLs
        r'Bearer\s+[^\s]+',  # Bearer tokens
        r'Basic\s+[^\s]+',  # Basic auth
        r'(?:api[_-]?key|access[_-]?token)[\s=:]+[^\s]+',  # API keys
        r'(?:aws[_-]?access[_-]?key|aws[_-]?secret)[^\s]+',  # AWS credentials
    ]
    
    # Safe error messages for different error types
    SAFE_ERROR_MESSAGES = {
        'FileNotFoundError': 'Requested file not found',
        'PermissionError': 'Access denied to requested resource',
        'ConnectionError': 'Service temporarily unavailable',
        'TimeoutError': 'Request timeout - please try again',
        'ValidationError': 'Invalid input provided',
        'SecurityError': 'Security validation failed',
        'FFmpegError': 'Video processing failed',
        'FFmpegCommandError': 'Invalid processing parameters',
        'FFmpegExecutionError': 'Video processing error occurred',
        'StorageError': 'Storage operation failed',
        'AuthenticationError': 'Authentication required',
        'AuthorizationError': 'Access denied',
        'RateLimitError': 'Rate limit exceeded',
        'DatabaseError': 'Database operation failed',
        'NetworkError': 'Network connectivity issue',
        'ConfigurationError': 'Service configuration error'
    }
    
    def __init__(self, debug_mode: bool = False):
        self.debug_mode = debug_mode
        self.compiled_patterns = [re.compile(pattern, re.IGNORECASE) for pattern in self.SENSITIVE_PATTERNS]
    
    def sanitize_error_message(self, error: Exception, error_level: ErrorLevel = ErrorLevel.MEDIUM) -> Dict[str, Any]:
        """
        Sanitize error message for production use.
        
        Args:
            error: The exception to sanitize
            error_level: Severity level of the error
            
        Returns:
            Dict containing sanitized error information
        """
        error_type = type(error).__name__
        original_message = str(error)
        
        # Get safe message based on error type
        safe_message = self.SAFE_ERROR_MESSAGES.get(error_type, "An error occurred")
        
        # In debug mode, return more detailed information
        if self.debug_mode and error_level in [ErrorLevel.LOW, ErrorLevel.MEDIUM]:
            sanitized_message = self._sanitize_message_content(original_message)
            return {
                "error": {
                    "code": error_type.upper(),
                    "message": sanitized_message,
                    "type": error_type,
                    "level": error_level.value,
                    "debug_info": {
                        "original_message": sanitized_message,
                        "traceback": self._sanitize_traceback()
                    }
                }
            }
        
        # Production mode - return minimal safe information
        error_code = self._generate_error_code(error_type)
        
        result = {
            "error": {
                "code": error_code,
                "message": safe_message,
                "type": error_type,
                "level": error_level.value
            }
        }
        
        # Add helpful context for certain error types
        if error_type == 'ValidationError':
            result["error"]["details"] = "Please check your input parameters"
        elif error_type in ['RateLimitError']:
            result["error"]["details"] = "Please wait before making another request"
        elif error_type in ['AuthenticationError', 'AuthorizationError']:
            result["error"]["details"] = "Please check your credentials"
        
        # Log the actual error for debugging
        logger.error(
            "Error occurred", 
            error_type=error_type,
            error_message=original_message,
            error_level=error_level.value,
            sanitized=True
        )
        
        return result
    
    def _sanitize_message_content(self, message: str) -> str:
        """Remove sensitive information from error message content."""
        sanitized = message
        
        # Remove sensitive patterns
        for pattern in self.compiled_patterns:
            sanitized = pattern.sub('[REDACTED]', sanitized)
        
        # Remove common sensitive keywords
        sensitive_keywords = [
            'password', 'secret', 'key', 'token', 'credential',
            'username', 'email', 'phone', 'ssn', 'credit'
        ]
        
        for keyword in sensitive_keywords:
            # Replace sensitive values after keywords
            pattern = rf'{keyword}[\s=:]+[^\s]+'
            sanitized = re.sub(pattern, f'{keyword}=[REDACTED]', sanitized, flags=re.IGNORECASE)
        
        return sanitized
    
    def _sanitize_traceback(self) -> Optional[str]:
        """Get sanitized traceback information."""
        if not self.debug_mode:
            return None
        
        try:
            tb = traceback.format_exc()
            return self._sanitize_message_content(tb)
        except Exception:
            return "Traceback unavailable"
    
    def _generate_error_code(self, error_type: str) -> str:
        """Generate consistent error codes."""
        error_codes = {
            'FileNotFoundError': 'FILE_NOT_FOUND',
            'PermissionError': 'ACCESS_DENIED',
            'ConnectionError': 'CONNECTION_FAILED',
            'TimeoutError': 'REQUEST_TIMEOUT',
            'ValidationError': 'VALIDATION_FAILED',
            'SecurityError': 'SECURITY_VIOLATION',
            'FFmpegError': 'PROCESSING_FAILED',
            'FFmpegCommandError': 'INVALID_PARAMETERS',
            'FFmpegExecutionError': 'PROCESSING_ERROR',
            'StorageError': 'STORAGE_FAILED',
            'AuthenticationError': 'AUTH_REQUIRED',
            'AuthorizationError': 'ACCESS_FORBIDDEN',
            'RateLimitError': 'RATE_LIMIT_EXCEEDED',
            'DatabaseError': 'DATABASE_ERROR',
            'NetworkError': 'NETWORK_ERROR',
            'ConfigurationError': 'CONFIG_ERROR'
        }
        
        return error_codes.get(error_type, 'INTERNAL_ERROR')
    
    def handle_http_exception(self, status_code: int, detail: str = None) -> Dict[str, Any]:
        """Handle HTTP exceptions with appropriate sanitization."""
        http_errors = {
            400: {
                "code": "BAD_REQUEST",
                "message": "Invalid request format or parameters",
                "level": ErrorLevel.LOW.value
            },
            401: {
                "code": "UNAUTHORIZED",
                "message": "Authentication required",
                "level": ErrorLevel.MEDIUM.value
            },
            403: {
                "code": "FORBIDDEN",
                "message": "Access denied",
                "level": ErrorLevel.MEDIUM.value
            },
            404: {
                "code": "NOT_FOUND",
                "message": "Requested resource not found",
                "level": ErrorLevel.LOW.value
            },
            422: {
                "code": "VALIDATION_ERROR",
                "message": "Request validation failed",
                "level": ErrorLevel.LOW.value
            },
            429: {
                "code": "RATE_LIMIT_EXCEEDED",
                "message": "Too many requests",
                "level": ErrorLevel.MEDIUM.value
            },
            500: {
                "code": "INTERNAL_ERROR",
                "message": "Internal server error",
                "level": ErrorLevel.HIGH.value
            },
            502: {
                "code": "BAD_GATEWAY",
                "message": "Service temporarily unavailable",
                "level": ErrorLevel.HIGH.value
            },
            503: {
                "code": "SERVICE_UNAVAILABLE",
                "message": "Service temporarily unavailable",
                "level": ErrorLevel.HIGH.value
            },
            504: {
                "code": "GATEWAY_TIMEOUT",
                "message": "Request timeout",
                "level": ErrorLevel.MEDIUM.value
            }
        }
        
        error_info = http_errors.get(status_code, {
            "code": "HTTP_ERROR",
            "message": "HTTP error occurred",
            "level": ErrorLevel.MEDIUM.value
        })
        
        # Sanitize detail if provided
        if detail and self.debug_mode:
            error_info["details"] = self._sanitize_message_content(detail)
        
        return {"error": error_info}
    
    def create_security_alert(self, alert_type: str, details: Dict[str, Any]) -> Dict[str, Any]:
        """Create security alert with sanitized information."""
        # Remove sensitive details for security alerts
        safe_details = {}
        allowed_fields = ['ip', 'user_agent', 'endpoint', 'method', 'timestamp']
        
        for field in allowed_fields:
            if field in details:
                safe_details[field] = details[field]
        
        # Sanitize IP if needed (keep only first 3 octets for privacy)
        if 'ip' in safe_details:
            ip_parts = safe_details['ip'].split('.')
            if len(ip_parts) == 4:
                safe_details['ip'] = f"{ip_parts[0]}.{ip_parts[1]}.{ip_parts[2]}.xxx"
        
        logger.warning(
            "Security alert",
            alert_type=alert_type,
            details=safe_details,
            level=ErrorLevel.HIGH.value
        )
        
        return {
            "error": {
                "code": "SECURITY_VIOLATION",
                "message": "Security policy violation detected",
                "type": "SecurityError",
                "level": ErrorLevel.HIGH.value,
                "alert_type": alert_type
            }
        }


# Global error handler instance
error_handler = ProductionErrorHandler(debug_mode=False)


def set_debug_mode(enabled: bool):
    """Enable or disable debug mode globally."""
    global error_handler
    error_handler.debug_mode = enabled


def sanitize_error(error: Exception, level: ErrorLevel = ErrorLevel.MEDIUM) -> Dict[str, Any]:
    """Convenience function for error sanitization."""
    return error_handler.sanitize_error_message(error, level)


def create_http_error(status_code: int, detail: str = None) -> Dict[str, Any]:
    """Convenience function for HTTP error creation."""
    return error_handler.handle_http_exception(status_code, detail)


def create_security_alert(alert_type: str, details: Dict[str, Any]) -> Dict[str, Any]:
    """Convenience function for security alert creation."""
    return error_handler.create_security_alert(alert_type, details)