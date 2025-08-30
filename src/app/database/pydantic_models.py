"""
Extended Pydantic models with database integration.

This module extends the existing Pydantic models with database-specific
functionality, including conversion methods and database field mappings.
"""

from datetime import datetime
from typing import Optional, Dict, Any, List, Union
from uuid import UUID
import uuid

from pydantic import BaseModel, Field, validator, ConfigDict
from sqlalchemy.orm import Session

from ..models.user import ClerkUser, UserProfile, UserRole, UserStatus
from ..models.job import Job as JobModel, JobStatus, JobType, JobPriority, JobConfiguration, JobProgress, JobError, JobMetrics
from ..models.file import FileType
from . import models as db_models


class DatabaseMixin(BaseModel):
    """Mixin class for database integration functionality."""
    
    model_config = ConfigDict(from_attributes=True)
    
    @classmethod
    def from_db(cls, db_obj):
        """Create Pydantic model from SQLAlchemy database object."""
        if db_obj is None:
            return None
        return cls.model_validate(db_obj)
    
    def to_db_dict(self, exclude_none: bool = True) -> Dict[str, Any]:
        """Convert to dictionary suitable for database operations."""
        data = self.model_dump(exclude_none=exclude_none)
        return data


class UserDB(DatabaseMixin):
    """Database-integrated User model."""
    
    # Database fields
    id: Optional[UUID] = Field(default_factory=uuid.uuid4)
    clerk_user_id: str = Field(..., description="Clerk user ID")
    
    # Basic user information
    username: Optional[str] = None
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    image_url: Optional[str] = None
    
    # Contact information
    email_addresses: List[Dict[str, Any]] = Field(default_factory=list)
    phone_numbers: List[Dict[str, Any]] = Field(default_factory=list)
    primary_email: Optional[str] = None
    primary_phone: Optional[str] = None
    
    # Account status and verification
    email_verified: bool = False
    phone_verified: bool = False
    two_factor_enabled: bool = False
    
    # User role and status
    role: UserRole = UserRole.USER
    status: UserStatus = UserStatus.ACTIVE
    
    # Timestamps
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    last_sign_in_at: Optional[datetime] = None
    last_active_at: Optional[datetime] = None
    
    # Metadata
    metadata: Dict[str, Any] = Field(default_factory=dict)
    
    # Soft delete
    is_deleted: bool = False
    deleted_at: Optional[datetime] = None
    
    @classmethod
    def from_clerk_user(cls, clerk_user: ClerkUser) -> "UserDB":
        """Create UserDB from ClerkUser."""
        return cls(
            clerk_user_id=clerk_user.id,
            username=clerk_user.username,
            first_name=clerk_user.first_name,
            last_name=clerk_user.last_name,
            image_url=clerk_user.image_url,
            email_addresses=[addr.model_dump() for addr in clerk_user.email_addresses],
            phone_numbers=[phone.model_dump() for phone in clerk_user.phone_numbers],
            primary_email=clerk_user.primary_email,
            primary_phone=clerk_user.primary_phone,
            email_verified=clerk_user.email_verified,
            phone_verified=clerk_user.phone_verified,
            two_factor_enabled=clerk_user.two_factor_enabled,
            role=clerk_user.role,
            status=clerk_user.status,
            created_at=clerk_user.created_at,
            updated_at=clerk_user.updated_at,
            last_sign_in_at=clerk_user.last_sign_in_at,
            last_active_at=clerk_user.last_active_at,
            metadata=clerk_user.metadata.model_dump()
        )
    
    def to_user_profile(self) -> UserProfile:
        """Convert to UserProfile for API responses."""
        full_name = " ".join(filter(None, [self.first_name, self.last_name])) or self.username or "Unknown User"
        return UserProfile(
            id=str(self.id),
            username=self.username,
            full_name=full_name,
            email=self.primary_email,
            image_url=self.image_url,
            email_verified=self.email_verified,
            created_at=self.created_at,
            last_sign_in_at=self.last_sign_in_at
        )
    
    async def save_to_db(self, session: Session) -> db_models.User:
        """Save to database and return SQLAlchemy object."""
        db_data = self.to_db_dict()
        
        # Check if user exists
        existing_user = session.query(db_models.User).filter(
            db_models.User.clerk_user_id == self.clerk_user_id
        ).first()
        
        if existing_user:
            # Update existing user
            for key, value in db_data.items():
                if hasattr(existing_user, key):
                    setattr(existing_user, key, value)
            db_user = existing_user
        else:
            # Create new user
            db_user = db_models.User(**db_data)
            session.add(db_user)
        
        session.commit()
        session.refresh(db_user)
        return db_user


class JobDB(DatabaseMixin):
    """Database-integrated Job model."""
    
    # Database fields
    id: Optional[UUID] = Field(default_factory=uuid.uuid4)
    user_id: UUID = Field(..., description="User ID")
    
    # Job type and priority
    job_type: JobType = JobType.VIDEO_GENERATION
    priority: JobPriority = JobPriority.NORMAL
    
    # Job configuration
    configuration: Dict[str, Any] = Field(..., description="Job configuration")
    
    # Status and progress
    status: JobStatus = JobStatus.QUEUED
    progress_percentage: float = Field(default=0.0, ge=0.0, le=100.0)
    current_stage: Optional[str] = None
    stages_completed: List[str] = Field(default_factory=list)
    estimated_completion: Optional[datetime] = None
    processing_time_seconds: Optional[float] = None
    
    # Error handling
    error_info: Optional[Dict[str, Any]] = None
    
    # Performance metrics
    metrics: Optional[Dict[str, Any]] = None
    
    # Timestamps
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    
    # Batch job support
    batch_id: Optional[UUID] = None
    parent_job_id: Optional[UUID] = None
    
    # Soft delete
    is_deleted: bool = False
    deleted_at: Optional[datetime] = None
    
    @classmethod
    def from_job_model(cls, job: JobModel, user_id: UUID) -> "JobDB":
        """Create JobDB from Job Pydantic model."""
        return cls(
            id=UUID(job.id) if job.id else uuid.uuid4(),
            user_id=user_id,
            job_type=job.job_type,
            priority=job.priority,
            configuration=job.configuration.model_dump(),
            status=job.status,
            progress_percentage=job.progress.percentage,
            current_stage=job.progress.current_stage,
            stages_completed=job.progress.stages_completed,
            estimated_completion=job.progress.estimated_completion,
            processing_time_seconds=job.progress.processing_time_seconds,
            error_info=job.error.model_dump() if job.error else None,
            metrics=job.metrics.model_dump() if job.metrics else None,
            created_at=job.created_at,
            updated_at=job.updated_at,
            started_at=job.started_at,
            completed_at=job.completed_at,
            batch_id=UUID(job.batch_id) if job.batch_id else None,
            parent_job_id=UUID(job.parent_job_id) if job.parent_job_id else None,
            is_deleted=job.is_deleted,
            deleted_at=job.deleted_at
        )
    
    def to_job_model(self) -> JobModel:
        """Convert to Job Pydantic model."""
        # Reconstruct JobConfiguration
        config = JobConfiguration(**self.configuration)
        
        # Reconstruct JobProgress
        progress = JobProgress(
            percentage=self.progress_percentage,
            current_stage=self.current_stage,
            stages_completed=self.stages_completed,
            estimated_completion=self.estimated_completion,
            processing_time_seconds=self.processing_time_seconds
        )
        
        # Reconstruct JobError if exists
        error = None
        if self.error_info:
            error = JobError(**self.error_info)
        
        # Reconstruct JobMetrics if exists
        metrics = None
        if self.metrics:
            metrics = JobMetrics(**self.metrics)
        
        return JobModel(
            id=str(self.id),
            user_id=str(self.user_id),
            job_type=self.job_type,
            priority=self.priority,
            configuration=config,
            status=self.status,
            progress=progress,
            error=error,
            metrics=metrics,
            created_at=self.created_at,
            updated_at=self.updated_at,
            started_at=self.started_at,
            completed_at=self.completed_at,
            batch_id=str(self.batch_id) if self.batch_id else None,
            parent_job_id=str(self.parent_job_id) if self.parent_job_id else None,
            is_deleted=self.is_deleted,
            deleted_at=self.deleted_at
        )
    
    async def save_to_db(self, session: Session) -> db_models.Job:
        """Save to database and return SQLAlchemy object."""
        db_data = self.to_db_dict()
        
        # Check if job exists
        existing_job = session.query(db_models.Job).filter(
            db_models.Job.id == self.id
        ).first()
        
        if existing_job:
            # Update existing job
            for key, value in db_data.items():
                if hasattr(existing_job, key):
                    setattr(existing_job, key, value)
            db_job = existing_job
        else:
            # Create new job
            db_job = db_models.Job(**db_data)
            session.add(db_job)
        
        session.commit()
        session.refresh(db_job)
        return db_job


class FileMetadataDB(DatabaseMixin):
    """Database-integrated FileMetadata model."""
    
    # Database fields
    id: Optional[UUID] = Field(default_factory=uuid.uuid4)
    user_id: UUID = Field(..., description="User ID")
    job_id: Optional[UUID] = None
    
    # File information
    file_type: str = Field(..., description="File type")
    original_filename: str = Field(..., description="Original filename")
    stored_filename: str = Field(..., description="Stored filename")
    
    # S3 storage information
    s3_bucket: str = Field(..., description="S3 bucket name")
    s3_key: str = Field(..., description="S3 object key")
    s3_version_id: Optional[str] = None
    
    # File properties
    file_size: int = Field(..., ge=0, description="File size in bytes")
    content_type: str = Field(..., description="MIME content type")
    checksum: Optional[str] = None
    
    # File-specific metadata
    metadata: Dict[str, Any] = Field(default_factory=dict)
    
    # Access and organization
    description: Optional[str] = None
    tags: List[str] = Field(default_factory=list)
    
    # Timestamps
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    last_accessed_at: Optional[datetime] = None
    
    # Soft delete
    is_deleted: bool = False
    deleted_at: Optional[datetime] = None
    
    @validator("file_type")
    def validate_file_type(cls, v):
        """Validate file type is supported."""
        valid_types = [ft.value for ft in FileType]
        if v not in valid_types:
            raise ValueError(f"File type must be one of: {valid_types}")
        return v
    
    async def save_to_db(self, session: Session) -> db_models.FileMetadata:
        """Save to database and return SQLAlchemy object."""
        db_data = self.to_db_dict()
        
        # Check if file exists
        existing_file = session.query(db_models.FileMetadata).filter(
            db_models.FileMetadata.id == self.id
        ).first()
        
        if existing_file:
            # Update existing file
            for key, value in db_data.items():
                if hasattr(existing_file, key):
                    setattr(existing_file, key, value)
            db_file = existing_file
        else:
            # Create new file
            db_file = db_models.FileMetadata(**db_data)
            session.add(db_file)
        
        session.commit()
        session.refresh(db_file)
        return db_file


class JobQueueDB(DatabaseMixin):
    """Database-integrated JobQueue model."""
    
    # Database fields
    id: Optional[UUID] = Field(default_factory=uuid.uuid4)
    job_id: UUID = Field(..., description="Job ID")
    
    # Queue management
    priority: JobPriority = JobPriority.NORMAL
    queue_status: str = Field(default="queued", description="Queue status")
    
    # Processing information
    worker_id: Optional[str] = None
    processing_node: Optional[str] = None
    
    # Timestamps
    queued_at: datetime = Field(default_factory=datetime.utcnow)
    processing_started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    
    # Retry logic
    retry_count: int = Field(default=0, ge=0)
    max_retries: int = Field(default=3, ge=0)
    next_retry_at: Optional[datetime] = None
    
    # Queue position
    queue_position: Optional[int] = None
    
    async def save_to_db(self, session: Session) -> db_models.JobQueue:
        """Save to database and return SQLAlchemy object."""
        db_data = self.to_db_dict()
        
        # Check if queue entry exists
        existing_entry = session.query(db_models.JobQueue).filter(
            db_models.JobQueue.job_id == self.job_id
        ).first()
        
        if existing_entry:
            # Update existing entry
            for key, value in db_data.items():
                if hasattr(existing_entry, key):
                    setattr(existing_entry, key, value)
            db_entry = existing_entry
        else:
            # Create new entry
            db_entry = db_models.JobQueue(**db_data)
            session.add(db_entry)
        
        session.commit()
        session.refresh(db_entry)
        return db_entry


# Query helper classes for database operations

class UserQueries:
    """Helper class for user database queries."""
    
    @staticmethod
    def get_by_clerk_id(session: Session, clerk_user_id: str) -> Optional[db_models.User]:
        """Get user by Clerk user ID."""
        return session.query(db_models.User).filter(
            db_models.User.clerk_user_id == clerk_user_id,
            db_models.User.is_deleted == False
        ).first()
    
    @staticmethod
    def get_by_email(session: Session, email: str) -> Optional[db_models.User]:
        """Get user by primary email."""
        return session.query(db_models.User).filter(
            db_models.User.primary_email == email,
            db_models.User.is_deleted == False
        ).first()
    
    @staticmethod
    def get_active_users(session: Session, limit: int = 100, offset: int = 0) -> List[db_models.User]:
        """Get active users with pagination."""
        return session.query(db_models.User).filter(
            db_models.User.is_deleted == False,
            db_models.User.status == UserStatus.ACTIVE
        ).offset(offset).limit(limit).all()


class JobQueries:
    """Helper class for job database queries."""
    
    @staticmethod
    def get_user_jobs(session: Session, user_id: UUID, status: Optional[JobStatus] = None, 
                     limit: int = 100, offset: int = 0) -> List[db_models.Job]:
        """Get jobs for a user with optional status filter."""
        query = session.query(db_models.Job).filter(
            db_models.Job.user_id == user_id,
            db_models.Job.is_deleted == False
        )
        
        if status:
            query = query.filter(db_models.Job.status == status)
        
        return query.order_by(db_models.Job.created_at.desc()).offset(offset).limit(limit).all()
    
    @staticmethod
    def get_queued_jobs(session: Session, limit: int = 100) -> List[db_models.Job]:
        """Get queued jobs ordered by priority and creation time."""
        return session.query(db_models.Job).filter(
            db_models.Job.status == JobStatus.QUEUED,
            db_models.Job.is_deleted == False
        ).order_by(
            db_models.Job.priority.desc(),
            db_models.Job.created_at.asc()
        ).limit(limit).all()
    
    @staticmethod
    def get_active_jobs(session: Session, limit: int = 100) -> List[db_models.Job]:
        """Get active (queued or processing) jobs."""
        return session.query(db_models.Job).filter(
            db_models.Job.status.in_([JobStatus.QUEUED, JobStatus.PROCESSING]),
            db_models.Job.is_deleted == False
        ).order_by(db_models.Job.created_at.desc()).limit(limit).all()


class FileQueries:
    """Helper class for file database queries."""
    
    @staticmethod
    def get_user_files(session: Session, user_id: UUID, file_type: Optional[str] = None,
                      limit: int = 100, offset: int = 0) -> List[db_models.FileMetadata]:
        """Get files for a user with optional type filter."""
        query = session.query(db_models.FileMetadata).filter(
            db_models.FileMetadata.user_id == user_id,
            db_models.FileMetadata.is_deleted == False
        )
        
        if file_type:
            query = query.filter(db_models.FileMetadata.file_type == file_type)
        
        return query.order_by(db_models.FileMetadata.created_at.desc()).offset(offset).limit(limit).all()
    
    @staticmethod
    def get_job_files(session: Session, job_id: UUID) -> List[db_models.FileMetadata]:
        """Get all files associated with a job."""
        return session.query(db_models.FileMetadata).filter(
            db_models.FileMetadata.job_id == job_id,
            db_models.FileMetadata.is_deleted == False
        ).order_by(db_models.FileMetadata.created_at.asc()).all()