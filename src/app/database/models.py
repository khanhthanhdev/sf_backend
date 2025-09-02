"""
SQLAlchemy database models for AWS RDS integration.

This module defines the database schema using SQLAlchemy ORM models
that correspond to the existing Pydantic models.
"""

from datetime import datetime
from typing import Optional, Dict, Any
import uuid

from sqlalchemy import (
    Column, String, DateTime, JSON, ForeignKey, 
    BigInteger, Boolean, Text, Integer, Index
)
from sqlalchemy.types import DECIMAL
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

Base = declarative_base()


class User(Base):
    """User database model corresponding to ClerkUser Pydantic model."""
    
    __tablename__ = 'users'
    
    # Primary key
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    
    # Clerk integration
    clerk_user_id = Column(String(255), unique=True, nullable=False, index=True)
    
    # Basic user information
    username = Column(String(255), nullable=True, index=True)
    first_name = Column(String(255), nullable=True)
    last_name = Column(String(255), nullable=True)
    image_url = Column(Text, nullable=True)
    
    # Contact information (stored as JSON for flexibility)
    email_addresses = Column(JSON, nullable=False, default=list)
    phone_numbers = Column(JSON, nullable=False, default=list)
    
    # Primary contact info (denormalized for performance)
    primary_email = Column(String(255), nullable=True, index=True)
    primary_phone = Column(String(50), nullable=True)
    
    # Account status and verification
    email_verified = Column(Boolean, default=False, nullable=False)
    phone_verified = Column(Boolean, default=False, nullable=False)
    two_factor_enabled = Column(Boolean, default=False, nullable=False)
    
    # User role and status
    role = Column(String(50), default='user', nullable=False, index=True)
    status = Column(String(50), default='active', nullable=False, index=True)
    
    # Timestamps
    created_at = Column(DateTime, default=func.now(), nullable=False)
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now(), nullable=False)
    last_sign_in_at = Column(DateTime, nullable=True)
    last_active_at = Column(DateTime, nullable=True)
    
    # Metadata from Clerk
    user_metadata = Column(JSON, nullable=False, default=dict)
    
    # Soft delete support
    is_deleted = Column(Boolean, default=False, nullable=False)
    deleted_at = Column(DateTime, nullable=True)
    
    # Relationships
    jobs = relationship("Job", back_populates="user", cascade="all, delete-orphan")
    files = relationship("FileMetadata", back_populates="user", cascade="all, delete-orphan")
    
    # Indexes for performance
    __table_args__ = (
        Index('idx_users_clerk_id', 'clerk_user_id'),
        Index('idx_users_email', 'primary_email'),
        Index('idx_users_role_status', 'role', 'status'),
        Index('idx_users_created_at', 'created_at'),
        Index('idx_users_active', 'is_deleted', 'status'),
    )
    
    def __repr__(self):
        return f"<User(id={self.id}, clerk_id={self.clerk_user_id}, email={self.primary_email})>"


class Job(Base):
    """Job database model corresponding to Job Pydantic model."""
    
    __tablename__ = 'jobs'
    
    # Primary key
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    
    # Foreign key to user
    user_id = Column(UUID(as_uuid=True), ForeignKey('users.id'), nullable=False, index=True)
    
    # Job type and priority
    job_type = Column(String(50), default='video_generation', nullable=False, index=True)
    priority = Column(String(20), default='normal', nullable=False, index=True)
    
    # Job configuration (stored as JSON)
    configuration = Column(JSON, nullable=False)
    
    # Status and progress tracking
    status = Column(String(50), default='queued', nullable=False, index=True)
    progress_percentage = Column(DECIMAL(5, 2), default=0, nullable=False)
    current_stage = Column(String(100), nullable=True)
    stages_completed = Column(JSON, nullable=False, default=list)
    estimated_completion = Column(DateTime, nullable=True)
    processing_time_seconds = Column(DECIMAL(10, 2), nullable=True)
    
    # Error handling
    error_info = Column(JSON, nullable=True)
    
    # Performance metrics
    metrics = Column(JSON, nullable=True)
    
    # Result data
    result_url = Column(String(500), nullable=True)
    
    # Timestamps
    created_at = Column(DateTime, default=func.now(), nullable=False)
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now(), nullable=False)
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    
    # Batch job support
    batch_id = Column(UUID(as_uuid=True), nullable=True, index=True)
    parent_job_id = Column(UUID(as_uuid=True), ForeignKey('jobs.id'), nullable=True)
    
    # Soft delete support
    is_deleted = Column(Boolean, default=False, nullable=False)
    deleted_at = Column(DateTime, nullable=True)
    
    # Relationships
    user = relationship("User", back_populates="jobs")
    files = relationship("FileMetadata", back_populates="job", cascade="all, delete-orphan")
    queue_entries = relationship("JobQueue", back_populates="job", cascade="all, delete-orphan")
    child_jobs = relationship("Job", backref="parent_job", remote_side=[id])
    
    # Indexes for performance
    __table_args__ = (
        Index('idx_jobs_user_id', 'user_id'),
        Index('idx_jobs_status', 'status'),
        Index('idx_jobs_priority', 'priority'),
        Index('idx_jobs_type', 'job_type'),
        Index('idx_jobs_batch_id', 'batch_id'),
        Index('idx_jobs_created_at', 'created_at'),
        Index('idx_jobs_user_status', 'user_id', 'status'),
        Index('idx_jobs_active', 'is_deleted', 'status'),
        Index('idx_jobs_queue_priority', 'status', 'priority', 'created_at'),
    )
    
    def __repr__(self):
        return f"<Job(id={self.id}, user_id={self.user_id}, status={self.status})>"


class FileMetadata(Base):
    """File metadata database model."""
    
    __tablename__ = 'file_metadata'
    
    # Primary key
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    
    # Foreign keys
    user_id = Column(UUID(as_uuid=True), ForeignKey('users.id'), nullable=False, index=True)
    job_id = Column(UUID(as_uuid=True), ForeignKey('jobs.id'), nullable=True, index=True)
    
    # File information
    file_type = Column(String(50), nullable=False, index=True)
    original_filename = Column(String(255), nullable=False)
    stored_filename = Column(String(255), nullable=False)
    
    # S3 storage information
    s3_bucket = Column(String(255), nullable=False)
    s3_key = Column(String(500), nullable=False, index=True)
    s3_version_id = Column(String(255), nullable=True)
    
    # File properties
    file_size = Column(BigInteger, nullable=False)
    content_type = Column(String(100), nullable=False)
    checksum = Column(String(64), nullable=True)  # SHA-256 hash
    
    # File-specific metadata (dimensions, duration, etc.)
    file_metadata = Column(JSON, nullable=False, default=dict)
    
    # Access and organization
    description = Column(Text, nullable=True)
    tags = Column(JSON, nullable=False, default=list)
    
    # Timestamps
    created_at = Column(DateTime, default=func.now(), nullable=False)
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now(), nullable=False)
    last_accessed_at = Column(DateTime, nullable=True)
    
    # Soft delete support
    is_deleted = Column(Boolean, default=False, nullable=False)
    deleted_at = Column(DateTime, nullable=True)
    
    # Relationships
    user = relationship("User", back_populates="files")
    job = relationship("Job", back_populates="files")
    
    # Indexes for performance
    __table_args__ = (
        Index('idx_files_user_id', 'user_id'),
        Index('idx_files_job_id', 'job_id'),
        Index('idx_files_type', 'file_type'),
        Index('idx_files_s3_key', 's3_key'),
        Index('idx_files_created_at', 'created_at'),
        Index('idx_files_user_type', 'user_id', 'file_type'),
        Index('idx_files_active', 'is_deleted'),
    )
    
    def __repr__(self):
        return f"<FileMetadata(id={self.id}, filename={self.original_filename}, type={self.file_type})>"


class JobQueue(Base):
    """Job queue database model for managing job processing order."""
    
    __tablename__ = 'job_queue'
    
    # Primary key
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    
    # Foreign key to job
    job_id = Column(UUID(as_uuid=True), ForeignKey('jobs.id'), nullable=False, unique=True, index=True)
    
    # Queue management
    priority = Column(String(20), default='normal', nullable=False, index=True)
    queue_status = Column(String(50), default='queued', nullable=False, index=True)
    
    # Processing information
    worker_id = Column(String(255), nullable=True)  # ID of worker processing the job
    processing_node = Column(String(255), nullable=True)  # Node/server processing the job
    
    # Timestamps
    queued_at = Column(DateTime, default=func.now(), nullable=False)
    processing_started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    
    # Retry logic
    retry_count = Column(Integer, default=0, nullable=False)
    max_retries = Column(Integer, default=3, nullable=False)
    next_retry_at = Column(DateTime, nullable=True)
    
    # Queue position (for ordering)
    queue_position = Column(Integer, nullable=True, index=True)
    
    # Relationships
    job = relationship("Job", back_populates="queue_entries")
    
    # Indexes for performance
    __table_args__ = (
        Index('idx_queue_job_id', 'job_id'),
        Index('idx_queue_status', 'queue_status'),
        Index('idx_queue_priority', 'priority'),
        Index('idx_queue_position', 'queue_position'),
        Index('idx_queue_processing', 'queue_status', 'priority', 'queued_at'),
        Index('idx_queue_retry', 'next_retry_at', 'retry_count'),
    )
    
    def __repr__(self):
        return f"<JobQueue(id={self.id}, job_id={self.job_id}, status={self.queue_status})>"