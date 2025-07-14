"""
API Key models for database and API schemas
"""
from datetime import datetime, timedelta
from enum import Enum
from typing import Optional, Dict, Any
from uuid import UUID, uuid4
import secrets
import hashlib

from sqlalchemy import Column, String, DateTime, Boolean, Integer, Index, Text
from sqlalchemy.ext.declarative import declarative_base
from pydantic import BaseModel, Field, ConfigDict

from api.models.job import Base, GUID


class ApiKeyStatus(str, Enum):
    """API Key status enumeration."""
    ACTIVE = "active"
    INACTIVE = "inactive"
    EXPIRED = "expired"
    REVOKED = "revoked"


class ApiKey(Base):
    """Database model for API keys."""
    __tablename__ = "api_keys"
    
    id = Column(GUID(), primary_key=True, default=uuid4)
    name = Column(String(100), nullable=False)  # Human-readable name
    key_hash = Column(String(64), nullable=False, unique=True, index=True)  # SHA-256 hash
    prefix = Column(String(8), nullable=False, index=True)  # First 8 chars for identification
    status = Column(String, default=ApiKeyStatus.ACTIVE, nullable=False, index=True)
    
    # User/Owner information
    owner_id = Column(String(100), nullable=True)  # Future user system integration
    owner_name = Column(String(100), nullable=True)
    owner_email = Column(String(200), nullable=True)
    
    # Permissions and limits
    role = Column(String(20), default="user", nullable=False)  # user, admin
    max_concurrent_jobs = Column(Integer, default=5, nullable=False)
    monthly_quota_minutes = Column(Integer, default=10000, nullable=False)
    
    # Usage tracking
    total_jobs_created = Column(Integer, default=0, nullable=False)
    total_minutes_processed = Column(Integer, default=0, nullable=False)
    last_used_at = Column(DateTime, nullable=True)
    
    # Timing
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    expires_at = Column(DateTime, nullable=True)  # Optional expiration
    revoked_at = Column(DateTime, nullable=True)
    
    # Security
    created_by = Column(String(100), nullable=True)  # Who created this key
    revoked_by = Column(String(100), nullable=True)  # Who revoked this key
    revocation_reason = Column(Text, nullable=True)
    
    # Metadata
    metadata = Column(String(1000), nullable=True)  # JSON string for additional data
    
    # Indexes
    __table_args__ = (
        Index("idx_api_key_hash", "key_hash"),
        Index("idx_api_key_prefix", "prefix"),
        Index("idx_api_key_status_created", "status", "created_at"),
        Index("idx_api_key_owner", "owner_id"),
    )
    
    @staticmethod
    def generate_key() -> tuple[str, str, str]:
        """Generate a new API key with prefix and hash.
        
        Returns:
            tuple: (full_key, prefix, hash)
        """
        # Generate 32-byte random key
        key_bytes = secrets.token_bytes(32)
        # Create base64-like encoding but URL-safe
        key = secrets.token_urlsafe(32)
        # Add prefix for identification
        full_key = f"rdf_{key}"
        
        # Extract prefix (first 8 characters after rdf_)
        prefix = full_key[:8]
        
        # Create hash for storage
        key_hash = hashlib.sha256(full_key.encode()).hexdigest()
        
        return full_key, prefix, key_hash
    
    @staticmethod
    def hash_key(key: str) -> str:
        """Hash an API key for storage."""
        return hashlib.sha256(key.encode()).hexdigest()
    
    def is_valid(self) -> bool:
        """Check if the API key is currently valid."""
        if self.status != ApiKeyStatus.ACTIVE:
            return False
        
        if self.expires_at and self.expires_at < datetime.utcnow():
            return False
        
        return True
    
    def is_expired(self) -> bool:
        """Check if the API key is expired."""
        if self.expires_at and self.expires_at < datetime.utcnow():
            return True
        return False
    
    def update_last_used(self) -> None:
        """Update the last used timestamp."""
        self.last_used_at = datetime.utcnow()


# Pydantic schemas for API
class ApiKeyCreate(BaseModel):
    """Request schema for creating an API key."""
    model_config = ConfigDict(extra="forbid")
    
    name: str = Field(..., min_length=1, max_length=100)
    owner_name: Optional[str] = Field(None, max_length=100)
    owner_email: Optional[str] = Field(None, max_length=200)
    role: str = Field(default="user", pattern="^(user|admin)$")
    max_concurrent_jobs: int = Field(default=5, ge=1, le=50)
    monthly_quota_minutes: int = Field(default=10000, ge=0)
    expires_days: Optional[int] = Field(None, ge=1, le=365)
    metadata: Optional[str] = Field(None, max_length=1000)


class ApiKeyResponse(BaseModel):
    """Response schema for API key information."""
    model_config = ConfigDict(from_attributes=True)
    
    id: UUID
    name: str
    prefix: str  # Only show prefix, never the full key
    status: ApiKeyStatus
    role: str
    max_concurrent_jobs: int
    monthly_quota_minutes: int
    
    # Usage statistics
    total_jobs_created: int
    total_minutes_processed: int
    last_used_at: Optional[datetime]
    
    # Timing
    created_at: datetime
    expires_at: Optional[datetime]
    
    # Owner info (limited)
    owner_name: Optional[str]
    
    # Never expose sensitive data
    # key_hash, owner_email, created_by, etc. are intentionally excluded


class ApiKeyCreateResponse(BaseModel):
    """Response after creating an API key."""
    api_key: ApiKeyResponse
    key: str  # Full key is only shown once during creation
    warning: str = "Store this key securely. It will not be shown again."


class ApiKeyListResponse(BaseModel):
    """Response for API key listing."""
    api_keys: list[ApiKeyResponse]
    total: int
    page: int
    per_page: int
    has_next: bool
    has_prev: bool


class ApiKeyUpdateRequest(BaseModel):
    """Request schema for updating an API key."""
    model_config = ConfigDict(extra="forbid")
    
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    status: Optional[ApiKeyStatus] = None
    max_concurrent_jobs: Optional[int] = Field(None, ge=1, le=50)
    monthly_quota_minutes: Optional[int] = Field(None, ge=0)
    expires_days: Optional[int] = Field(None, ge=1, le=365)
    metadata: Optional[str] = Field(None, max_length=1000)


class ApiKeyUser(BaseModel):
    """User information derived from API key."""
    id: str
    api_key_id: Optional[UUID]
    api_key_prefix: str
    role: str
    max_concurrent_jobs: int
    monthly_quota_minutes: int
    is_admin: bool
    
    # Usage info
    total_jobs_created: int
    total_minutes_processed: int
    last_used_at: Optional[datetime]
    
    @property
    def quota(self) -> Dict[str, Any]:
        """Get quota information."""
        return {
            "concurrent_jobs": self.max_concurrent_jobs,
            "monthly_minutes": self.monthly_quota_minutes,
        }