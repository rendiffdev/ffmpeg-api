"""
Test fixtures and mock objects
"""
from typing import Any, Dict, List, Optional
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

from api.models.job import Job, JobStatus
from api.models.api_key import ApiKey, ApiKeyStatus


class MockDatabaseSession:
    """Mock database session for testing."""
    
    def __init__(self):
        self.add = MagicMock()
        self.commit = AsyncMock()
        self.rollback = AsyncMock()
        self.refresh = AsyncMock()
        self.delete = AsyncMock()
        self.execute = AsyncMock()
        self.scalar = AsyncMock()
        self.scalar_one_or_none = AsyncMock()
        self.close = AsyncMock()
        
        # Store added objects for testing
        self._added_objects = []
        self._committed = False
        self._rolled_back = False
    
    def add(self, obj):
        """Mock add method."""
        self._added_objects.append(obj)
    
    async def commit(self):
        """Mock commit method."""
        self._committed = True
    
    async def rollback(self):
        """Mock rollback method."""
        self._rolled_back = True
    
    async def refresh(self, obj):
        """Mock refresh method."""
        # Simulate ID assignment after commit
        if not hasattr(obj, 'id') or obj.id is None:
            obj.id = uuid4()
    
    def get_added_objects(self):
        """Get objects that were added to the session."""
        return self._added_objects
    
    def was_committed(self):
        """Check if session was committed."""
        return self._committed
    
    def was_rolled_back(self):
        """Check if session was rolled back."""
        return self._rolled_back


class MockQueueService:
    """Mock queue service for testing."""
    
    def __init__(self):
        self.initialize = AsyncMock()
        self.cleanup = AsyncMock()
        self.submit_job = AsyncMock()
        self.get_job_status = AsyncMock()
        self.cancel_job = AsyncMock()
        self.get_queue_stats = AsyncMock()
        
        # Default return values
        self.submit_job.return_value = "job-123"
        self.get_job_status.return_value = JobStatus.QUEUED
        self.cancel_job.return_value = True
        self.get_queue_stats.return_value = {
            "pending": 5,
            "processing": 2,
            "workers": 3,
        }
    
    async def submit_job(self, job_data: Dict[str, Any]) -> str:
        """Mock job submission."""
        return f"job-{uuid4().hex[:8]}"
    
    async def get_job_status(self, job_id: str) -> str:
        """Mock job status retrieval."""
        return JobStatus.PROCESSING
    
    async def cancel_job(self, job_id: str) -> bool:
        """Mock job cancellation."""
        return True


class MockStorageService:
    """Mock storage service for testing."""
    
    def __init__(self):
        self.initialize = AsyncMock()
        self.cleanup = AsyncMock()
        self.upload = AsyncMock()
        self.download = AsyncMock()
        self.delete = AsyncMock()
        self.exists = AsyncMock()
        self.get_url = AsyncMock()
        self.list_files = AsyncMock()
        
        # Default return values
        self.upload.return_value = "storage/uploaded/file.mp4"
        self.download.return_value = b"file content"
        self.delete.return_value = True
        self.exists.return_value = True
        self.get_url.return_value = "https://storage.example.com/file.mp4"
        self.list_files.return_value = ["file1.mp4", "file2.mp4"]
        
        # Store uploaded files for testing
        self._uploaded_files = {}
    
    async def upload(self, local_path: str, remote_path: str) -> str:
        """Mock file upload."""
        self._uploaded_files[remote_path] = local_path
        return remote_path
    
    async def download(self, remote_path: str, local_path: str) -> bytes:
        """Mock file download."""
        return b"mock file content"
    
    async def exists(self, remote_path: str) -> bool:
        """Mock file existence check."""
        return remote_path in self._uploaded_files
    
    def get_uploaded_files(self):
        """Get files that were uploaded."""
        return self._uploaded_files


class MockFFmpeg:
    """Mock FFmpeg for testing."""
    
    def __init__(self):
        self.run = AsyncMock()
        self.probe = AsyncMock()
        self.get_formats = AsyncMock()
        self.get_codecs = AsyncMock()
        
        # Default return values
        self.run.return_value = True
        self.probe.return_value = {
            "format": {
                "filename": "test.mp4",
                "format_name": "mov,mp4,m4a,3gp,3g2,mj2",
                "duration": "10.000000",
                "size": "1000000",
                "bit_rate": "800000",
            },
            "streams": [
                {
                    "index": 0,
                    "codec_name": "h264",
                    "codec_type": "video",
                    "width": 1920,
                    "height": 1080,
                    "r_frame_rate": "30/1",
                    "duration": "10.000000",
                },
                {
                    "index": 1,
                    "codec_name": "aac",
                    "codec_type": "audio",
                    "sample_rate": "48000",
                    "channels": 2,
                    "duration": "10.000000",
                }
            ]
        }
        self.get_formats.return_value = {
            "input": {
                "video": ["mp4", "avi", "mov", "mkv"],
                "audio": ["mp3", "wav", "aac", "flac"],
            },
            "output": {
                "video": ["mp4", "avi", "mov", "mkv"],
                "audio": ["mp3", "wav", "aac", "flac"],
            }
        }
        self.get_codecs.return_value = {
            "video_codecs": ["h264", "h265", "vp9", "av1"],
            "audio_codecs": ["aac", "mp3", "opus", "flac"],
        }
    
    async def run(self, command: List[str], **kwargs) -> bool:
        """Mock FFmpeg command execution."""
        return True
    
    async def probe(self, file_path: str) -> Dict[str, Any]:
        """Mock FFmpeg probe."""
        return self.probe.return_value


class MockApiKeyService:
    """Mock API key service for testing."""
    
    def __init__(self):
        self.create_api_key = AsyncMock()
        self.validate_api_key = AsyncMock()
        self.get_api_key_by_id = AsyncMock()
        self.list_api_keys = AsyncMock()
        self.update_api_key = AsyncMock()
        self.revoke_api_key = AsyncMock()
        self.delete_api_key = AsyncMock()
        self.cleanup_expired_keys = AsyncMock()
        
        # Store created keys for testing
        self._created_keys = {}
        self._next_key_id = 1
    
    async def create_api_key(self, request, created_by=None):
        """Mock API key creation."""
        key_id = uuid4()
        full_key = f"rdf_test{self._next_key_id:08d}"
        self._next_key_id += 1
        
        mock_key = MagicMock(spec=ApiKey)
        mock_key.id = key_id
        mock_key.name = request.name
        mock_key.prefix = full_key[:8]
        mock_key.status = ApiKeyStatus.ACTIVE
        mock_key.role = request.role
        mock_key.max_concurrent_jobs = request.max_concurrent_jobs
        mock_key.monthly_quota_minutes = request.monthly_quota_minutes
        
        self._created_keys[str(key_id)] = (mock_key, full_key)
        
        return mock_key, full_key
    
    async def validate_api_key(self, key):
        """Mock API key validation."""
        # Return mock user for valid keys
        if key and key.startswith("rdf_"):
            from api.models.api_key import ApiKeyUser
            return ApiKeyUser(
                id="test-user",
                api_key_id=uuid4(),
                api_key_prefix=key[:8],
                role="user",
                max_concurrent_jobs=5,
                monthly_quota_minutes=1000,
                is_admin=False,
                total_jobs_created=0,
                total_minutes_processed=0,
                last_used_at=None,
            )
        return None


class MockRedisService:
    """Mock Redis service for testing."""
    
    def __init__(self):
        self.get = AsyncMock()
        self.set = AsyncMock()
        self.delete = AsyncMock()
        self.exists = AsyncMock()
        self.expire = AsyncMock()
        self.lpush = AsyncMock()
        self.rpop = AsyncMock()
        self.llen = AsyncMock()
        
        # Store data for testing
        self._data = {}
        self._lists = {}
    
    async def get(self, key):
        """Mock Redis get."""
        return self._data.get(key)
    
    async def set(self, key, value, ex=None):
        """Mock Redis set."""
        self._data[key] = value
        return True
    
    async def delete(self, key):
        """Mock Redis delete."""
        return self._data.pop(key, None) is not None
    
    async def exists(self, key):
        """Mock Redis exists."""
        return key in self._data
    
    async def lpush(self, key, value):
        """Mock Redis lpush."""
        if key not in self._lists:
            self._lists[key] = []
        self._lists[key].insert(0, value)
        return len(self._lists[key])
    
    async def rpop(self, key):
        """Mock Redis rpop."""
        if key in self._lists and self._lists[key]:
            return self._lists[key].pop()
        return None
    
    async def llen(self, key):
        """Mock Redis llen."""
        return len(self._lists.get(key, []))


class MockPrometheusMetrics:
    """Mock Prometheus metrics for testing."""
    
    def __init__(self):
        self.counter = MagicMock()
        self.gauge = MagicMock()
        self.histogram = MagicMock()
        self.summary = MagicMock()
        
        # Mock metric methods
        self.counter.inc = MagicMock()
        self.gauge.set = MagicMock()
        self.histogram.observe = MagicMock()
        self.summary.observe = MagicMock()


def create_mock_request():
    """Create a mock FastAPI request object."""
    request = MagicMock()
    request.client.host = "127.0.0.1"
    request.headers = {}
    request.url.path = "/test"
    request.method = "GET"
    return request


def create_mock_response():
    """Create a mock FastAPI response object."""
    response = MagicMock()
    response.status_code = 200
    response.headers = {}
    return response