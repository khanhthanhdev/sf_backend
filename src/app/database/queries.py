"""
Database query methods that work with Pydantic models.

This module provides high-level database operations that integrate
Pydantic models with SQLAlchemy database operations.
"""

import logging
from typing import Optional, List, Dict, Any, Union
from uuid import UUID
from datetime import datetime, timedelta

from sqlalchemy import select, update, delete, func, and_, or_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from .models import User, Job, FileMetadata, JobQueue
from .pydantic_models import UserDB, JobDB, FileMetadataDB, JobQueueDB
from ..models.job import JobStatus, JobPriority, JobType
from ..models.user import UserRole, UserStatus

logger = logging.getLogger(__name__)


class DatabaseQueries:
    """High-level database query methods with Pydantic integration."""
    
    def __init__(self, session: AsyncSession):
        self.session = session
    
    # User queries
    
    async def get_user_by_clerk_id(self, clerk_user_id: str) -> Optional[UserDB]:
        """Get user by Clerk user ID."""
        try:
            stmt = select(User).where(
                and_(
                    User.clerk_user_id == clerk_user_id,
                    User.is_deleted == False
                )
            )
            result = await self.session.execute(stmt)
            user = result.scalar_one_or_none()
            
            return UserDB.from_db(user) if user else None
            
        except Exception as e:
            logger.error(f"Failed to get user by clerk_id {clerk_user_id}: {e}")
            raise
    
    async def get_user_by_id(self, user_id: UUID) -> Optional[UserDB]:
        """Get user by ID."""
        try:
            stmt = select(User).where(
                and_(
                    User.id == user_id,
                    User.is_deleted == False
                )
            )
            result = await self.session.execute(stmt)
            user = result.scalar_one_or_none()
            
            return UserDB.from_db(user) if user else None
            
        except Exception as e:
            logger.error(f"Failed to get user by id {user_id}: {e}")
            raise
    
    async def get_user_by_email(self, email: str) -> Optional[UserDB]:
        """Get user by primary email."""
        try:
            stmt = select(User).where(
                and_(
                    User.primary_email == email,
                    User.is_deleted == False
                )
            )
            result = await self.session.execute(stmt)
            user = result.scalar_one_or_none()
            
            return UserDB.from_db(user) if user else None
            
        except Exception as e:
            logger.error(f"Failed to get user by email {email}: {e}")
            raise
    
    async def create_user(self, user_data: UserDB) -> UserDB:
        """Create a new user."""
        try:
            db_user = User(**user_data.to_db_dict())
            self.session.add(db_user)
            await self.session.commit()
            await self.session.refresh(db_user)
            
            logger.info(f"Created user {db_user.id} with clerk_id {db_user.clerk_user_id}")
            return UserDB.from_db(db_user)
            
        except Exception as e:
            await self.session.rollback()
            logger.error(f"Failed to create user: {e}")
            raise
    
    async def update_user(self, user_id: UUID, updates: Dict[str, Any]) -> Optional[UserDB]:
        """Update user by ID."""
        try:
            updates['updated_at'] = datetime.utcnow()
            
            stmt = update(User).where(
                and_(
                    User.id == user_id,
                    User.is_deleted == False
                )
            ).values(**updates).returning(User)
            
            result = await self.session.execute(stmt)
            await self.session.commit()
            
            user = result.scalar_one_or_none()
            if user:
                logger.info(f"Updated user {user_id}")
                return UserDB.from_db(user)
            
            return None
            
        except Exception as e:
            await self.session.rollback()
            logger.error(f"Failed to update user {user_id}: {e}")
            raise
    
    async def get_active_users(self, limit: int = 100, offset: int = 0) -> List[UserDB]:
        """Get active users with pagination."""
        try:
            stmt = select(User).where(
                and_(
                    User.is_deleted == False,
                    User.status == UserStatus.ACTIVE
                )
            ).order_by(User.created_at.desc()).offset(offset).limit(limit)
            
            result = await self.session.execute(stmt)
            users = result.scalars().all()
            
            return [UserDB.from_db(user) for user in users]
            
        except Exception as e:
            logger.error(f"Failed to get active users: {e}")
            raise
    
    # Job queries
    
    async def get_job_by_id(self, job_id: UUID, user_id: Optional[UUID] = None) -> Optional[JobDB]:
        """Get job by ID, optionally filtered by user."""
        try:
            conditions = [Job.id == job_id, Job.is_deleted == False]
            if user_id:
                conditions.append(Job.user_id == user_id)
            
            stmt = select(Job).where(and_(*conditions))
            result = await self.session.execute(stmt)
            job = result.scalar_one_or_none()
            
            return JobDB.from_db(job) if job else None
            
        except Exception as e:
            logger.error(f"Failed to get job {job_id}: {e}")
            raise
    
    async def create_job(self, job_data: JobDB) -> JobDB:
        """Create a new job."""
        try:
            db_job = Job(**job_data.to_db_dict())
            self.session.add(db_job)
            await self.session.commit()
            await self.session.refresh(db_job)
            
            logger.info(f"Created job {db_job.id} for user {db_job.user_id}")
            return JobDB.from_db(db_job)
            
        except Exception as e:
            await self.session.rollback()
            logger.error(f"Failed to create job: {e}")
            raise
    
    async def update_job(self, job_id: UUID, updates: Dict[str, Any]) -> Optional[JobDB]:
        """Update job by ID."""
        try:
            updates['updated_at'] = datetime.utcnow()
            
            stmt = update(Job).where(
                and_(
                    Job.id == job_id,
                    Job.is_deleted == False
                )
            ).values(**updates).returning(Job)
            
            result = await self.session.execute(stmt)
            await self.session.commit()
            
            job = result.scalar_one_or_none()
            if job:
                logger.info(f"Updated job {job_id}")
                return JobDB.from_db(job)
            
            return None
            
        except Exception as e:
            await self.session.rollback()
            logger.error(f"Failed to update job {job_id}: {e}")
            raise
    
    async def get_user_jobs(self, user_id: UUID, status: Optional[JobStatus] = None, 
                           limit: int = 100, offset: int = 0) -> List[JobDB]:
        """Get jobs for a user with optional status filter."""
        try:
            conditions = [Job.user_id == user_id, Job.is_deleted == False]
            if status:
                conditions.append(Job.status == status)
            
            stmt = select(Job).where(and_(*conditions)).order_by(
                Job.created_at.desc()
            ).offset(offset).limit(limit)
            
            result = await self.session.execute(stmt)
            jobs = result.scalars().all()
            
            return [JobDB.from_db(job) for job in jobs]
            
        except Exception as e:
            logger.error(f"Failed to get user jobs for {user_id}: {e}")
            raise
    
    async def get_queued_jobs(self, limit: int = 100) -> List[JobDB]:
        """Get queued jobs ordered by priority and creation time."""
        try:
            stmt = select(Job).where(
                and_(
                    Job.status == JobStatus.QUEUED,
                    Job.is_deleted == False
                )
            ).order_by(
                Job.priority.desc(),
                Job.created_at.asc()
            ).limit(limit)
            
            result = await self.session.execute(stmt)
            jobs = result.scalars().all()
            
            return [JobDB.from_db(job) for job in jobs]
            
        except Exception as e:
            logger.error(f"Failed to get queued jobs: {e}")
            raise
    
    async def get_active_jobs(self, limit: int = 100) -> List[JobDB]:
        """Get active (queued or processing) jobs."""
        try:
            stmt = select(Job).where(
                and_(
                    Job.status.in_([JobStatus.QUEUED, JobStatus.PROCESSING]),
                    Job.is_deleted == False
                )
            ).order_by(Job.created_at.desc()).limit(limit)
            
            result = await self.session.execute(stmt)
            jobs = result.scalars().all()
            
            return [JobDB.from_db(job) for job in jobs]
            
        except Exception as e:
            logger.error(f"Failed to get active jobs: {e}")
            raise
    
    async def get_batch_jobs(self, batch_id: UUID) -> List[JobDB]:
        """Get all jobs in a batch."""
        try:
            stmt = select(Job).where(
                and_(
                    Job.batch_id == batch_id,
                    Job.is_deleted == False
                )
            ).order_by(Job.created_at.asc())
            
            result = await self.session.execute(stmt)
            jobs = result.scalars().all()
            
            return [JobDB.from_db(job) for job in jobs]
            
        except Exception as e:
            logger.error(f"Failed to get batch jobs for {batch_id}: {e}")
            raise
    
    # File metadata queries
    
    async def get_file_by_id(self, file_id: UUID, user_id: Optional[UUID] = None) -> Optional[FileMetadataDB]:
        """Get file metadata by ID, optionally filtered by user."""
        try:
            conditions = [FileMetadata.id == file_id, FileMetadata.is_deleted == False]
            if user_id:
                conditions.append(FileMetadata.user_id == user_id)
            
            stmt = select(FileMetadata).where(and_(*conditions))
            result = await self.session.execute(stmt)
            file_meta = result.scalar_one_or_none()
            
            return FileMetadataDB.from_db(file_meta) if file_meta else None
            
        except Exception as e:
            logger.error(f"Failed to get file {file_id}: {e}")
            raise
    
    async def create_file_metadata(self, file_data: FileMetadataDB) -> FileMetadataDB:
        """Create file metadata record."""
        try:
            db_file = FileMetadata(**file_data.to_db_dict())
            self.session.add(db_file)
            await self.session.commit()
            await self.session.refresh(db_file)
            
            logger.info(f"Created file metadata {db_file.id} for user {db_file.user_id}")
            return FileMetadataDB.from_db(db_file)
            
        except Exception as e:
            await self.session.rollback()
            logger.error(f"Failed to create file metadata: {e}")
            raise
    
    async def get_user_files(self, user_id: UUID, file_type: Optional[str] = None,
                            limit: int = 100, offset: int = 0) -> List[FileMetadataDB]:
        """Get files for a user with optional type filter."""
        try:
            conditions = [FileMetadata.user_id == user_id, FileMetadata.is_deleted == False]
            if file_type:
                conditions.append(FileMetadata.file_type == file_type)
            
            stmt = select(FileMetadata).where(and_(*conditions)).order_by(
                FileMetadata.created_at.desc()
            ).offset(offset).limit(limit)
            
            result = await self.session.execute(stmt)
            files = result.scalars().all()
            
            return [FileMetadataDB.from_db(file_meta) for file_meta in files]
            
        except Exception as e:
            logger.error(f"Failed to get user files for {user_id}: {e}")
            raise
    
    async def get_job_files(self, job_id: UUID) -> List[FileMetadataDB]:
        """Get all files associated with a job."""
        try:
            stmt = select(FileMetadata).where(
                and_(
                    FileMetadata.job_id == job_id,
                    FileMetadata.is_deleted == False
                )
            ).order_by(FileMetadata.created_at.asc())
            
            result = await self.session.execute(stmt)
            files = result.scalars().all()
            
            return [FileMetadataDB.from_db(file_meta) for file_meta in files]
            
        except Exception as e:
            logger.error(f"Failed to get job files for {job_id}: {e}")
            raise
    
    # Job queue queries
    
    async def add_job_to_queue(self, queue_data: JobQueueDB) -> JobQueueDB:
        """Add job to processing queue."""
        try:
            db_queue = JobQueue(**queue_data.to_db_dict())
            self.session.add(db_queue)
            await self.session.commit()
            await self.session.refresh(db_queue)
            
            logger.info(f"Added job {db_queue.job_id} to queue")
            return JobQueueDB.from_db(db_queue)
            
        except Exception as e:
            await self.session.rollback()
            logger.error(f"Failed to add job to queue: {e}")
            raise
    
    async def get_next_queued_job(self) -> Optional[JobQueueDB]:
        """Get next job from queue based on priority and queue time."""
        try:
            stmt = select(JobQueue).where(
                JobQueue.queue_status == "queued"
            ).order_by(
                JobQueue.priority.desc(),
                JobQueue.queued_at.asc()
            ).limit(1)
            
            result = await self.session.execute(stmt)
            queue_entry = result.scalar_one_or_none()
            
            return JobQueueDB.from_db(queue_entry) if queue_entry else None
            
        except Exception as e:
            logger.error(f"Failed to get next queued job: {e}")
            raise
    
    async def update_queue_status(self, job_id: UUID, status: str, 
                                 worker_id: Optional[str] = None) -> Optional[JobQueueDB]:
        """Update job queue status."""
        try:
            updates = {"queue_status": status}
            
            if status == "processing":
                updates["processing_started_at"] = datetime.utcnow()
                if worker_id:
                    updates["worker_id"] = worker_id
            elif status == "completed":
                updates["completed_at"] = datetime.utcnow()
            
            stmt = update(JobQueue).where(
                JobQueue.job_id == job_id
            ).values(**updates).returning(JobQueue)
            
            result = await self.session.execute(stmt)
            await self.session.commit()
            
            queue_entry = result.scalar_one_or_none()
            if queue_entry:
                logger.info(f"Updated queue status for job {job_id} to {status}")
                return JobQueueDB.from_db(queue_entry)
            
            return None
            
        except Exception as e:
            await self.session.rollback()
            logger.error(f"Failed to update queue status for job {job_id}: {e}")
            raise
    
    # Statistics and analytics queries
    
    async def get_user_stats(self, user_id: UUID) -> Dict[str, Any]:
        """Get user statistics."""
        try:
            # Job counts by status
            job_stats = await self.session.execute(
                select(Job.status, func.count(Job.id)).where(
                    and_(Job.user_id == user_id, Job.is_deleted == False)
                ).group_by(Job.status)
            )
            
            job_counts = {status: count for status, count in job_stats}
            
            # File counts by type
            file_stats = await self.session.execute(
                select(FileMetadata.file_type, func.count(FileMetadata.id)).where(
                    and_(FileMetadata.user_id == user_id, FileMetadata.is_deleted == False)
                ).group_by(FileMetadata.file_type)
            )
            
            file_counts = {file_type: count for file_type, count in file_stats}
            
            # Total file size
            total_size_result = await self.session.execute(
                select(func.sum(FileMetadata.file_size)).where(
                    and_(FileMetadata.user_id == user_id, FileMetadata.is_deleted == False)
                )
            )
            total_file_size = total_size_result.scalar() or 0
            
            return {
                "job_counts": job_counts,
                "file_counts": file_counts,
                "total_file_size": total_file_size,
                "total_jobs": sum(job_counts.values()),
                "total_files": sum(file_counts.values())
            }
            
        except Exception as e:
            logger.error(f"Failed to get user stats for {user_id}: {e}")
            raise
    
    async def get_system_stats(self) -> Dict[str, Any]:
        """Get system-wide statistics."""
        try:
            # Total users
            total_users = await self.session.execute(
                select(func.count(User.id)).where(User.is_deleted == False)
            )
            
            # Active users (last 30 days)
            thirty_days_ago = datetime.utcnow() - timedelta(days=30)
            active_users = await self.session.execute(
                select(func.count(User.id)).where(
                    and_(
                        User.is_deleted == False,
                        User.last_active_at >= thirty_days_ago
                    )
                )
            )
            
            # Job statistics
            job_stats = await self.session.execute(
                select(Job.status, func.count(Job.id)).where(
                    Job.is_deleted == False
                ).group_by(Job.status)
            )
            
            # Queue statistics
            queue_stats = await self.session.execute(
                select(JobQueue.queue_status, func.count(JobQueue.id)).group_by(
                    JobQueue.queue_status
                )
            )
            
            return {
                "total_users": total_users.scalar(),
                "active_users": active_users.scalar(),
                "job_counts": {status: count for status, count in job_stats},
                "queue_counts": {status: count for status, count in queue_stats}
            }
            
        except Exception as e:
            logger.error(f"Failed to get system stats: {e}")
            raise
    
    # Cleanup and maintenance queries
    
    async def soft_delete_user(self, user_id: UUID) -> bool:
        """Soft delete a user and their associated data."""
        try:
            now = datetime.utcnow()
            
            # Soft delete user
            await self.session.execute(
                update(User).where(User.id == user_id).values(
                    is_deleted=True,
                    deleted_at=now,
                    updated_at=now
                )
            )
            
            # Soft delete user's jobs
            await self.session.execute(
                update(Job).where(Job.user_id == user_id).values(
                    is_deleted=True,
                    deleted_at=now,
                    updated_at=now
                )
            )
            
            # Soft delete user's files
            await self.session.execute(
                update(FileMetadata).where(FileMetadata.user_id == user_id).values(
                    is_deleted=True,
                    deleted_at=now,
                    updated_at=now
                )
            )
            
            await self.session.commit()
            logger.info(f"Soft deleted user {user_id} and associated data")
            return True
            
        except Exception as e:
            await self.session.rollback()
            logger.error(f"Failed to soft delete user {user_id}: {e}")
            raise
    
    async def cleanup_old_jobs(self, days: int = 30) -> int:
        """Clean up completed jobs older than specified days."""
        try:
            cutoff_date = datetime.utcnow() - timedelta(days=days)
            
            result = await self.session.execute(
                update(Job).where(
                    and_(
                        Job.status.in_([JobStatus.COMPLETED, JobStatus.FAILED, JobStatus.CANCELLED]),
                        Job.completed_at < cutoff_date,
                        Job.is_deleted == False
                    )
                ).values(
                    is_deleted=True,
                    deleted_at=datetime.utcnow(),
                    updated_at=datetime.utcnow()
                )
            )
            
            await self.session.commit()
            cleaned_count = result.rowcount
            
            logger.info(f"Cleaned up {cleaned_count} old jobs")
            return cleaned_count
            
        except Exception as e:
            await self.session.rollback()
            logger.error(f"Failed to cleanup old jobs: {e}")
            raise
    
    async def soft_delete_job(self, job_id: UUID) -> bool:
        """Soft delete a job by ID."""
        try:
            now = datetime.utcnow()
            
            stmt = update(Job).where(
                and_(
                    Job.id == job_id,
                    Job.is_deleted == False
                )
            ).values(
                is_deleted=True,
                deleted_at=now,
                updated_at=now
            )
            
            result = await self.session.execute(stmt)
            await self.session.commit()
            
            success = result.rowcount > 0
            if success:
                logger.info(f"Soft deleted job {job_id}")
            
            return success
            
        except Exception as e:
            await self.session.rollback()
            logger.error(f"Failed to soft delete job {job_id}: {e}")
            raise
    
    async def update_file_metadata(self, file_id: UUID, updates: Dict[str, Any]) -> Optional[FileMetadataDB]:
        """Update file metadata by ID."""
        try:
            updates['updated_at'] = datetime.utcnow()
            
            stmt = update(FileMetadata).where(
                and_(
                    FileMetadata.id == file_id,
                    FileMetadata.is_deleted == False
                )
            ).values(**updates).returning(FileMetadata)
            
            result = await self.session.execute(stmt)
            await self.session.commit()
            
            file_meta = result.scalar_one_or_none()
            if file_meta:
                logger.info(f"Updated file metadata {file_id}")
                return FileMetadataDB.from_db(file_meta)
            
            return None
            
        except Exception as e:
            await self.session.rollback()
            logger.error(f"Failed to update file metadata {file_id}: {e}")
            raise