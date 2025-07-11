"""
Rendiff FFmpeg API - Main Application
"""
import asyncio
from contextlib import asynccontextmanager
from typing import Any, Dict

from fastapi import FastAPI, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from prometheus_client import make_asgi_app
import structlog

from api.config import settings
from api.routers import convert, jobs, admin, health, api_keys
from api.utils.logger import setup_logging
from api.utils.error_handlers import (
    RendiffError, rendiff_exception_handler, validation_exception_handler,
    http_exception_handler, general_exception_handler
)
from api.services.storage import StorageService
from api.services.queue import QueueService
from api.models.database import init_db
from api.middleware.security import SecurityHeadersMiddleware, RateLimitMiddleware

# Setup structured logging
setup_logging()
logger = structlog.get_logger()

# Initialize services
storage_service = StorageService()
queue_service = QueueService()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Handle application startup and shutdown."""
    # Startup
    logger.info("Starting Rendiff API", version=settings.VERSION)
    
    # Initialize database
    await init_db()
    
    # Initialize storage backends
    await storage_service.initialize()
    
    # Initialize queue connection
    await queue_service.initialize()
    
    # Log configuration
    logger.info(
        "Configuration loaded",
        api_host=settings.API_HOST,
        api_port=settings.API_PORT,
        workers=settings.API_WORKERS,
        storage_backends=list(storage_service.backends.keys()),
    )
    
    yield
    
    # Shutdown
    logger.info("Shutting down Rendiff API")
    await storage_service.cleanup()
    await queue_service.cleanup()


# Create FastAPI application
app = FastAPI(
    title="Rendiff FFmpeg API",
    description="Self-hosted FFmpeg processing API with multi-storage support by Rendiff",
    version=settings.VERSION,
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
    lifespan=lifespan,
    contact={
        "name": "Rendiff",
        "url": "https://rendiff.dev",
        "email": "dev@rendiff.dev",
    },
    license_info={
        "name": "MIT",
        "url": "https://github.com/rendiffdev/ffmpeg-api/blob/main/LICENSE",
    },
)

# Add security middleware
app.add_middleware(
    SecurityHeadersMiddleware,
    csp_policy="default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'",
    enable_hsts=True,
    hsts_max_age=31536000,
)

# Add rate limiting middleware (backup to KrakenD)
app.add_middleware(
    RateLimitMiddleware,
    calls=2000,  # Higher limit since KrakenD handles primary rate limiting
    period=3600,
    enabled=True,
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Exception handlers
app.add_exception_handler(RendiffError, rendiff_exception_handler)
app.add_exception_handler(RequestValidationError, validation_exception_handler)
app.add_exception_handler(HTTPException, http_exception_handler)
app.add_exception_handler(Exception, general_exception_handler)


# Include routers
app.include_router(convert.router, prefix="/api/v1", tags=["convert"])
app.include_router(jobs.router, prefix="/api/v1", tags=["jobs"])
app.include_router(admin.router, prefix="/api/v1", tags=["admin"])
app.include_router(health.router, prefix="/api/v1", tags=["health"])
app.include_router(api_keys.router, prefix="/api/v1", tags=["api-keys"])

# Conditionally include GenAI routers
try:
    from api.genai.main import mount_genai_routers
    mount_genai_routers(app)
except ImportError:
    logger.info("GenAI module not available, skipping GenAI features")
except Exception as e:
    logger.warning("Failed to load GenAI features", error=str(e))

# Add Prometheus metrics endpoint
if settings.ENABLE_METRICS:
    metrics_app = make_asgi_app()
    app.mount("/metrics", metrics_app)


@app.get("/", tags=["root"])
async def root() -> Dict[str, Any]:
    """Root endpoint with API information."""
    base_info = {
        "name": "Rendiff FFmpeg API",
        "version": settings.VERSION,
        "status": "operational",
        "documentation": "/docs",
        "health": "/api/v1/health",
        "website": "https://rendiff.dev",
        "repository": "https://github.com/rendiffdev/ffmpeg-api",
        "contact": "dev@rendiff.dev",
    }
    
    # Add GenAI information if available
    try:
        from api.genai.main import get_genai_info
        base_info["genai"] = get_genai_info()
    except ImportError:
        base_info["genai"] = {
            "enabled": False,
            "message": "GenAI module not installed. Install with: pip install -r requirements-genai.txt"
        }
    except Exception as e:
        base_info["genai"] = {
            "enabled": False,
            "error": str(e)
        }
    
    return base_info


def main():
    """Main entry point for API server."""
    import uvicorn
    
    uvicorn.run(
        "api.main:app",
        host=settings.API_HOST,
        port=settings.API_PORT,
        workers=settings.API_WORKERS,
        reload=settings.API_RELOAD,
        log_config=None,  # Use structlog
    )

if __name__ == "__main__":
    main()