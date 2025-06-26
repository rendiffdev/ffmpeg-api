"""
Job models for database and API schemas
"""
from datetime import datetime
from enum import Enum
from typing import Optional, Dict, Any, List
from uuid import UUID, uuid4

from sqlalchemy import Column, String, JSON, DateTime, Float, Integer, Boolean, Index, Text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.types import TypeDecorator, CHAR
import uuid
from pydantic import BaseModel, Field, ConfigDict

Base = declarative_base()


class GUID(TypeDecorator):
    """Platform-agnostic GUID type for SQLite and PostgreSQL compatibility."""
    impl = CHAR
    cache_ok = True

    def load_dialect_impl(self, dialect):
        if dialect.name == 'postgresql':
            return dialect.type_descriptor(CHAR(36))
        else:
            return dialect.type_descriptor(CHAR(36))

    def process_bind_param(self, value, dialect):
        if value is None:
            return value
        elif isinstance(value, UUID):
            return str(value)
        else:
            return str(UUID(value))

    def process_result_value(self, value, dialect):
        if value is None:
            return value
        else:
            return UUID(value)


class JobStatus(str, Enum):
    """Job status enumeration."""
    QUEUED = "queued"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class JobPriority(str, Enum):
    """Job priority levels."""
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"


class Job(Base):
    """Database model for jobs."""
    __tablename__ = "jobs"
    
    id = Column(GUID(), primary_key=True, default=uuid4)
    status = Column(String, default=JobStatus.QUEUED, nullable=False, index=True)
    priority = Column(String, default=JobPriority.NORMAL, nullable=False)
    
    # Input/Output
    input_path = Column(String, nullable=False)
    output_path = Column(String, nullable=False)
    input_metadata = Column(JSON, default={})
    output_metadata = Column(JSON, default={})
    
    # Processing options
    options = Column(JSON, default={})
    operations = Column(JSON, default=[])
    
    # Progress tracking
    progress = Column(Float, default=0.0)
    stage = Column(String, default="queued")
    fps = Column(Float, nullable=True)
    eta_seconds = Column(Integer, nullable=True)
    
    # Quality metrics
    vmaf_score = Column(Float, nullable=True)
    psnr_score = Column(Float, nullable=True)
    ssim_score = Column(Float, nullable=True)
    
    # Timing
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    
    # Error handling
    error_message = Column(String, nullable=True)
    error_details = Column(JSON, nullable=True)
    retry_count = Column(Integer, default=0)
    
    # Resource tracking
    worker_id = Column(String, nullable=True)
    processing_time = Column(Float, nullable=True)
    
    # API key tracking (optional)
    api_key = Column(String, nullable=True, index=True)
    
    # Webhook
    webhook_url = Column(String, nullable=True)
    webhook_events = Column(JSON, default=["complete", "error"])
    
    # Indexes
    __table_args__ = (
        Index("idx_job_status_created", "status", "created_at"),
        Index("idx_job_api_key_created", "api_key", "created_at"),
    )


# Pydantic schemas for API
class ConvertRequest(BaseModel):
    """Request schema for conversion endpoint."""
    model_config = ConfigDict(extra="forbid")
    
    input: str | Dict[str, Any]
    output: str | Dict[str, Any]
    operations: List[Dict[str, Any]] = Field(default_factory=list)
    options: Dict[str, Any] = Field(default_factory=dict)
    priority: JobPriority = JobPriority.NORMAL
    webhook_url: Optional[str] = None
    webhook_events: List[str] = Field(default=["complete", "error"])


class JobResponse(BaseModel):
    """Response schema for job information."""
    model_config = ConfigDict(from_attributes=True)
    
    id: UUID
    status: JobStatus
    priority: JobPriority
    progress: float
    stage: str
    created_at: datetime
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    eta_seconds: Optional[int] = None
    
    # URLs for accessing job
    links: Dict[str, str] = Field(default_factory=dict)
    
    # Error info if failed
    error: Optional[Dict[str, Any]] = None
    
    # Progress details
    progress_details: Optional[Dict[str, Any]] = None


class JobProgress(BaseModel):
    """Progress update schema."""
    percentage: float
    stage: str
    fps: Optional[float] = None
    bitrate: Optional[str] = None
    size_bytes: Optional[int] = None
    time_elapsed: Optional[float] = None
    eta_seconds: Optional[int] = None
    
    # Quality metrics if available
    quality: Optional[Dict[str, float]] = None


class JobListResponse(BaseModel):
    """Response for job listing."""
    jobs: List[JobResponse]
    total: int
    page: int
    per_page: int
    has_next: bool
    has_prev: bool


class JobCreateResponse(BaseModel):
    """Response after creating a job."""
    job: JobResponse
    estimated_cost: Optional[Dict[str, Any]] = None
    warnings: List[str] = Field(default_factory=list)