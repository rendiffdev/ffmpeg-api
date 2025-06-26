"""
Base storage backend interface
"""
from abc import ABC, abstractmethod
from typing import AsyncIterator, Optional, Dict, Any, List
from pathlib import Path
import aiofiles


class StorageBackend(ABC):
    """Abstract base class for storage backends."""
    
    def __init__(self, config: Dict[str, Any]):
        """Initialize storage backend with configuration."""
        self.config = config
        self.name = config.get("name", "unknown")
    
    @abstractmethod
    async def exists(self, path: str) -> bool:
        """Check if a file exists."""
        pass
    
    @abstractmethod
    async def read(self, path: str, chunk_size: int = 8192) -> AsyncIterator[bytes]:
        """Read file content as chunks."""
        pass
    
    @abstractmethod
    async def write(self, path: str, content: AsyncIterator[bytes]) -> int:
        """Write content to file. Returns bytes written."""
        pass
    
    @abstractmethod
    async def delete(self, path: str) -> bool:
        """Delete a file. Returns True if successful."""
        pass
    
    @abstractmethod
    async def list(self, prefix: str) -> List[str]:
        """List files with given prefix."""
        pass
    
    @abstractmethod
    async def stat(self, path: str) -> Dict[str, Any]:
        """Get file statistics."""
        pass
    
    @abstractmethod
    async def move(self, src: str, dst: str) -> bool:
        """Move/rename a file."""
        pass
    
    @abstractmethod
    async def copy(self, src: str, dst: str) -> bool:
        """Copy a file."""
        pass
    
    async def ensure_dir(self, path: str) -> None:
        """Ensure directory exists (for backends that support it)."""
        pass
    
    async def get_url(self, path: str, expires: int = 3600) -> str:
        """Get a temporary URL for direct access (if supported)."""
        raise NotImplementedError(f"{self.__class__.__name__} does not support direct URLs")
    
    async def stream_to(self, src: str, dst_backend: 'StorageBackend', dst_path: str) -> int:
        """Stream file from this backend to another."""
        bytes_written = 0
        async for chunk in self.read(src):
            bytes_written += len(chunk)
            await dst_backend.write(dst_path, chunk)
        return bytes_written
    
    def parse_uri(self, uri: str) -> tuple[str, str]:
        """Parse storage URI into backend name and path."""
        if "://" in uri:
            backend, path = uri.split("://", 1)
            return backend, path
        # Assume local filesystem if no scheme
        return "local", uri


class LocalStorageBackend(StorageBackend):
    """Local filesystem storage backend."""
    
    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.base_path = Path(config.get("base_path", "/storage"))
        self.base_path.mkdir(parents=True, exist_ok=True)
    
    def _full_path(self, path: str) -> Path:
        """Get full filesystem path."""
        # Remove leading slash to avoid absolute path issues
        path = path.lstrip("/")
        full_path = self.base_path / path
        
        # Security: ensure path is within base_path
        try:
            full_path.resolve().relative_to(self.base_path.resolve())
        except ValueError:
            raise ValueError(f"Path '{path}' is outside storage boundary")
        
        return full_path
    
    async def exists(self, path: str) -> bool:
        """Check if file exists."""
        return self._full_path(path).exists()
    
    async def read(self, path: str, chunk_size: int = 8192) -> AsyncIterator[bytes]:
        """Read file in chunks."""
        full_path = self._full_path(path)
        if not full_path.exists():
            raise FileNotFoundError(f"File not found: {path}")
        
        async with aiofiles.open(full_path, "rb") as f:
            while chunk := await f.read(chunk_size):
                yield chunk
    
    async def write(self, path: str, content: AsyncIterator[bytes]) -> int:
        """Write content to file."""
        full_path = self._full_path(path)
        full_path.parent.mkdir(parents=True, exist_ok=True)
        
        bytes_written = 0
        async with aiofiles.open(full_path, "wb") as f:
            async for chunk in content:
                await f.write(chunk)
                bytes_written += len(chunk)
        
        return bytes_written
    
    async def delete(self, path: str) -> bool:
        """Delete file."""
        full_path = self._full_path(path)
        if full_path.exists():
            full_path.unlink()
            return True
        return False
    
    async def list(self, prefix: str) -> List[str]:
        """List files with prefix."""
        base = self._full_path(prefix)
        if not base.exists():
            return []
        
        files = []
        if base.is_dir():
            for item in base.rglob("*"):
                if item.is_file():
                    relative = item.relative_to(self.base_path)
                    files.append(str(relative))
        elif base.is_file():
            files.append(prefix)
        
        return files
    
    async def stat(self, path: str) -> Dict[str, Any]:
        """Get file statistics."""
        full_path = self._full_path(path)
        if not full_path.exists():
            raise FileNotFoundError(f"File not found: {path}")
        
        stat = full_path.stat()
        return {
            "size": stat.st_size,
            "modified": stat.st_mtime,
            "created": stat.st_ctime,
            "is_dir": full_path.is_dir(),
        }
    
    async def move(self, src: str, dst: str) -> bool:
        """Move file."""
        src_path = self._full_path(src)
        dst_path = self._full_path(dst)
        
        if not src_path.exists():
            return False
        
        dst_path.parent.mkdir(parents=True, exist_ok=True)
        src_path.rename(dst_path)
        return True
    
    async def copy(self, src: str, dst: str) -> bool:
        """Copy file."""
        src_path = self._full_path(src)
        dst_path = self._full_path(dst)
        
        if not src_path.exists():
            return False
        
        dst_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Stream copy for large files
        async with aiofiles.open(src_path, "rb") as src_file:
            async with aiofiles.open(dst_path, "wb") as dst_file:
                while chunk := await src_file.read(8192):
                    await dst_file.write(chunk)
        
        return True
    
    async def ensure_dir(self, path: str) -> None:
        """Ensure directory exists."""
        dir_path = self._full_path(path)
        dir_path.mkdir(parents=True, exist_ok=True)