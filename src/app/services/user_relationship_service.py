"""
User relationship management service for file and job associations.

This service provides user-file associations, access control, job history tracking,
and user data cleanup procedures using Pydantic models and async database operations.
"""

import logging
from typing import Dict, Any, Optional, List, Tuple
from datetime import datetime, timedelta
from uuid import UUID
import asyncio

from ..database.connection import RDSConnectionManager
from ..database.queries import DatabaseQueries
from ..database.pydantic_models import UserDB, JobDB, FileMetadataDB
from ..models.user import UserRole, UserStatus
from ..models.job import JobStatus, JobType, JobPriority
from ..models.file import FileType

logger = logging.getLogger(__name__)


class UserFileAssociation:
    """Model for user-file associations with access control."""
    
    def __init__(self, user_id: UUID, file_id: UUID, access_level: str = "owner"):
        self.user_id = user_id
        self.file_id = file_id
        self.access_level = access_level  # owner, read, write, admin
        self.created_at = datetime.utcnow()
        self.last_accessed = None
    
    def can_read(self) -> bool:
        """Check if user can read the file."""
        return self.access_level in ["owner", "read", "write", "admin"]
    
    def can_write(self) -> bool:
        """Check if user can modify the file."""
        return self.access_level in ["owner", "write", "admin"]
    
    def can_delete(self) -> bool:
        """Check if user can delete the file."""
        return self.access_level in ["owner", "admin"]


class UserJobHistory:
    """Model for user job history and statistics."""
    
    def __init__(self, user_id: UUID):
        self.user_id = user_id
        self.total_jobs = 0
        self.completed_jobs = 0
        self.failed_jobs = 0
        self.cancelled_jobs = 0
        self.active_jobs = 0
        self.total_processing_time = 0.0
        self.avg_processing_time = 0.0
        self.job_types_count = {}
        self.priority_distribution = {}
        self.recent_activity = []
        self.last_job_date = None
        self.first_job_date = None


class UserDataRetention:
    """Model for user data retention policies."""
    
    def __init__(self, user_id: UUID):
        self.user_id = user_id
        self.job_retention_days = 90  # Keep jobs for 90 days
        self.file_retention_days = 365  # Keep files for 1 year
        self.log_retention_days = 30  # Keep logs for 30 days
        self.inactive_user_days = 180  # Mark user inactive after 180 days
        self.cleanup_enabled = True


class UserRelationshipService:
    """
    Service for managing user relationships with files and jobs.
    
    Provides user-file associations, access control, job history tracking,
    and data cleanup procedures.
    """
    
    def __init__(self, connection_manager: RDSConnectionManager):
        self.connection_manager = connection_manager
    
    # User-File Association Methods
    
    async def get_user_files_with_access(self, user_id: UUID, file_type: Optional[str] = None,
                                       access_level: Optional[str] = None,
                                       limit: int = 100, offset: int = 0) -> List[Dict[str, Any]]:
        """
        Get user files with access control information.
        
        Args:
            user_id: User ID
            file_type: Optional file type filter
            access_level: Optional access level filter
            limit: Maximum number of files to return
            offset: Number of files to skip
            
        Returns:
            List of files with access information
        """
        try:
            async with self.connection_manager.get_session() as session:
                queries = DatabaseQueries(session)
                
                # Get user files
                files = await queries.get_user_files(user_id, file_type, limit, offset)
                
                # Enhance with access control information
                files_with_access = []
                for file_meta in files:
                    file_dict = file_meta.model_dump()
                    
                    # Add access control information
                    association = UserFileAssociation(user_id, file_meta.id, "owner")
                    file_dict.update({
                        "access_level": association.access_level,
                        "can_read": association.can_read(),
                        "can_write": association.can_write(),
                        "can_delete": association.can_delete(),
                        "last_accessed": file_meta.last_accessed_at
                    })
                    
                    # Filter by access level if specified
                    if access_level and association.access_level != access_level:
                        continue
                    
                    files_with_access.append(file_dict)
                
                logger.info(f"Retrieved {len(files_with_access)} files for user {user_id}")
                return files_with_access
                
        except Exception as e:
            logger.error(f"Failed to get user files with access for {user_id}: {e}")
            raise
    
    async def check_file_access(self, user_id: UUID, file_id: UUID, 
                               required_access: str = "read") -> bool:
        """
        Check if user has required access to a file.
        
        Args:
            user_id: User ID
            file_id: File ID
            required_access: Required access level (read, write, delete)
            
        Returns:
            True if user has required access
        """
        try:
            async with self.connection_manager.get_session() as session:
                queries = DatabaseQueries(session)
                
                # Get file metadata
                file_meta = await queries.get_file_by_id(file_id, user_id)
                if not file_meta:
                    return False
                
                # Check if user owns the file
                if file_meta.user_id == user_id:
                    association = UserFileAssociation(user_id, file_id, "owner")
                else:
                    # For now, only owners have access
                    # This can be extended to support shared files
                    return False
                
                # Check access level
                if required_access == "read":
                    return association.can_read()
                elif required_access == "write":
                    return association.can_write()
                elif required_access == "delete":
                    return association.can_delete()
                
                return False
                
        except Exception as e:
            logger.error(f"Failed to check file access for user {user_id}, file {file_id}: {e}")
            return False
    
    async def update_file_access_time(self, user_id: UUID, file_id: UUID) -> bool:
        """
        Update file last accessed time.
        
        Args:
            user_id: User ID
            file_id: File ID
            
        Returns:
            True if updated successfully
        """
        try:
            async with self.connection_manager.get_session() as session:
                queries = DatabaseQueries(session)
                
                # Update last accessed time
                updates = {"last_accessed_at": datetime.utcnow()}
                file_meta = await queries.update_file_metadata(file_id, updates)
                
                if file_meta:
                    logger.debug(f"Updated access time for file {file_id} by user {user_id}")
                    return True
                
                return False
                
        except Exception as e:
            logger.error(f"Failed to update file access time: {e}")
            return False
    
    # User Job History and Statistics Methods
    
    async def get_user_job_history(self, user_id: UUID, 
                                  include_stats: bool = True) -> UserJobHistory:
        """
        Get comprehensive user job history and statistics.
        
        Args:
            user_id: User ID
            include_stats: Whether to include detailed statistics
            
        Returns:
            UserJobHistory object with statistics
        """
        try:
            async with self.connection_manager.get_session() as session:
                queries = DatabaseQueries(session)
                
                # Get user statistics
                stats = await queries.get_user_stats(user_id)
                
                # Create job history object
                history = UserJobHistory(user_id)
                
                # Populate basic counts
                job_counts = stats.get("job_counts", {})
                history.total_jobs = stats.get("total_jobs", 0)
                history.completed_jobs = job_counts.get(JobStatus.COMPLETED, 0)
                history.failed_jobs = job_counts.get(JobStatus.FAILED, 0)
                history.cancelled_jobs = job_counts.get(JobStatus.CANCELLED, 0)
                history.active_jobs = (
                    job_counts.get(JobStatus.QUEUED, 0) + 
                    job_counts.get(JobStatus.PROCESSING, 0)
                )
                
                if include_stats:
                    # Get detailed job statistics
                    await self._populate_detailed_job_stats(session, user_id, history)
                
                logger.info(f"Retrieved job history for user {user_id}: {history.total_jobs} total jobs")
                return history
                
        except Exception as e:
            logger.error(f"Failed to get user job history for {user_id}: {e}")
            raise
    
    async def _populate_detailed_job_stats(self, session, user_id: UUID, 
                                         history: UserJobHistory):
        """Populate detailed job statistics."""
        try:
            queries = DatabaseQueries(session)
            
            # Get all user jobs for detailed analysis
            all_jobs = await queries.get_user_jobs(user_id, limit=1000)
            
            if not all_jobs:
                return
            
            # Calculate processing time statistics
            processing_times = []
            job_types = {}
            priorities = {}
            
            for job in all_jobs:
                # Job type distribution
                job_type = job.job_type.value
                job_types[job_type] = job_types.get(job_type, 0) + 1
                
                # Priority distribution
                priority = job.priority.value
                priorities[priority] = priorities.get(priority, 0) + 1
                
                # Processing time calculation
                if job.processing_time_seconds:
                    processing_times.append(job.processing_time_seconds)
                
                # Date tracking
                if not history.first_job_date or job.created_at < history.first_job_date:
                    history.first_job_date = job.created_at
                
                if not history.last_job_date or job.created_at > history.last_job_date:
                    history.last_job_date = job.created_at
            
            # Calculate averages
            if processing_times:
                history.total_processing_time = sum(processing_times)
                history.avg_processing_time = history.total_processing_time / len(processing_times)
            
            history.job_types_count = job_types
            history.priority_distribution = priorities
            
            # Get recent activity (last 10 jobs)
            recent_jobs = await queries.get_user_jobs(user_id, limit=10)
            history.recent_activity = [
                {
                    "job_id": str(job.id),
                    "status": job.status.value,
                    "job_type": job.job_type.value,
                    "created_at": job.created_at,
                    "completed_at": job.completed_at
                }
                for job in recent_jobs
            ]
            
        except Exception as e:
            logger.error(f"Failed to populate detailed job stats: {e}")
    
    async def get_user_job_trends(self, user_id: UUID, days: int = 30) -> Dict[str, Any]:
        """
        Get user job trends over specified period.
        
        Args:
            user_id: User ID
            days: Number of days to analyze
            
        Returns:
            Dictionary with trend data
        """
        try:
            async with self.connection_manager.get_session() as session:
                queries = DatabaseQueries(session)
                
                # Get jobs from the specified period
                cutoff_date = datetime.utcnow() - timedelta(days=days)
                
                # Custom query for trend analysis
                query = """
                    SELECT 
                        DATE(created_at) as job_date,
                        status,
                        job_type,
                        COUNT(*) as job_count,
                        AVG(processing_time_seconds) as avg_processing_time
                    FROM jobs 
                    WHERE user_id = $1 
                        AND created_at >= $2 
                        AND is_deleted = FALSE
                    GROUP BY DATE(created_at), status, job_type
                    ORDER BY job_date DESC
                """
                
                results = await self.connection_manager.execute_query(
                    query, {"user_id": user_id, "cutoff_date": cutoff_date}
                )
                
                # Process results into trend data
                trends = {
                    "period_days": days,
                    "daily_counts": {},
                    "status_trends": {},
                    "type_trends": {},
                    "performance_trends": {}
                }
                
                for row in results:
                    date_str = row["job_date"].strftime("%Y-%m-%d")
                    status = row["status"]
                    job_type = row["job_type"]
                    count = row["job_count"]
                    avg_time = row["avg_processing_time"]
                    
                    # Daily counts
                    if date_str not in trends["daily_counts"]:
                        trends["daily_counts"][date_str] = 0
                    trends["daily_counts"][date_str] += count
                    
                    # Status trends
                    if status not in trends["status_trends"]:
                        trends["status_trends"][status] = {}
                    trends["status_trends"][status][date_str] = count
                    
                    # Type trends
                    if job_type not in trends["type_trends"]:
                        trends["type_trends"][job_type] = {}
                    trends["type_trends"][job_type][date_str] = count
                    
                    # Performance trends
                    if avg_time and date_str not in trends["performance_trends"]:
                        trends["performance_trends"][date_str] = avg_time
                
                logger.info(f"Retrieved job trends for user {user_id} over {days} days")
                return trends
                
        except Exception as e:
            logger.error(f"Failed to get user job trends for {user_id}: {e}")
            raise
    
    # User Data Cleanup and Retention Methods
    
    async def cleanup_user_data(self, user_id: UUID, 
                               retention_policy: Optional[UserDataRetention] = None,
                               dry_run: bool = False) -> Dict[str, Any]:
        """
        Clean up user data based on retention policies.
        
        Args:
            user_id: User ID
            retention_policy: Custom retention policy (uses default if None)
            dry_run: If True, only report what would be cleaned
            
        Returns:
            Dictionary with cleanup results
        """
        try:
            if not retention_policy:
                retention_policy = UserDataRetention(user_id)
            
            cleanup_results = {
                "user_id": str(user_id),
                "dry_run": dry_run,
                "jobs_cleaned": 0,
                "files_cleaned": 0,
                "logs_cleaned": 0,
                "total_space_freed": 0,
                "cleanup_date": datetime.utcnow()
            }
            
            async with self.connection_manager.get_session() as session:
                queries = DatabaseQueries(session)
                
                # Clean up old completed jobs
                if retention_policy.cleanup_enabled:
                    jobs_cleaned = await self._cleanup_old_jobs(
                        queries, user_id, retention_policy.job_retention_days, dry_run
                    )
                    cleanup_results["jobs_cleaned"] = jobs_cleaned
                    
                    # Clean up orphaned files
                    files_cleaned, space_freed = await self._cleanup_orphaned_files(
                        queries, user_id, retention_policy.file_retention_days, dry_run
                    )
                    cleanup_results["files_cleaned"] = files_cleaned
                    cleanup_results["total_space_freed"] = space_freed
                    
                    # Clean up old activity logs (if implemented)
                    logs_cleaned = await self._cleanup_activity_logs(
                        user_id, retention_policy.log_retention_days, dry_run
                    )
                    cleanup_results["logs_cleaned"] = logs_cleaned
                
                logger.info(f"Cleanup completed for user {user_id}: {cleanup_results}")
                return cleanup_results
                
        except Exception as e:
            logger.error(f"Failed to cleanup user data for {user_id}: {e}")
            raise
    
    async def _cleanup_old_jobs(self, queries: DatabaseQueries, user_id: UUID, 
                               retention_days: int, dry_run: bool) -> int:
        """Clean up old completed jobs."""
        try:
            cutoff_date = datetime.utcnow() - timedelta(days=retention_days)
            
            # Find old completed jobs
            old_jobs_query = """
                SELECT id FROM jobs 
                WHERE user_id = $1 
                    AND status IN ('completed', 'failed', 'cancelled')
                    AND completed_at < $2
                    AND is_deleted = FALSE
            """
            
            old_jobs = await self.connection_manager.execute_query(
                old_jobs_query, {"user_id": user_id, "cutoff_date": cutoff_date}
            )
            
            if not dry_run and old_jobs:
                # Soft delete old jobs
                job_ids = [job["id"] for job in old_jobs]
                for job_id in job_ids:
                    await queries.soft_delete_job(job_id)
            
            return len(old_jobs)
            
        except Exception as e:
            logger.error(f"Failed to cleanup old jobs: {e}")
            return 0
    
    async def _cleanup_orphaned_files(self, queries: DatabaseQueries, user_id: UUID,
                                    retention_days: int, dry_run: bool) -> Tuple[int, int]:
        """Clean up orphaned files."""
        try:
            cutoff_date = datetime.utcnow() - timedelta(days=retention_days)
            
            # Find orphaned files (files without associated jobs or old temp files)
            orphaned_files_query = """
                SELECT f.id, f.file_size 
                FROM file_metadata f
                LEFT JOIN jobs j ON f.job_id = j.id
                WHERE f.user_id = $1 
                    AND f.created_at < $2
                    AND f.is_deleted = FALSE
                    AND (j.id IS NULL OR j.is_deleted = TRUE)
            """
            
            orphaned_files = await self.connection_manager.execute_query(
                orphaned_files_query, {"user_id": user_id, "cutoff_date": cutoff_date}
            )
            
            total_space_freed = 0
            if not dry_run and orphaned_files:
                # Soft delete orphaned files
                for file_info in orphaned_files:
                    file_id = file_info["id"]
                    file_size = file_info["file_size"] or 0
                    
                    success = await self.connection_manager.delete_pydantic_model(
                        "file_metadata", "id = $1", [file_id], soft_delete=True
                    )
                    
                    if success:
                        total_space_freed += file_size
            else:
                # Calculate potential space savings for dry run
                total_space_freed = sum(f.get("file_size", 0) for f in orphaned_files)
            
            return len(orphaned_files), total_space_freed
            
        except Exception as e:
            logger.error(f"Failed to cleanup orphaned files: {e}")
            return 0, 0
    
    async def _cleanup_activity_logs(self, user_id: UUID, retention_days: int, 
                                   dry_run: bool) -> int:
        """Clean up old activity logs."""
        try:
            # This would integrate with the existing user activity logging
            # For now, return 0 as activity logs are handled by Redis TTL
            return 0
            
        except Exception as e:
            logger.error(f"Failed to cleanup activity logs: {e}")
            return 0
    
    async def get_user_data_summary(self, user_id: UUID) -> Dict[str, Any]:
        """
        Get comprehensive summary of user's data.
        
        Args:
            user_id: User ID
            
        Returns:
            Dictionary with user data summary
        """
        try:
            async with self.connection_manager.get_session() as session:
                queries = DatabaseQueries(session)
                
                # Get user info
                user = await queries.get_user_by_id(user_id)
                if not user:
                    raise ValueError(f"User {user_id} not found")
                
                # Get statistics
                stats = await queries.get_user_stats(user_id)
                
                # Get job history
                job_history = await self.get_user_job_history(user_id)
                
                # Calculate data usage
                total_file_size = stats.get("total_file_size", 0)
                total_files = stats.get("total_files", 0)
                total_jobs = stats.get("total_jobs", 0)
                
                # Account age
                account_age_days = (datetime.utcnow() - user.created_at).days
                
                summary = {
                    "user_id": str(user_id),
                    "account_created": user.created_at,
                    "account_age_days": account_age_days,
                    "last_active": user.last_active_at,
                    "status": user.status.value,
                    "role": user.role.value,
                    
                    # Data usage
                    "total_files": total_files,
                    "total_file_size_bytes": total_file_size,
                    "total_file_size_mb": round(total_file_size / (1024 * 1024), 2),
                    "total_jobs": total_jobs,
                    
                    # Job statistics
                    "completed_jobs": job_history.completed_jobs,
                    "failed_jobs": job_history.failed_jobs,
                    "active_jobs": job_history.active_jobs,
                    "avg_processing_time": job_history.avg_processing_time,
                    
                    # Activity
                    "first_job_date": job_history.first_job_date,
                    "last_job_date": job_history.last_job_date,
                    "job_types_used": list(job_history.job_types_count.keys()),
                    
                    # File breakdown
                    "file_types": stats.get("file_counts", {}),
                    
                    # Recommendations
                    "cleanup_recommended": self._should_recommend_cleanup(
                        account_age_days, total_files, total_jobs, user.last_active_at
                    )
                }
                
                logger.info(f"Generated data summary for user {user_id}")
                return summary
                
        except Exception as e:
            logger.error(f"Failed to get user data summary for {user_id}: {e}")
            raise
    
    def _should_recommend_cleanup(self, account_age_days: int, total_files: int,
                                 total_jobs: int, last_active: Optional[datetime]) -> bool:
        """Determine if cleanup should be recommended."""
        # Recommend cleanup if:
        # - Account is older than 90 days AND has many files/jobs
        # - User hasn't been active in 30 days AND has data
        # - Large number of files or jobs
        
        if account_age_days > 90 and (total_files > 100 or total_jobs > 50):
            return True
        
        if last_active:
            days_inactive = (datetime.utcnow() - last_active).days
            if days_inactive > 30 and (total_files > 10 or total_jobs > 5):
                return True
        
        if total_files > 500 or total_jobs > 200:
            return True
        
        return False
    
    async def bulk_cleanup_inactive_users(self, inactive_days: int = 180,
                                        dry_run: bool = True) -> Dict[str, Any]:
        """
        Perform bulk cleanup of inactive users' data.
        
        Args:
            inactive_days: Number of days to consider user inactive
            dry_run: If True, only report what would be cleaned
            
        Returns:
            Dictionary with bulk cleanup results
        """
        try:
            cutoff_date = datetime.utcnow() - timedelta(days=inactive_days)
            
            # Find inactive users
            inactive_users_query = """
                SELECT id, clerk_user_id, last_active_at, created_at
                FROM users 
                WHERE (last_active_at < $1 OR last_active_at IS NULL)
                    AND created_at < $1
                    AND is_deleted = FALSE
                    AND status = 'active'
            """
            
            inactive_users = await self.connection_manager.execute_query(
                inactive_users_query, {"cutoff_date": cutoff_date}
            )
            
            bulk_results = {
                "inactive_days": inactive_days,
                "dry_run": dry_run,
                "users_processed": 0,
                "total_jobs_cleaned": 0,
                "total_files_cleaned": 0,
                "total_space_freed": 0,
                "cleanup_date": datetime.utcnow(),
                "user_summaries": []
            }
            
            # Process each inactive user
            for user_info in inactive_users:
                user_id = user_info["id"]
                
                try:
                    # Cleanup user data
                    cleanup_result = await self.cleanup_user_data(
                        user_id, dry_run=dry_run
                    )
                    
                    bulk_results["users_processed"] += 1
                    bulk_results["total_jobs_cleaned"] += cleanup_result["jobs_cleaned"]
                    bulk_results["total_files_cleaned"] += cleanup_result["files_cleaned"]
                    bulk_results["total_space_freed"] += cleanup_result["total_space_freed"]
                    
                    bulk_results["user_summaries"].append({
                        "user_id": str(user_id),
                        "clerk_user_id": user_info["clerk_user_id"],
                        "last_active": user_info["last_active_at"],
                        "cleanup_result": cleanup_result
                    })
                    
                except Exception as e:
                    logger.error(f"Failed to cleanup user {user_id}: {e}")
                    continue
            
            logger.info(f"Bulk cleanup completed: {bulk_results['users_processed']} users processed")
            return bulk_results
            
        except Exception as e:
            logger.error(f"Failed to perform bulk cleanup: {e}")
            raise


# Helper functions for integration with existing services

async def get_user_relationship_service(connection_manager: RDSConnectionManager) -> UserRelationshipService:
    """
    Get user relationship service instance.
    
    Args:
        connection_manager: RDS connection manager
        
    Returns:
        UserRelationshipService instance
    """
    return UserRelationshipService(connection_manager)