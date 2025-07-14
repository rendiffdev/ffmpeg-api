"""
Batch processing models
"""
from typing import List, Optional, Dict, Any
from datetime import datetime
from enum import Enum
from uuid import uuid4

from sqlalchemy import Column, String, DateTime, Integer, JSON, ForeignKey, Text, Boolean
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from pydantic import BaseModel, Field

from api.models.database import Base


class BatchStatus(str, Enum):
    """Batch processing status."""
    PENDING = "pending"
    PROCESSING = "processing" 
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class BatchJob(Base):
    """Batch job database model."""
    
    __tablename__ = "batch_jobs"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    name = Column(String(255), nullable=False)
    description = Column(Text)
    status = Column(String(50), default=BatchStatus.PENDING, nullable=False)
    
    # User and authentication
    user_id = Column(String(255), nullable=False)
    api_key_id = Column(UUID(as_uuid=True), nullable=True)
    
    # Batch configuration
    total_jobs = Column(Integer, default=0)
    completed_jobs = Column(Integer, default=0)
    failed_jobs = Column(Integer, default=0)
    processing_jobs = Column(Integer, default=0)
    
    # Processing settings
    max_concurrent_jobs = Column(Integer, default=5)
    priority = Column(Integer, default=0)  # Higher number = higher priority
    
    # Metadata
    input_settings = Column(JSON)  # Common settings for all jobs in batch
    metadata = Column(JSON)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    started_at = Column(DateTime)
    completed_at = Column(DateTime)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Error handling
    error_message = Column(Text)
    retry_count = Column(Integer, default=0)
    max_retries = Column(Integer, default=3)
    
    # Relationships
    individual_jobs = relationship("Job", back_populates="batch_job", cascade="all, delete-orphan")
    
    def __repr__(self):
        return f"<BatchJob(id={self.id}, name={self.name}, status={self.status})>"
    
    @property
    def progress_percentage(self) -> float:
        """Calculate completion percentage."""
        if self.total_jobs == 0:
            return 0.0
        return (self.completed_jobs / self.total_jobs) * 100
    
    @property
    def is_complete(self) -> bool:
        """Check if batch is complete."""
        return self.status in [BatchStatus.COMPLETED, BatchStatus.FAILED, BatchStatus.CANCELLED]
    
    @property
    def success_rate(self) -> float:
        """Calculate success rate."""
        if self.total_jobs == 0:
            return 0.0
        return (self.completed_jobs / self.total_jobs) * 100


# Pydantic models for API

class BatchJobCreate(BaseModel):
    """Batch job creation request."""
    name: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = None
    max_concurrent_jobs: int = Field(default=5, ge=1, le=20)
    priority: int = Field(default=0, ge=0, le=10)
    input_settings: Optional[Dict[str, Any]] = None
    metadata: Optional[Dict[str, Any]] = None
    max_retries: int = Field(default=3, ge=0, le=10)
    
    # List of files/jobs to process
    files: List[Dict[str, Any]] = Field(..., min_items=1, max_items=1000)
    

class BatchJobResponse(BaseModel):
    """Batch job response."""
    id: str
    name: str
    description: Optional[str]
    status: BatchStatus
    user_id: str
    
    total_jobs: int
    completed_jobs: int
    failed_jobs: int
    processing_jobs: int
    
    max_concurrent_jobs: int
    priority: int
    progress_percentage: float
    success_rate: float
    
    created_at: datetime
    started_at: Optional[datetime]
    completed_at: Optional[datetime]
    updated_at: datetime
    
    error_message: Optional[str]
    retry_count: int
    max_retries: int
    
    metadata: Optional[Dict[str, Any]]
    
    class Config:
        from_attributes = True


class BatchJobUpdate(BaseModel):
    """Batch job update request."""
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = None
    priority: Optional[int] = Field(None, ge=0, le=10)
    max_concurrent_jobs: Optional[int] = Field(None, ge=1, le=20)
    status: Optional[BatchStatus] = None
    metadata: Optional[Dict[str, Any]] = None


class BatchJobListResponse(BaseModel):
    """Batch job list response."""
    batches: List[BatchJobResponse]
    total: int
    page: int
    per_page: int
    total_pages: int


class BatchJobStats(BaseModel):
    """Batch job statistics."""
    total_batches: int
    pending_batches: int
    processing_batches: int
    completed_batches: int
    failed_batches: int
    
    total_jobs_in_batches: int
    avg_jobs_per_batch: float
    avg_completion_time_minutes: Optional[float]
    overall_success_rate: float


class BatchJobProgress(BaseModel):
    """Batch job progress update."""
    batch_id: str
    status: BatchStatus
    total_jobs: int
    completed_jobs: int
    failed_jobs: int
    processing_jobs: int
    progress_percentage: float
    current_job_id: Optional[str]
    estimated_completion: Optional[datetime]
    error_message: Optional[str]