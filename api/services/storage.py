"""
Storage service for managing multiple backends
"""
from typing import Dict, Any, Optional, Tuple
import yaml
from pathlib import Path

import structlog

from api.config import settings
from storage.factory import create_storage_backend
from storage.base import StorageBackend

logger = structlog.get_logger()


class StorageService:
    """Service for managing storage backends."""
    
    def __init__(self):
        self.backends: Dict[str, StorageBackend] = {}
        self.config: Dict[str, Any] = {}
    
    async def initialize(self) -> None:
        """Initialize storage backends from configuration."""
        # Load storage configuration
        config_path = Path(settings.STORAGE_CONFIG)
        if not config_path.exists():
            # Use default configuration
            self.config = {
                "storage": {
                    "default_backend": "local",
                    "backends": {
                        "local": {
                            "type": "filesystem",
                            "name": "local",
                            "base_path": settings.STORAGE_PATH,
                        }
                    }
                }
            }
        else:
            with open(config_path, 'r') as f:
                self.config = yaml.safe_load(f)
        
        # Initialize backends
        storage_config = self.config.get("storage", {})
        backends_config = storage_config.get("backends", {})
        
        for name, backend_config in backends_config.items():
            try:
                backend = create_storage_backend(backend_config)
                self.backends[name] = backend
                logger.info(f"Initialized storage backend: {name}")
            except Exception as e:
                logger.error(f"Failed to initialize backend {name}: {e}")
        
        if not self.backends:
            raise RuntimeError("No storage backends initialized")
        
        # Set default backend
        default_backend = storage_config.get("default_backend", "local")
        if default_backend not in self.backends:
            logger.warning(f"Default backend '{default_backend}' not found, using first available")
            default_backend = list(self.backends.keys())[0]
        
        self.default_backend = default_backend
        logger.info(f"Storage service initialized with {len(self.backends)} backends")
    
    async def cleanup(self) -> None:
        """Clean up storage backends."""
        for backend in self.backends.values():
            if hasattr(backend, 'cleanup'):
                await backend.cleanup()
    
    def parse_uri(self, uri: str) -> Tuple[str, str]:
        """
        Parse storage URI into backend name and path.
        
        Examples:
        - /path/to/file -> ("local", "/path/to/file")
        - s3://bucket/path -> ("s3", "bucket/path")
        - nfs://server/path -> ("nfs", "server/path")
        """
        if "://" in uri:
            parts = uri.split("://", 1)
            backend_name = parts[0]
            path = parts[1]
        else:
            # Default to local backend for absolute paths
            backend_name = self.default_backend
            path = uri
        
        return backend_name, path
    
    def get_backend(self, name: str) -> Optional[StorageBackend]:
        """Get storage backend by name."""
        return self.backends.get(name)
    
    async def exists(self, uri: str) -> bool:
        """Check if file exists in any backend."""
        backend_name, path = self.parse_uri(uri)
        backend = self.get_backend(backend_name)
        
        if not backend:
            raise ValueError(f"Unknown storage backend: {backend_name}")
        
        return await backend.exists(path)
    
    async def copy_between_backends(
        self,
        source_uri: str,
        dest_uri: str,
        progress_callback: Optional[callable] = None
    ) -> int:
        """Copy file between different storage backends."""
        # Parse URIs
        src_backend_name, src_path = self.parse_uri(source_uri)
        dst_backend_name, dst_path = self.parse_uri(dest_uri)
        
        # Get backends
        src_backend = self.get_backend(src_backend_name)
        dst_backend = self.get_backend(dst_backend_name)
        
        if not src_backend:
            raise ValueError(f"Unknown source backend: {src_backend_name}")
        if not dst_backend:
            raise ValueError(f"Unknown destination backend: {dst_backend_name}")
        
        # Check if source exists
        if not await src_backend.exists(src_path):
            raise FileNotFoundError(f"Source file not found: {source_uri}")
        
        # Copy data
        bytes_copied = 0
        async for chunk in src_backend.read(src_path):
            await dst_backend.write(dst_path, chunk)
            bytes_copied += len(chunk)
            
            if progress_callback:
                progress_callback(bytes_copied)
        
        logger.info(f"Copied {bytes_copied} bytes from {source_uri} to {dest_uri}")
        return bytes_copied
    
    async def health_check(self) -> Dict[str, Any]:
        """Check health of all storage backends."""
        health_status = {
            "status": "healthy",
            "backends": {},
        }
        
        for name, backend in self.backends.items():
            try:
                # Try to list root directory
                await backend.list("")
                health_status["backends"][name] = {
                    "status": "healthy",
                    "type": backend.__class__.__name__,
                }
            except Exception as e:
                health_status["status"] = "degraded"
                health_status["backends"][name] = {
                    "status": "unhealthy",
                    "error": str(e),
                }
        
        return health_status
    
    async def get_backend_status(self, backend_name: str) -> Dict[str, Any]:
        """Get detailed status of a specific backend."""
        backend = self.get_backend(backend_name)
        if not backend:
            raise ValueError(f"Unknown backend: {backend_name}")
        
        # Get backend-specific status
        if hasattr(backend, 'get_status'):
            return await backend.get_status()
        
        # Default status
        return {
            "type": backend.__class__.__name__,
            "config": backend.config,
        }