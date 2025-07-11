"""
Mock storage backends for testing
"""
import asyncio
import io
from pathlib import Path
from typing import Dict, Any, List, AsyncGenerator
from unittest.mock import AsyncMock


class MockStorageBackend:
    """Mock storage backend for testing."""
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.files = {}  # In-memory file storage
        self.operation_history = []
    
    async def write(self, path: str, file_obj):
        """Mock file write."""
        content = file_obj.read()
        self.files[path] = {
            "content": content,
            "size": len(content),
            "modified": "2024-07-10T12:00:00Z"
        }
        self.operation_history.append(("write", path, len(content)))
    
    async def read(self, path: str):
        """Mock file read."""
        if path not in self.files:
            raise FileNotFoundError(f"File not found: {path}")
        
        self.operation_history.append(("read", path))
        
        class MockAsyncStream:
            def __init__(self, content):
                self.content = content
                self.position = 0
                self.chunk_size = 8192
            
            async def __aenter__(self):
                return self
            
            async def __aexit__(self, exc_type, exc_val, exc_tb):
                pass
            
            def __aiter__(self):
                return self
            
            async def __anext__(self):
                if self.position >= len(self.content):
                    raise StopAsyncIteration
                
                chunk = self.content[self.position:self.position + self.chunk_size]
                self.position += len(chunk)
                return chunk
        
        return MockAsyncStream(self.files[path]["content"])
    
    async def delete(self, path: str):
        """Mock file deletion."""
        if path in self.files:
            del self.files[path]
        self.operation_history.append(("delete", path))
    
    async def exists(self, path: str) -> bool:
        """Mock file existence check."""
        self.operation_history.append(("exists", path))
        return path in self.files
    
    async def list(self, prefix: str = "") -> List[Dict[str, Any]]:
        """Mock file listing."""
        self.operation_history.append(("list", prefix))
        
        files = []
        for path, info in self.files.items():
            if path.startswith(prefix):
                files.append({
                    "path": path,
                    "size": info["size"],
                    "modified": info["modified"],
                    "type": "file"
                })
        
        return files
    
    def get_operation_history(self) -> List[tuple]:
        """Get operation history for testing."""
        return self.operation_history.copy()
    
    def clear_history(self):
        """Clear operation history."""
        self.operation_history.clear()
    
    def clear_files(self):
        """Clear all stored files."""
        self.files.clear()


class MockS3Backend(MockStorageBackend):
    """Mock S3 storage backend."""
    
    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.bucket = config.get("bucket", "test-bucket")
        self.region = config.get("region", "us-east-1")


class MockAzureBackend(MockStorageBackend):
    """Mock Azure storage backend."""
    
    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.container = config.get("container", "test-container")
        self.account_name = config.get("account_name", "testaccount")


class MockGCPBackend(MockStorageBackend):
    """Mock GCP storage backend."""
    
    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.bucket = config.get("bucket", "test-bucket")
        self.project_id = config.get("project_id", "test-project")


def create_mock_storage_backend(config: Dict[str, Any]) -> MockStorageBackend:
    """Factory function to create mock storage backends."""
    storage_type = config.get("type", "local").lower()
    
    if storage_type == "local":
        return MockStorageBackend(config)
    elif storage_type == "s3":
        return MockS3Backend(config)
    elif storage_type == "azure":
        return MockAzureBackend(config)
    elif storage_type == "gcp":
        return MockGCPBackend(config)
    else:
        raise ValueError(f"Unsupported mock storage type: {storage_type}")


class MockStorageFactory:
    """Mock storage factory for testing."""
    
    @staticmethod
    def create_backend(config: Dict[str, Any]) -> MockStorageBackend:
        """Create mock storage backend."""
        return create_mock_storage_backend(config)