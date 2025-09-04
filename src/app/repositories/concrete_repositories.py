"""
Concrete Repository Implementations.

This module provides concrete implementations of repository interfaces
for specific domain entities (User, Job, Video, File).
"""

import logging
from typing import Optional, List
from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_

from .base_repository import BaseRepository, IUserRepository, IJobRepository, IVideoRepository, IFileRepository, PaginatedResult
from ..database.models import User as UserDB, Job as JobDB, VideoMetadata as VideoDB, FileMetadata as FileDB
from ..models.user import ClerkUser
from ..models.job import Job
from ..models.video import VideoMetadata
from ..models.file import FileMetadataResponse as FileMetadata
from ..schemas.common import PaginationRequest
from ..interfaces.base import ServiceResult

logger = logging.getLogger(__name__)


class UserRepository(BaseRepository[ClerkUser], IUserRepository[ClerkUser]):
    """Concrete implementation of user repository."""
    
    def __init__(self, session: AsyncSession):
        """Initialize user repository."""
        super().__init__(session, UserDB)
    
    async def get_by_clerk_id(self, clerk_id: str) -> ServiceResult[Optional[ClerkUser]]:
        """Get user by Clerk ID."""
        try:
            stmt = select(UserDB).where(UserDB.clerk_user_id == clerk_id)
            result = await self.session.execute(stmt)
            db_user = result.scalar_one_or_none()
            
            if db_user is None:
                return ServiceResult.success(None)
            
            domain_user = await self._to_domain_model(db_user)
            return ServiceResult.success(domain_user)
            
        except Exception as e:
            logger.error(f"Error getting user by Clerk ID {clerk_id}: {e}")
            return ServiceResult.error(
                error=f"Failed to get user by Clerk ID: {str(e)}",
                error_code="USER_REPOSITORY_GET_BY_CLERK_ID_ERROR"
            )
    
    async def get_by_email(self, email: str) -> ServiceResult[Optional[ClerkUser]]:
        """Get user by email."""
        try:
            stmt = select(UserDB).where(UserDB.primary_email == email)
            result = await self.session.execute(stmt)
            db_user = result.scalar_one_or_none()
            
            if db_user is None:
                return ServiceResult.success(None)
            
            domain_user = await self._to_domain_model(db_user)
            return ServiceResult.success(domain_user)
            
        except Exception as e:
            logger.error(f"Error getting user by email {email}: {e}")
            return ServiceResult.error(
                error=f"Failed to get user by email: {str(e)}",
                error_code="USER_REPOSITORY_GET_BY_EMAIL_ERROR"
            )
    
    async def _to_domain_model(self, db_user: UserDB) -> ClerkUser:
        """Convert database user model to domain model."""
        return ClerkUser(
            clerk_user_id=db_user.clerk_user_id,
            username=db_user.username,
            first_name=db_user.first_name,
            last_name=db_user.last_name,
            full_name=f"{db_user.first_name or ''} {db_user.last_name or ''}".strip(),
            email=db_user.primary_email,
            image_url=db_user.image_url,
            email_verified=db_user.email_verified,
            subscription_tier=db_user.user_metadata.get('subscription_tier', 'free') if db_user.user_metadata else 'free',
            created_at=db_user.created_at,
            last_active_at=db_user.updated_at
        )
    
    async def _to_db_model(self, domain_user: ClerkUser) -> UserDB:
        """Convert domain user model to database model."""
        return UserDB(
            clerk_user_id=domain_user.clerk_user_id,
            username=domain_user.username,
            first_name=domain_user.first_name,
            last_name=domain_user.last_name,
            primary_email=domain_user.email,
            image_url=domain_user.image_url,
            email_verified=domain_user.email_verified,
            user_metadata={'subscription_tier': domain_user.subscription_tier},
            created_at=domain_user.created_at or datetime.utcnow(),
            updated_at=domain_user.last_active_at or datetime.utcnow()
        )


class JobRepository(BaseRepository[Job], IJobRepository[Job]):
    """Concrete implementation of job repository."""
    
    def __init__(self, session: AsyncSession):
        """Initialize job repository."""
        super().__init__(session, JobDB)
    
    async def get_by_user_id(
        self,
        user_id: str,
        pagination: Optional[PaginationRequest] = None,
        status_filter: Optional[str] = None
    ) -> ServiceResult[PaginatedResult[Job]]:
        """Get jobs by user ID."""
        try:
            # Build filters
            filters = {"user_id": user_id}
            if status_filter:
                filters["status"] = status_filter
            
            # Use base repository list method
            return await self.list(
                filters=filters,
                pagination=pagination,
                order_by=["-created_at"]  # Newest first
            )
            
        except Exception as e:
            logger.error(f"Error getting jobs for user {user_id}: {e}")
            return ServiceResult.error(
                error=f"Failed to get jobs by user ID: {str(e)}",
                error_code="JOB_REPOSITORY_GET_BY_USER_ID_ERROR"
            )
    
    async def get_pending_jobs(self, limit: Optional[int] = None) -> ServiceResult[List[Job]]:
        """Get pending jobs for processing."""
        try:
            pagination = PaginationRequest(page=1, page_size=limit or 100)
            
            result = await self.list(
                filters={"status": "queued"},
                pagination=pagination,
                order_by=["created_at"]  # Oldest first (FIFO)
            )
            
            if result.success:
                return ServiceResult.success(result.data.items)
            else:
                return result
            
        except Exception as e:
            logger.error(f"Error getting pending jobs: {e}")
            return ServiceResult.error(
                error=f"Failed to get pending jobs: {str(e)}",
                error_code="JOB_REPOSITORY_GET_PENDING_ERROR"
            )
    
    async def update_status(self, job_id: str, status: str) -> ServiceResult[bool]:
        """Update job status."""
        try:
            # Get the job first
            job_result = await self.get_by_id(job_id)
            if not job_result.success or job_result.data is None:
                return ServiceResult.error(
                    error=f"Job {job_id} not found",
                    error_code="JOB_NOT_FOUND"
                )
            
            job = job_result.data
            job.status = status
            job.updated_at = datetime.utcnow()
            
            # Update the job
            update_result = await self.update(job)
            if update_result.success:
                return ServiceResult.success(True)
            else:
                return ServiceResult.error(
                    error=update_result.error,
                    error_code="JOB_STATUS_UPDATE_ERROR"
                )
            
        except Exception as e:
            logger.error(f"Error updating job status for {job_id}: {e}")
            return ServiceResult.error(
                error=f"Failed to update job status: {str(e)}",
                error_code="JOB_REPOSITORY_UPDATE_STATUS_ERROR"
            )
    
    async def _to_domain_model(self, db_job: JobDB) -> Job:
        """Convert database job model to domain model."""
        from ..models.job import JobType, JobStatus, JobPriority, JobProgress, JobConfiguration
        
        # Convert configuration
        config_data = db_job.configuration or {}
        configuration = JobConfiguration(**config_data) if config_data else None
        
        # Convert progress
        progress = JobProgress(
            percentage=db_job.progress_percentage or 0.0,
            current_stage=db_job.current_stage or "queued",
            stages_completed=db_job.stages_completed or [],
            estimated_completion=db_job.estimated_completion
        )
        
        return Job(
            id=db_job.id,
            user_id=db_job.user_id,
            job_type=JobType(db_job.job_type),
            priority=JobPriority(db_job.priority) if db_job.priority else JobPriority.NORMAL,
            configuration=configuration,
            status=JobStatus(db_job.status),
            progress=progress,
            result_data=db_job.result_data,
            error_message=db_job.error_message,
            created_at=db_job.created_at,
            updated_at=db_job.updated_at,
            started_at=db_job.started_at,
            completed_at=db_job.completed_at
        )
    
    async def _to_db_model(self, domain_job: Job) -> JobDB:
        """Convert domain job model to database model."""
        return JobDB(
            id=domain_job.id,
            user_id=domain_job.user_id,
            job_type=domain_job.job_type.value,
            priority=domain_job.priority.value if domain_job.priority else "normal",
            configuration=domain_job.configuration.dict() if domain_job.configuration else {},
            status=domain_job.status.value,
            progress_percentage=domain_job.progress.percentage if domain_job.progress else 0.0,
            current_stage=domain_job.progress.current_stage if domain_job.progress else "queued",
            stages_completed=domain_job.progress.stages_completed if domain_job.progress else [],
            estimated_completion=domain_job.progress.estimated_completion if domain_job.progress else None,
            result_data=domain_job.result_data,
            error_message=domain_job.error_message,
            created_at=domain_job.created_at or datetime.utcnow(),
            updated_at=domain_job.updated_at or datetime.utcnow(),
            started_at=domain_job.started_at,
            completed_at=domain_job.completed_at
        )


class VideoRepository(BaseRepository[VideoMetadata], IVideoRepository[VideoMetadata]):
    """Concrete implementation of video repository."""
    
    def __init__(self, session: AsyncSession):
        """Initialize video repository."""
        super().__init__(session, VideoDB)
    
    async def get_by_user_id(
        self,
        user_id: str,
        pagination: Optional[PaginationRequest] = None
    ) -> ServiceResult[PaginatedResult[VideoMetadata]]:
        """Get videos by user ID."""
        try:
            return await self.list(
                filters={"user_id": user_id},
                pagination=pagination,
                order_by=["-created_at"]  # Newest first
            )
            
        except Exception as e:
            logger.error(f"Error getting videos for user {user_id}: {e}")
            return ServiceResult.error(
                error=f"Failed to get videos by user ID: {str(e)}",
                error_code="VIDEO_REPOSITORY_GET_BY_USER_ID_ERROR"
            )
    
    async def get_by_status(
        self,
        status: str,
        pagination: Optional[PaginationRequest] = None
    ) -> ServiceResult[PaginatedResult[VideoMetadata]]:
        """Get videos by status."""
        try:
            return await self.list(
                filters={"status": status},
                pagination=pagination,
                order_by=["-created_at"]  # Newest first
            )
            
        except Exception as e:
            logger.error(f"Error getting videos by status {status}: {e}")
            return ServiceResult.error(
                error=f"Failed to get videos by status: {str(e)}",
                error_code="VIDEO_REPOSITORY_GET_BY_STATUS_ERROR"
            )
    
    async def _to_domain_model(self, db_video: VideoDB) -> VideoMetadata:
        """Convert database video model to domain model."""
        from ..models.video import VideoStatus
        
        return VideoMetadata(
            id=db_video.id,
            job_id=db_video.job_id,
            user_id=db_video.user_id,
            title=db_video.title,
            description=db_video.description,
            status=VideoStatus(db_video.status),
            file_path=db_video.file_path,
            file_size=db_video.file_size,
            duration=db_video.duration,
            resolution=db_video.resolution,
            format=db_video.format,
            thumbnail_path=db_video.thumbnail_path,
            metadata=db_video.metadata or {},
            created_at=db_video.created_at,
            updated_at=db_video.updated_at
        )
    
    async def _to_db_model(self, domain_video: VideoMetadata) -> VideoDB:
        """Convert domain video model to database model."""
        return VideoDB(
            id=domain_video.id,
            job_id=domain_video.job_id,
            user_id=domain_video.user_id,
            title=domain_video.title,
            description=domain_video.description,
            status=domain_video.status.value,
            file_path=domain_video.file_path,
            file_size=domain_video.file_size,
            duration=domain_video.duration,
            resolution=domain_video.resolution,
            format=domain_video.format,
            thumbnail_path=domain_video.thumbnail_path,
            metadata=domain_video.metadata,
            created_at=domain_video.created_at or datetime.utcnow(),
            updated_at=domain_video.updated_at or datetime.utcnow()
        )


class FileRepository(BaseRepository[FileMetadata], IFileRepository[FileMetadata]):
    """Concrete implementation of file repository."""
    
    def __init__(self, session: AsyncSession):
        """Initialize file repository."""
        super().__init__(session, FileDB)
    
    async def get_by_user_id(
        self,
        user_id: str,
        pagination: Optional[PaginationRequest] = None
    ) -> ServiceResult[PaginatedResult[FileMetadata]]:
        """Get files by user ID."""
        try:
            return await self.list(
                filters={"user_id": user_id},
                pagination=pagination,
                order_by=["-uploaded_at"]  # Newest first
            )
            
        except Exception as e:
            logger.error(f"Error getting files for user {user_id}: {e}")
            return ServiceResult.error(
                error=f"Failed to get files by user ID: {str(e)}",
                error_code="FILE_REPOSITORY_GET_BY_USER_ID_ERROR"
            )
    
    async def get_by_type(
        self,
        file_type: str,
        pagination: Optional[PaginationRequest] = None
    ) -> ServiceResult[PaginatedResult[FileMetadata]]:
        """Get files by type."""
        try:
            return await self.list(
                filters={"file_type": file_type},
                pagination=pagination,
                order_by=["-uploaded_at"]  # Newest first
            )
            
        except Exception as e:
            logger.error(f"Error getting files by type {file_type}: {e}")
            return ServiceResult.error(
                error=f"Failed to get files by type: {str(e)}",
                error_code="FILE_REPOSITORY_GET_BY_TYPE_ERROR"
            )
    
    async def _to_domain_model(self, db_file: FileDB) -> FileMetadata:
        """Convert database file model to domain model."""
        from ..models.file import FileType
        
        return FileMetadata(
            id=db_file.id,
            filename=db_file.filename,
            original_filename=db_file.original_filename,
            file_type=FileType(db_file.file_type),
            file_size=db_file.file_size,
            content_type=db_file.content_type,
            storage_path=db_file.storage_path,
            user_id=db_file.user_id,
            metadata=db_file.metadata or {},
            uploaded_at=db_file.uploaded_at,
            updated_at=db_file.updated_at
        )
    
    async def _to_db_model(self, domain_file: FileMetadata) -> FileDB:
        """Convert domain file model to database model."""
        return FileDB(
            id=domain_file.id,
            filename=domain_file.filename,
            original_filename=domain_file.original_filename,
            file_type=domain_file.file_type.value,
            file_size=domain_file.file_size,
            content_type=domain_file.content_type,
            storage_path=domain_file.storage_path,
            user_id=domain_file.user_id,
            metadata=domain_file.metadata,
            uploaded_at=domain_file.uploaded_at or datetime.utcnow(),
            updated_at=domain_file.updated_at or datetime.utcnow()
        )
