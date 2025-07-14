"""
Tests for worker base classes and functionality
"""
import asyncio
import tempfile
from datetime import datetime
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4
import pytest

from api.models.job import Job, JobStatus
from api.models.api_key import ApiKeyUser
from worker.base import (
    BaseWorkerTask, 
    BaseProcessor, 
    AsyncDatabaseMixin, 
    TaskExecutionMixin,
    ProcessingError
)


class TestAsyncDatabaseMixin:
    """Test async database mixin functionality."""
    
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_get_async_session(self):
        """Test async session creation."""
        mixin = AsyncDatabaseMixin()
        
        # Mock the session maker
        with patch.object(mixin, '_get_async_session_maker') as mock_maker:
            mock_session = AsyncMock()
            mock_context = AsyncMock()
            mock_context.__aenter__.return_value = mock_session
            mock_context.__aexit__.return_value = None
            mock_maker.return_value.return_value = mock_context
            
            async with mixin.get_async_session() as session:
                assert session is mock_session
                mock_session.commit.assert_not_called()  # Should not auto-commit yet
            
            # After context exit, commit should be called
            mock_session.commit.assert_called_once()
    
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_get_async_session_rollback_on_error(self):
        """Test session rollback on error."""
        mixin = AsyncDatabaseMixin()
        
        with patch.object(mixin, '_get_async_session_maker') as mock_maker:
            mock_session = AsyncMock()
            mock_context = AsyncMock()
            mock_context.__aenter__.return_value = mock_session
            mock_context.__aexit__.return_value = None
            mock_maker.return_value.return_value = mock_context
            
            with pytest.raises(ValueError):
                async with mixin.get_async_session() as session:
                    raise ValueError("Test error")
            
            mock_session.rollback.assert_called_once()
            mock_session.commit.assert_not_called()


class TestBaseWorkerTask:
    """Test base worker task functionality."""
    
    @pytest.fixture
    def base_task(self):
        """Create base worker task instance."""
        return BaseWorkerTask()
    
    @pytest.mark.unit
    def test_parse_storage_path_with_backend(self, base_task):
        """Test storage path parsing with backend."""
        backend, path = base_task.parse_storage_path("s3://bucket/path/file.mp4")
        assert backend == "s3"
        assert path == "bucket/path/file.mp4"
    
    @pytest.mark.unit
    def test_parse_storage_path_local(self, base_task):
        """Test storage path parsing for local files."""
        backend, path = base_task.parse_storage_path("/local/path/file.mp4")
        assert backend == "local"
        assert path == "/local/path/file.mp4"
    
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_get_job_success(self, base_task, test_db_session):
        """Test successful job retrieval."""
        # Create a test job
        job = Job(
            id=str(uuid4()),
            status=JobStatus.QUEUED,
            input_path="test-input.mp4",
            output_path="test-output.mp4",
            api_key="test-key",
            operations=[],
            options={}
        )
        test_db_session.add(job)
        await test_db_session.commit()
        
        # Mock the async session
        with patch.object(base_task, 'get_async_session') as mock_session:
            mock_session.return_value.__aenter__.return_value.get.return_value = job
            
            result = await base_task.get_job(job.id)
            assert result.id == job.id
    
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_get_job_not_found(self, base_task):
        """Test job not found error."""
        with patch.object(base_task, 'get_async_session') as mock_session:
            mock_session.return_value.__aenter__.return_value.get.return_value = None
            
            with pytest.raises(ProcessingError, match="Job .* not found"):
                await base_task.get_job("nonexistent-id")
    
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_update_job_status(self, base_task):
        """Test job status update."""
        job_id = str(uuid4())
        mock_job = MagicMock()
        
        with patch.object(base_task, 'get_async_session') as mock_session:
            mock_db = mock_session.return_value.__aenter__.return_value
            mock_db.get.return_value = mock_job
            
            await base_task.update_job_status(
                job_id, 
                JobStatus.PROCESSING,
                progress=50.0,
                worker_id="test-worker"
            )
            
            assert mock_job.status == JobStatus.PROCESSING
            assert mock_job.progress == 50.0
            assert mock_job.worker_id == "test-worker"
            mock_db.commit.assert_called_once()
    
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_handle_job_error(self, base_task):
        """Test job error handling."""
        job_id = str(uuid4())
        error = Exception("Test error")
        
        with patch.object(base_task, 'update_job_status') as mock_update:
            with patch.object(base_task, 'send_webhook') as mock_webhook:
                await base_task.handle_job_error(job_id, error)
                
                mock_update.assert_called_once_with(
                    job_id,
                    JobStatus.FAILED,
                    error_message="Test error",
                    completed_at=datetime
                )
                mock_webhook.assert_called_once()
    
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_send_webhook(self, base_task):
        """Test webhook sending."""
        job_id = str(uuid4())
        mock_job = MagicMock()
        mock_job.webhook_url = "https://example.com/webhook"
        
        with patch.object(base_task, 'get_job', return_value=mock_job):
            await base_task.send_webhook(job_id, "test_event", {"test": "data"})
            # Should not raise error (just logs for now)
    
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_send_webhook_no_url(self, base_task):
        """Test webhook sending with no URL."""
        job_id = str(uuid4())
        mock_job = MagicMock()
        mock_job.webhook_url = None
        
        with patch.object(base_task, 'get_job', return_value=mock_job):
            await base_task.send_webhook(job_id, "test_event", {"test": "data"})
            # Should not raise error and return early
    
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_create_storage_backends(self, base_task):
        """Test storage backend creation."""
        with patch('worker.base.open', create=True) as mock_open:
            with patch('worker.base.yaml.safe_load') as mock_yaml:
                with patch('worker.base.create_storage_backend') as mock_create:
                    # Mock YAML config
                    mock_yaml.return_value = {
                        "backends": {
                            "s3": {"type": "s3", "bucket": "test"},
                            "local": {"type": "local", "path": "/tmp"}
                        }
                    }
                    
                    # Mock backend instances
                    mock_input_backend = MagicMock()
                    mock_output_backend = MagicMock()
                    mock_create.side_effect = [mock_input_backend, mock_output_backend]
                    
                    input_backend, output_backend = await base_task.create_storage_backends(
                        "s3://bucket/input.mp4",
                        "local:///output/output.mp4"
                    )
                    
                    assert input_backend is mock_input_backend
                    assert output_backend is mock_output_backend
                    assert mock_create.call_count == 2
    
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_download_file(self, base_task):
        """Test file download."""
        mock_backend = MagicMock()
        mock_stream = AsyncMock()
        mock_stream.__aiter__.return_value = [b"chunk1", b"chunk2"]
        mock_backend.read.return_value.__aenter__.return_value = mock_stream
        
        with tempfile.TemporaryDirectory() as temp_dir:
            local_path = Path(temp_dir) / "test" / "file.mp4"
            
            await base_task.download_file(mock_backend, "remote/file.mp4", local_path)
            
            assert local_path.exists()
            assert local_path.read_bytes() == b"chunk1chunk2"
    
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_upload_file(self, base_task):
        """Test file upload."""
        mock_backend = AsyncMock()
        
        with tempfile.TemporaryDirectory() as temp_dir:
            local_path = Path(temp_dir) / "file.mp4"
            local_path.write_bytes(b"test content")
            
            await base_task.upload_file(mock_backend, local_path, "remote/file.mp4")
            
            mock_backend.write.assert_called_once()
            # Check that file handle was passed
            args = mock_backend.write.call_args[0]
            assert args[0] == "remote/file.mp4"
    
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_start_job_processing(self, base_task):
        """Test job processing start."""
        job_id = str(uuid4())
        mock_job = MagicMock()
        mock_job.id = job_id
        
        with patch.object(base_task, 'update_job_status') as mock_update:
            with patch.object(base_task, 'get_job', return_value=mock_job) as mock_get:
                with patch('worker.base.current_task') as mock_current:
                    mock_current.request.hostname = "test-worker"
                    
                    result = await base_task.start_job_processing(job_id)
                    
                    assert result is mock_job
                    assert base_task.job_id == job_id
                    assert base_task.progress_tracker is not None
                    mock_update.assert_called_once()
    
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_complete_job_processing(self, base_task):
        """Test job processing completion."""
        job_id = str(uuid4())
        mock_job = MagicMock()
        mock_job.output_path = "output.mp4"
        mock_job.started_at = datetime.utcnow()
        
        result = {
            "vmaf_score": 95.5,
            "psnr_score": 40.2,
            "metrics": {"quality": "high"}
        }
        
        with patch.object(base_task, 'get_job', return_value=mock_job):
            with patch.object(base_task, 'update_job_status') as mock_update:
                with patch.object(base_task, 'send_webhook') as mock_webhook:
                    await base_task.complete_job_processing(job_id, result)
                    
                    mock_update.assert_called_once()
                    mock_webhook.assert_called_once()


class TestBaseProcessor:
    """Test base processor functionality."""
    
    class TestProcessor(BaseProcessor):
        """Test implementation of BaseProcessor."""
        
        def __init__(self):
            super().__init__()
            self.test_initialized = False
        
        async def initialize(self):
            self.test_initialized = True
            self.initialized = True
        
        async def process(self, input_path, output_path, options, operations, progress_callback=None):
            return {"success": True, "output": output_path}
        
        def get_supported_formats(self):
            return {"input": ["mp4", "avi"], "output": ["mp4", "webm"]}
    
    @pytest.fixture
    def processor(self):
        """Create test processor instance."""
        return self.TestProcessor()
    
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_initialization(self, processor):
        """Test processor initialization."""
        assert not processor.initialized
        assert not processor.test_initialized
        
        await processor.initialize()
        
        assert processor.initialized
        assert processor.test_initialized
    
    @pytest.mark.unit
    def test_get_supported_formats(self, processor):
        """Test supported formats retrieval."""
        formats = processor.get_supported_formats()
        assert "input" in formats
        assert "output" in formats
        assert "mp4" in formats["input"]
        assert "mp4" in formats["output"]
    
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_validate_input_file_exists(self, processor):
        """Test input validation for existing file."""
        with tempfile.NamedTemporaryFile() as temp_file:
            temp_file.write(b"test content")
            temp_file.flush()
            
            result = await processor.validate_input(temp_file.name)
            assert result is True
    
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_validate_input_file_not_exists(self, processor):
        """Test input validation for non-existent file."""
        with pytest.raises(ProcessingError, match="does not exist"):
            await processor.validate_input("/nonexistent/file.mp4")
    
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_validate_input_empty_file(self, processor):
        """Test input validation for empty file."""
        with tempfile.NamedTemporaryFile() as temp_file:
            # File is empty by default
            with pytest.raises(ProcessingError, match="is empty"):
                await processor.validate_input(temp_file.name)
    
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_validate_output_creates_directory(self, processor):
        """Test output validation creates parent directory."""
        with tempfile.TemporaryDirectory() as temp_dir:
            output_path = str(Path(temp_dir) / "subdir" / "output.mp4")
            
            result = await processor.validate_output(output_path)
            assert result is True
            assert Path(output_path).parent.exists()
    
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_safe_process_success(self, processor):
        """Test safe processing success path."""
        with tempfile.NamedTemporaryFile() as input_file:
            input_file.write(b"test content")
            input_file.flush()
            
            with tempfile.TemporaryDirectory() as temp_dir:
                output_path = str(Path(temp_dir) / "output.mp4")
                
                result = await processor.safe_process(
                    input_file.name,
                    output_path,
                    {},
                    [],
                    None
                )
                
                assert result["success"] is True
                assert result["output"] == output_path
                assert processor.initialized
    
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_safe_process_with_error(self, processor):
        """Test safe processing with error."""
        # Mock process method to raise error
        async def mock_process(*args, **kwargs):
            raise Exception("Processing failed")
        
        processor.process = mock_process
        
        with tempfile.NamedTemporaryFile() as input_file:
            input_file.write(b"test content")
            input_file.flush()
            
            with tempfile.TemporaryDirectory() as temp_dir:
                output_path = str(Path(temp_dir) / "output.mp4")
                
                with pytest.raises(ProcessingError, match="Processing failed"):
                    await processor.safe_process(
                        input_file.name,
                        output_path,
                        {},
                        [],
                        None
                    )
    
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_cleanup_resources(self, processor):
        """Test resource cleanup."""
        await processor.cleanup_resources()
        # Should not raise error


class TestTaskExecutionMixin:
    """Test task execution mixin functionality."""
    
    class TestTaskWithMixin(BaseWorkerTask, TaskExecutionMixin):
        """Test class combining BaseWorkerTask with TaskExecutionMixin."""
        
        async def test_processing_func(self, job):
            """Test processing function."""
            return {"job_id": str(job.id), "status": "processed"}
    
    @pytest.fixture
    def task_with_mixin(self):
        """Create task instance with mixin."""
        return self.TestTaskWithMixin()
    
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_execute_with_error_handling_success(self, task_with_mixin):
        """Test successful execution with error handling."""
        job_id = str(uuid4())
        mock_job = MagicMock()
        mock_job.id = job_id
        
        with patch.object(task_with_mixin, 'start_job_processing', return_value=mock_job):
            with patch.object(task_with_mixin, 'complete_job_processing') as mock_complete:
                result = await task_with_mixin.execute_with_error_handling(
                    job_id,
                    task_with_mixin.test_processing_func
                )
                
                assert result["job_id"] == job_id
                assert result["status"] == "processed"
                mock_complete.assert_called_once()
    
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_execute_with_error_handling_failure(self, task_with_mixin):
        """Test execution with error handling when processing fails."""
        job_id = str(uuid4())
        mock_job = MagicMock()
        
        async def failing_func(job):
            raise Exception("Processing failed")
        
        with patch.object(task_with_mixin, 'start_job_processing', return_value=mock_job):
            with patch.object(task_with_mixin, 'handle_job_error') as mock_error:
                with pytest.raises(Exception, match="Processing failed"):
                    await task_with_mixin.execute_with_error_handling(
                        job_id,
                        failing_func
                    )
                
                mock_error.assert_called_once()


class TestIntegration:
    """Integration tests for base classes."""
    
    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_full_task_workflow(self, test_db_session):
        """Test complete task workflow with real database."""
        # Create test job
        job = Job(
            id=str(uuid4()),
            status=JobStatus.QUEUED,
            input_path="test-input.mp4",
            output_path="test-output.mp4",
            api_key="test-key",
            operations=[],
            options={}
        )
        test_db_session.add(job)
        await test_db_session.commit()
        
        # Create task instance
        task = BaseWorkerTask()
        
        # Mock async session to use test session
        with patch.object(task, 'get_async_session') as mock_session:
            mock_session.return_value.__aenter__.return_value = test_db_session
            
            # Test job retrieval
            retrieved_job = await task.get_job(str(job.id))
            assert retrieved_job.id == job.id
            
            # Test status update
            await task.update_job_status(str(job.id), JobStatus.PROCESSING, progress=50.0)
            
            # Verify update
            await test_db_session.refresh(job)
            assert job.status == JobStatus.PROCESSING
            assert job.progress == 50.0