"""
Dependency injection for services
"""
from functools import lru_cache

from api.services.job_service import JobService
from api.repositories.job_repository import JobRepository
from api.repositories.api_key_repository import APIKeyRepository


@lru_cache()
def get_job_repository() -> JobRepository:
    """Get job repository instance."""
    return JobRepository()


@lru_cache()
def get_api_key_repository() -> APIKeyRepository:
    """Get API key repository instance."""
    return APIKeyRepository()


@lru_cache()
def get_job_service() -> JobService:
    """Get job service instance."""
    return JobService(get_job_repository())


# Factory functions for dependency injection
def create_job_service() -> JobService:
    """Create a new job service instance."""
    return JobService(get_job_repository())


def create_job_repository() -> JobRepository:
    """Create a new job repository instance."""
    return JobRepository()


def create_api_key_repository() -> APIKeyRepository:
    """Create a new API key repository instance."""
    return APIKeyRepository()