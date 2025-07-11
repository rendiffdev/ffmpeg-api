"""
Tests for storage backend functionality
"""
import asyncio
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch
import pytest

from storage.factory import create_storage_backend
from storage.backends.local import LocalStorageBackend


class TestLocalStorageBackend:
    """Test local storage backend."""
    
    @pytest.fixture
    def temp_storage_dir(self):
        """Create temporary storage directory."""
        with tempfile.TemporaryDirectory() as temp_dir:
            yield Path(temp_dir)
    
    @pytest.fixture
    def local_backend(self, temp_storage_dir):
        """Create local storage backend."""
        config = {
            "type": "local",
            "base_path": str(temp_storage_dir)
        }
        return LocalStorageBackend(config)
    
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_write_and_read_file(self, local_backend, temp_storage_dir):
        """Test writing and reading a file."""
        test_content = b"test file content"
        file_path = "test/file.txt"
        
        # Write file
        with tempfile.NamedTemporaryFile() as temp_file:
            temp_file.write(test_content)
            temp_file.seek(0)
            
            await local_backend.write(file_path, temp_file)
        
        # Verify file exists
        full_path = temp_storage_dir / file_path
        assert full_path.exists()
        assert full_path.read_bytes() == test_content
        
        # Read file back
        async with await local_backend.read(file_path) as stream:
            content = b""
            async for chunk in stream:
                content += chunk
        
        assert content == test_content
    
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_delete_file(self, local_backend, temp_storage_dir):
        """Test file deletion."""
        test_content = b"test file content"
        file_path = "test/delete_me.txt"
        
        # Write file first
        with tempfile.NamedTemporaryFile() as temp_file:
            temp_file.write(test_content)
            temp_file.seek(0)
            await local_backend.write(file_path, temp_file)
        
        # Verify file exists
        full_path = temp_storage_dir / file_path
        assert full_path.exists()
        
        # Delete file
        await local_backend.delete(file_path)
        
        # Verify file is deleted
        assert not full_path.exists()
    
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_exists_file(self, local_backend, temp_storage_dir):
        """Test file existence check."""
        file_path = "test/exists_test.txt"
        
        # File should not exist initially
        exists = await local_backend.exists(file_path)
        assert not exists
        
        # Create file
        full_path = temp_storage_dir / file_path
        full_path.parent.mkdir(parents=True, exist_ok=True)
        full_path.write_bytes(b"test content")
        
        # File should exist now
        exists = await local_backend.exists(file_path)
        assert exists
    
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_list_files(self, local_backend, temp_storage_dir):
        """Test file listing."""
        # Create test files
        test_files = [
            "test/file1.txt",
            "test/file2.txt",
            "test/subdir/file3.txt"
        ]
        
        for file_path in test_files:
            with tempfile.NamedTemporaryFile() as temp_file:
                temp_file.write(b"test content")
                temp_file.seek(0)
                await local_backend.write(file_path, temp_file)
        
        # List files in test directory
        files = await local_backend.list("test/")
        
        # Should find all files
        assert len(files) >= 3
        file_names = [f["path"] for f in files]
        assert "test/file1.txt" in file_names
        assert "test/file2.txt" in file_names
        assert "test/subdir/file3.txt" in file_names


class TestStorageFactory:
    """Test storage factory functionality."""
    
    @pytest.mark.unit
    def test_create_local_backend(self):
        """Test creating local storage backend."""
        config = {
            "type": "local",
            "base_path": "/tmp/test"
        }
        
        backend = create_storage_backend(config)
        assert isinstance(backend, LocalStorageBackend)
    
    @pytest.mark.unit
    def test_create_unsupported_backend(self):
        """Test creating unsupported storage backend."""
        config = {
            "type": "unsupported",
            "some_config": "value"
        }
        
        with pytest.raises(ValueError, match="Unsupported storage backend"):
            create_storage_backend(config)
    
    @pytest.mark.unit
    @patch('storage.factory.S3StorageBackend')
    def test_create_s3_backend(self, mock_s3_class):
        """Test creating S3 storage backend."""
        config = {
            "type": "s3",
            "bucket": "test-bucket",
            "region": "us-east-1",
            "access_key": "test-key",
            "secret_key": "test-secret"
        }
        
        mock_backend = MagicMock()
        mock_s3_class.return_value = mock_backend
        
        backend = create_storage_backend(config)
        
        mock_s3_class.assert_called_once_with(config)
        assert backend is mock_backend


class TestStorageIntegration:
    """Integration tests for storage functionality."""
    
    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_file_upload_download_workflow(self):
        """Test complete file upload/download workflow."""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create backend
            config = {
                "type": "local",
                "base_path": temp_dir
            }
            backend = create_storage_backend(config)
            
            # Test data
            test_content = b"This is a test file for upload/download workflow"
            file_path = "workflow/test_file.bin"
            
            # Upload file
            with tempfile.NamedTemporaryFile() as temp_file:
                temp_file.write(test_content)
                temp_file.seek(0)
                await backend.write(file_path, temp_file)
            
            # Verify upload
            assert await backend.exists(file_path)
            
            # Download file
            downloaded_content = b""
            async with await backend.read(file_path) as stream:
                async for chunk in stream:
                    downloaded_content += chunk
            
            # Verify content matches
            assert downloaded_content == test_content
            
            # List files
            files = await backend.list("workflow/")
            assert len(files) == 1
            assert files[0]["path"] == file_path
            
            # Clean up
            await backend.delete(file_path)
            assert not await backend.exists(file_path)


class TestStorageErrors:
    """Test storage error handling."""
    
    @pytest.fixture
    def local_backend(self):
        """Create local storage backend with invalid path."""
        config = {
            "type": "local",
            "base_path": "/invalid/readonly/path"
        }
        return LocalStorageBackend(config)
    
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_write_to_readonly_path(self, local_backend):
        """Test writing to read-only path."""
        with tempfile.NamedTemporaryFile() as temp_file:
            temp_file.write(b"test content")
            temp_file.seek(0)
            
            with pytest.raises(Exception):  # Should raise some form of permission error
                await local_backend.write("test.txt", temp_file)
    
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_read_nonexistent_file(self):
        """Test reading non-existent file."""
        with tempfile.TemporaryDirectory() as temp_dir:
            config = {
                "type": "local",
                "base_path": temp_dir
            }
            backend = create_storage_backend(config)
            
            with pytest.raises(FileNotFoundError):
                await backend.read("nonexistent/file.txt")
    
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_delete_nonexistent_file(self):
        """Test deleting non-existent file."""
        with tempfile.TemporaryDirectory() as temp_dir:
            config = {
                "type": "local",
                "base_path": temp_dir
            }
            backend = create_storage_backend(config)
            
            # Should not raise error for deleting non-existent file
            await backend.delete("nonexistent/file.txt")


class TestStorageConfiguration:
    """Test storage configuration validation."""
    
    @pytest.mark.unit
    def test_local_backend_missing_base_path(self):
        """Test local backend with missing base_path."""
        config = {
            "type": "local"
            # Missing base_path
        }
        
        with pytest.raises(KeyError):
            LocalStorageBackend(config)
    
    @pytest.mark.unit
    def test_local_backend_creates_directory(self):
        """Test local backend creates base directory."""
        with tempfile.TemporaryDirectory() as temp_dir:
            base_path = Path(temp_dir) / "new_storage_dir"
            config = {
                "type": "local",
                "base_path": str(base_path)
            }
            
            backend = LocalStorageBackend(config)
            
            # Directory should be created
            assert base_path.exists()
            assert base_path.is_dir()


class TestStorageMetrics:
    """Test storage metrics and monitoring."""
    
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_file_size_tracking(self):
        """Test file size tracking in storage operations."""
        with tempfile.TemporaryDirectory() as temp_dir:
            config = {
                "type": "local",
                "base_path": temp_dir
            }
            backend = create_storage_backend(config)
            
            # Create test file with known size
            test_content = b"x" * 1024  # 1KB file
            file_path = "metrics/size_test.bin"
            
            with tempfile.NamedTemporaryFile() as temp_file:
                temp_file.write(test_content)
                temp_file.seek(0)
                await backend.write(file_path, temp_file)
            
            # List and check file size
            files = await backend.list("metrics/")
            assert len(files) == 1
            assert files[0]["size"] == 1024
    
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_large_file_handling(self):
        """Test handling of large files."""
        with tempfile.TemporaryDirectory() as temp_dir:
            config = {
                "type": "local",
                "base_path": temp_dir
            }
            backend = create_storage_backend(config)
            
            # Create large test file (1MB)
            test_size = 1024 * 1024
            file_path = "large/big_file.bin"
            
            with tempfile.NamedTemporaryFile() as temp_file:
                # Write in chunks to avoid memory issues
                chunk_size = 8192
                for _ in range(test_size // chunk_size):
                    temp_file.write(b"x" * chunk_size)
                temp_file.seek(0)
                
                await backend.write(file_path, temp_file)
            
            # Verify file exists and has correct size
            assert await backend.exists(file_path)
            files = await backend.list("large/")
            assert files[0]["size"] == test_size
            
            # Test reading in chunks
            total_read = 0
            async with await backend.read(file_path) as stream:
                async for chunk in stream:
                    total_read += len(chunk)
            
            assert total_read == test_size