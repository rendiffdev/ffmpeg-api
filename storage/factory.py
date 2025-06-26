"""
Factory for creating storage backends
"""
from typing import Dict, Any, Type, Optional
import importlib
import logging

from storage.base import StorageBackend, LocalStorageBackend

logger = logging.getLogger(__name__)


# Registry of available storage backends
STORAGE_BACKENDS = {
    "filesystem": LocalStorageBackend,
    "local": LocalStorageBackend,
}

def _lazy_import_backend(backend_type: str) -> Optional[Type[StorageBackend]]:
    """Lazy import storage backend to avoid dependency issues."""
    backend_imports = {
        "s3": ("storage.backends.s3", "S3StorageBackend", ["boto3"]),
        "azure": ("storage.backends.azure", "AzureStorageBackend", ["azure.storage.blob"]),
        "gcs": ("storage.backends.gcs", "GCSStorageBackend", ["google.cloud.storage"]),
        "nfs": ("storage.backends.nfs", "NFSStorageBackend", []),
        "network": ("storage.backends.nfs", "NFSStorageBackend", []),
    }
    
    if backend_type not in backend_imports:
        return None
    
    module_name, class_name, dependencies = backend_imports[backend_type]
    
    # Check dependencies first
    for dep in dependencies:
        try:
            importlib.import_module(dep)
        except ImportError:
            logger.error(f"Missing dependency for {backend_type} backend: {dep}")
            raise ValueError(
                f"Storage backend '{backend_type}' requires {dep}. "
                f"Install with: pip install {dep.replace('.', '-')}"
            )
    
    try:
        module = importlib.import_module(module_name)
        backend_class = getattr(module, class_name)
        
        if not issubclass(backend_class, StorageBackend):
            raise ValueError(f"Backend {class_name} must inherit from StorageBackend")
        
        # Cache the successfully imported backend
        STORAGE_BACKENDS[backend_type] = backend_class
        return backend_class
        
    except ImportError as e:
        logger.error(f"Failed to import {backend_type} backend: {e}")
        raise ValueError(f"Storage backend '{backend_type}' is not available: {e}")
    except AttributeError as e:
        logger.error(f"Backend class {class_name} not found in {module_name}: {e}")
        raise ValueError(f"Storage backend '{backend_type}' is misconfigured: {e}")


def create_storage_backend(config: Dict[str, Any]) -> StorageBackend:
    """
    Create a storage backend from configuration.
    
    Args:
        config: Backend configuration dictionary
        
    Returns:
        Initialized storage backend
        
    Raises:
        ValueError: If backend type is unknown or configuration is invalid
    """
    backend_type = config.get("type")
    if not backend_type:
        raise ValueError("Storage backend configuration must include 'type'")
    
    # Check if it's a built-in backend
    if backend_type in STORAGE_BACKENDS:
        backend_class = STORAGE_BACKENDS[backend_type]
        return backend_class(config)
    
    # Try to lazy load the backend
    backend_class = _lazy_import_backend(backend_type)
    if backend_class:
        return backend_class(config)
    
    # Check if it's a custom backend
    if backend_type == "custom":
        module_path = config.get("module")
        if not module_path:
            raise ValueError("Custom backend must specify 'module'")
        
        try:
            # Import custom backend module
            module_parts = module_path.split(".")
            class_name = module_parts[-1]
            module_name = ".".join(module_parts[:-1])
            
            module = importlib.import_module(module_name)
            backend_class = getattr(module, class_name)
            
            if not issubclass(backend_class, StorageBackend):
                raise ValueError(f"Custom backend {class_name} must inherit from StorageBackend")
            
            return backend_class(config.get("config", {}))
            
        except (ImportError, AttributeError) as e:
            raise ValueError(f"Failed to load custom backend {module_path}: {e}")
    
    raise ValueError(f"Unknown storage backend type: {backend_type}")


def register_backend(name: str, backend_class: type) -> None:
    """
    Register a new storage backend type.
    
    Args:
        name: Backend type name
        backend_class: Backend class (must inherit from StorageBackend)
    """
    if not issubclass(backend_class, StorageBackend):
        raise ValueError(f"Backend class must inherit from StorageBackend")
    
    STORAGE_BACKENDS[name] = backend_class