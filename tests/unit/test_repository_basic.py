"""
Basic tests for repository pattern (without pytest)
"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from api.repositories.job_repository import JobRepository
from api.repositories.api_key_repository import APIKeyRepository
from api.services.job_service import JobService
from api.models.job import Job, JobStatus
from api.models.api_key import APIKey


def test_repository_initialization():
    """Test that repositories initialize correctly."""
    print("Testing repository initialization...")
    
    job_repo = JobRepository()
    api_key_repo = APIKeyRepository()
    
    assert job_repo.model == Job, "Job repository should use Job model"
    assert api_key_repo.model == APIKey, "API key repository should use APIKey model"
    
    print("✓ Repository initialization test passed")


def test_service_initialization():
    """Test that services initialize correctly."""
    print("Testing service initialization...")
    
    # Test with default repository
    job_service = JobService()
    assert job_service.job_repository is not None, "Service should have repository"
    
    # Test with custom repository
    custom_repo = JobRepository()
    job_service2 = JobService(custom_repo)
    assert job_service2.job_repository == custom_repo, "Service should use custom repository"
    
    print("✓ Service initialization test passed")


def test_repository_interfaces():
    """Test that repositories implement required interfaces."""
    print("Testing repository interfaces...")
    
    job_repo = JobRepository()
    api_key_repo = APIKeyRepository()
    
    # Check that repositories have required methods
    required_methods = ['create', 'get_by_id', 'update', 'delete', 'exists', 'count']
    
    for method in required_methods:
        assert hasattr(job_repo, method), f"Job repository missing method: {method}"
        assert hasattr(api_key_repo, method), f"API key repository missing method: {method}"
    
    # Check job-specific methods
    job_specific_methods = ['get_by_status', 'get_by_user_id', 'update_status', 'get_pending_jobs']
    for method in job_specific_methods:
        assert hasattr(job_repo, method), f"Job repository missing specific method: {method}"
    
    # Check API key-specific methods
    key_specific_methods = ['get_by_key', 'get_active_keys', 'revoke_key']
    for method in key_specific_methods:
        assert hasattr(api_key_repo, method), f"API key repository missing specific method: {method}"
    
    print("✓ Repository interface test passed")


def test_service_methods():
    """Test that services have required methods."""
    print("Testing service methods...")
    
    job_service = JobService()
    
    service_methods = [
        'create_job', 'get_job', 'get_jobs_by_user', 'get_jobs_by_status',
        'update_job_status', 'start_job_processing', 'complete_job', 'fail_job'
    ]
    
    for method in service_methods:
        assert hasattr(job_service, method), f"Job service missing method: {method}"
        assert callable(getattr(job_service, method)), f"Service method {method} not callable"
    
    print("✓ Service methods test passed")


def test_enum_imports():
    """Test that enum imports work correctly."""
    print("Testing enum imports...")
    
    # Test JobStatus enum
    assert hasattr(JobStatus, 'PENDING'), "JobStatus missing PENDING"
    assert hasattr(JobStatus, 'PROCESSING'), "JobStatus missing PROCESSING"
    assert hasattr(JobStatus, 'COMPLETED'), "JobStatus missing COMPLETED"
    assert hasattr(JobStatus, 'FAILED'), "JobStatus missing FAILED"
    
    print("✓ Enum imports test passed")


def run_all_tests():
    """Run all tests."""
    print("Running repository pattern tests...\n")
    
    try:
        test_repository_initialization()
        test_service_initialization()
        test_repository_interfaces()
        test_service_methods()
        test_enum_imports()
        
        print("\n🎉 All tests passed! Repository pattern implemented successfully.")
        return True
        
    except Exception as e:
        print(f"\n❌ Test failed with error: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)