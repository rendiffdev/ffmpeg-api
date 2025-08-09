"""
Health check utilities for all system dependencies
"""
import asyncio
from typing import Dict, Any, Optional
import structlog

logger = structlog.get_logger()

class HealthChecker:
    """Comprehensive health checking for all dependencies."""
    
    def __init__(self):
        self.checks = {}
    
    async def check_database(self, db_session) -> Dict[str, Any]:
        """Check database connectivity and performance."""
        try:
            start_time = asyncio.get_event_loop().time()
            
            # Simple connectivity test
            from sqlalchemy import text
            result = await db_session.execute(text("SELECT 1"))
            response_time = (asyncio.get_event_loop().time() - start_time) * 1000
            
            return {
                "status": "healthy",
                "response_time_ms": round(response_time, 2),
                "details": "Database connection successful"
            }
        except Exception as e:
            return {
                "status": "unhealthy", 
                "error": str(e),
                "details": "Database connection failed"
            }
    
    async def check_redis(self) -> Dict[str, Any]:
        """Check Redis/Valkey connectivity."""
        try:
            import redis.asyncio as redis
            from api.config import settings
            
            start_time = asyncio.get_event_loop().time()
            
            # Parse Redis URL
            redis_client = redis.from_url(settings.VALKEY_URL)
            await redis_client.ping()
            response_time = (asyncio.get_event_loop().time() - start_time) * 1000
            
            # Check memory usage
            info = await redis_client.info('memory')
            memory_usage = info.get('used_memory_human', 'unknown')
            
            await redis_client.close()
            
            return {
                "status": "healthy",
                "response_time_ms": round(response_time, 2),
                "memory_usage": memory_usage,
                "details": "Redis connection successful"
            }
        except Exception as e:
            return {
                "status": "unhealthy",
                "error": str(e),
                "details": "Redis connection failed"
            }
    
    async def check_storage_backends(self) -> Dict[str, Any]:
        """Check all configured storage backends."""
        from api.services.storage import StorageService
        
        try:
            storage_service = StorageService()
            await storage_service.initialize()
            
            backend_status = {}
            overall_healthy = True
            
            for name, backend in storage_service.backends.items():
                try:
                    start_time = asyncio.get_event_loop().time()
                    
                    # Try to list root directory
                    await backend.list("")
                    response_time = (asyncio.get_event_loop().time() - start_time) * 1000
                    
                    backend_status[name] = {
                        "status": "healthy",
                        "response_time_ms": round(response_time, 2),
                        "type": backend.__class__.__name__
                    }
                except Exception as e:
                    backend_status[name] = {
                        "status": "unhealthy",
                        "error": str(e),
                        "type": backend.__class__.__name__
                    }
                    overall_healthy = False
            
            return {
                "status": "healthy" if overall_healthy else "degraded",
                "backends": backend_status,
                "total_backends": len(storage_service.backends)
            }
            
        except Exception as e:
            return {
                "status": "unhealthy",
                "error": str(e),
                "details": "Storage service initialization failed"
            }
    
    async def check_ffmpeg(self) -> Dict[str, Any]:
        """Check FFmpeg availability and version."""
        try:
            start_time = asyncio.get_event_loop().time()
            
            proc = await asyncio.create_subprocess_exec(
                'ffmpeg', '-version',
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            stdout, stderr = await proc.communicate()
            response_time = (asyncio.get_event_loop().time() - start_time) * 1000
            
            if proc.returncode == 0:
                version_line = stdout.decode().split('\n')[0]
                return {
                    "status": "healthy",
                    "response_time_ms": round(response_time, 2),
                    "version": version_line,
                    "details": "FFmpeg available"
                }
            else:
                return {
                    "status": "unhealthy",
                    "error": stderr.decode(),
                    "details": "FFmpeg execution failed"
                }
        except Exception as e:
            return {
                "status": "unhealthy",
                "error": str(e),
                "details": "FFmpeg not available"
            }
    
    async def check_disk_space(self) -> Dict[str, Any]:
        """Check available disk space."""
        import shutil
        import os
        
        try:
            from api.config import settings
            
            # Check temp directory space
            temp_path = getattr(settings, 'TEMP_DIR', '/tmp')
            total, used, free = shutil.disk_usage(temp_path)
            
            free_gb = free / (1024**3)
            total_gb = total / (1024**3)
            usage_percent = (used / total) * 100
            
            status = "healthy"
            if free_gb < 5:  # Less than 5GB free
                status = "warning"
            if free_gb < 1:  # Less than 1GB free  
                status = "unhealthy"
            
            return {
                "status": status,
                "free_space_gb": round(free_gb, 2),
                "total_space_gb": round(total_gb, 2),
                "usage_percent": round(usage_percent, 1),
                "path": temp_path
            }
        except Exception as e:
            return {
                "status": "unhealthy",
                "error": str(e),
                "details": "Disk space check failed"
            }
    
    async def run_all_checks(self, db_session=None) -> Dict[str, Any]:
        """Run all health checks concurrently."""
        try:
            # Run checks concurrently for better performance
            checks = await asyncio.gather(
                self.check_redis(),
                self.check_storage_backends(),
                self.check_ffmpeg(),
                self.check_disk_space(),
                self.check_database(db_session) if db_session else self._dummy_db_check(),
                return_exceptions=True
            )
            
            results = {
                "redis": checks[0] if not isinstance(checks[0], Exception) else {"status": "error", "error": str(checks[0])},
                "storage": checks[1] if not isinstance(checks[1], Exception) else {"status": "error", "error": str(checks[1])},
                "ffmpeg": checks[2] if not isinstance(checks[2], Exception) else {"status": "error", "error": str(checks[2])},
                "disk": checks[3] if not isinstance(checks[3], Exception) else {"status": "error", "error": str(checks[3])},
                "database": checks[4] if not isinstance(checks[4], Exception) else {"status": "error", "error": str(checks[4])},
            }
            
            # Determine overall status
            overall_status = "healthy"
            for service, result in results.items():
                if result.get("status") == "unhealthy":
                    overall_status = "unhealthy"
                    break
                elif result.get("status") in ["warning", "degraded"]:
                    overall_status = "degraded"
            
            return {
                "status": overall_status,
                "timestamp": asyncio.get_event_loop().time(),
                "services": results
            }
            
        except Exception as e:
            logger.error("Health check failed", error=str(e))
            return {
                "status": "unhealthy",
                "error": str(e),
                "timestamp": asyncio.get_event_loop().time()
            }
    
    async def _dummy_db_check(self):
        """Dummy database check when no session provided."""
        return {"status": "skipped", "details": "No database session provided"}

# Global health checker instance
health_checker = HealthChecker()