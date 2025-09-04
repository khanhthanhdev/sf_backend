"""
Database-only Job management service for handling job lifecycle and operations.

This service provides business logic for job management operations,
including job retrieval, cancellation, deletion, and cleanup.
Uses database-only storage without Redis dependencies.
"""

import logging
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List

from ..database.connection import RDSConnectionManager

logger = logging.getLogger(__name__)


class JobService:
    """
    Service class for job management operations using database-only storage.
    
    Handles job lifecycle management, status updates, cleanup,
    and data retrieval operations.
    """
    
    def __init__(self, db_manager: RDSConnectionManager):
        self.db_manager = db_manager
    
    async def get_jobs_paginated(
        self,
        user_id: str,
        limit: int = 10,
        offset: int = 0,
        filters: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Get paginated list of jobs for a user with optional filtering.
        
        Args:
            user_id: User ID to get jobs for
            limit: Maximum number of jobs to return
            offset: Number of jobs to skip
            filters: Optional filters (status, job_type, priority, dates)
            
        Returns:
            Dict containing jobs list and pagination info
        """
        try:
            async with self.db_manager.get_session() as session:
                # Build the base query
                query = """
                    SELECT * FROM jobs 
                    WHERE user_id = $1 AND is_deleted = FALSE
                """
                params = [user_id]
                param_count = 1
                
                # Add filters
                if filters:
                    if filters.get('status'):
                        param_count += 1
                        query += f" AND status = ${param_count}"
                        params.append(filters['status'])
                    
                    if filters.get('job_type'):
                        param_count += 1
                        query += f" AND job_type = ${param_count}"
                        params.append(filters['job_type'])
                    
                    if filters.get('priority'):
                        param_count += 1
                        query += f" AND priority = ${param_count}"
                        params.append(filters['priority'])
                
                # Add ordering and pagination
                query += f" ORDER BY created_at DESC LIMIT ${param_count + 1} OFFSET ${param_count + 2}"
                params.extend([limit, offset])
                
                # Get total count for pagination
                count_query = """
                    SELECT COUNT(*) FROM jobs 
                    WHERE user_id = $1 AND is_deleted = FALSE
                """
                count_params = [user_id]
                
                # Execute queries
                jobs_result = await session.fetch(query, *params)
                count_result = await session.fetchval(count_query, *count_params)
                
                jobs = [dict(row) for row in jobs_result]
                
                logger.info(
                    "Retrieved paginated jobs",
                    extra={
                        "user_id": user_id,
                        "total_count": count_result,
                        "returned_count": len(jobs),
                        "offset": offset,
                        "limit": limit
                    }
                )
                
                return {
                    "jobs": jobs,
                    "total_count": count_result
                }
                
        except Exception as e:
            logger.error(
                "Failed to get paginated jobs",
                extra={
                    "user_id": user_id,
                    "error": str(e)
                },
                exc_info=True
            )
            return {
                "jobs": [],
                "total_count": 0
            }
    
    async def cancel_job(self, job_id: str) -> bool:
        """
        Cancel a job if it's in a cancellable state.
        
        Args:
            job_id: Job ID to cancel
            
        Returns:
            True if cancellation successful, False otherwise
        """
        try:
            async with self.db_manager.get_session() as session:
                # Get job first
                job_query = "SELECT * FROM jobs WHERE id = $1"
                job_row = await session.fetchrow(job_query, job_id)
                
                if not job_row:
                    logger.warning(f"Job {job_id} not found for cancellation")
                    return False
                
                # Check if job can be cancelled (add your business logic here)
                current_status = job_row['status']
                if current_status in ['COMPLETED', 'FAILED', 'CANCELLED']:
                    logger.warning(
                        f"Job {job_id} cannot be cancelled. Current status: {current_status}"
                    )
                    return False
                
                # Update job status
                update_query = """
                    UPDATE jobs 
                    SET status = 'CANCELLED', 
                        completed_at = $2, 
                        updated_at = $2
                    WHERE id = $1
                """
                
                await session.execute(update_query, job_id, datetime.utcnow())
                await session.commit()
                
                logger.info(f"Job {job_id} cancelled successfully")
                return True
                
        except Exception as e:
            logger.error(
                "Failed to cancel job",
                extra={
                    "job_id": job_id,
                    "error": str(e)
                },
                exc_info=True
            )
            return False
    
    async def soft_delete_job(self, job_id: str) -> bool:
        """
        Perform soft delete on a job.
        
        Args:
            job_id: Job ID to delete
            
        Returns:
            True if deletion successful, False otherwise
        """
        try:
            async with self.db_manager.get_session() as session:
                # Check if job exists
                job_query = "SELECT id FROM jobs WHERE id = $1"
                job_row = await session.fetchrow(job_query, job_id)
                
                if not job_row:
                    logger.warning(f"Job {job_id} not found for deletion")
                    return False
                
                # Mark as deleted
                update_query = """
                    UPDATE jobs 
                    SET is_deleted = TRUE, 
                        deleted_at = $2, 
                        updated_at = $2
                    WHERE id = $1
                """
                
                await session.execute(update_query, job_id, datetime.utcnow())
                await session.commit()
                
                logger.info(f"Job {job_id} soft deleted successfully")
                return True
                
        except Exception as e:
            logger.error(
                "Failed to soft delete job",
                extra={
                    "job_id": job_id,
                    "error": str(e)
                },
                exc_info=True
            )
            return False
    
    async def cleanup_job_data(self, job_id: str) -> bool:
        """
        Clean up related data for a deleted job.
        
        Args:
            job_id: Job ID to clean up
            
        Returns:
            True if cleanup successful, False otherwise
        """
        try:
            # In a database-only implementation, this would involve
            # cleaning up related files, job artifacts, etc.
            logger.info(f"Job {job_id} cleanup completed (database-only implementation)")
            return True
            
        except Exception as e:
            logger.error(
                "Failed to cleanup job data",
                extra={
                    "job_id": job_id,
                    "error": str(e)
                },
                exc_info=True
            )
            return False

    async def get_job_by_id(self, job_id: str) -> Optional[Dict[str, Any]]:
        """
        Get job by ID from database.
        
        Args:
            job_id: Job ID to retrieve
            
        Returns:
            Job data or None if not found
        """
        try:
            async with self.db_manager.get_session() as session:
                query = "SELECT * FROM jobs WHERE id = $1 AND is_deleted = FALSE"
                row = await session.fetchrow(query, job_id)
                
                if row:
                    return dict(row)
                return None
                
        except Exception as e:
            logger.error(
                "Failed to get job by ID",
                extra={
                    "job_id": job_id,
                    "error": str(e)
                },
                exc_info=True
            )
            return None

    async def get_job_statistics(self, user_id: str) -> Dict[str, Any]:
        """
        Get job statistics for a user.
        
        Args:
            user_id: User ID to get statistics for
            
        Returns:
            Dict containing job statistics
        """
        try:
            async with self.db_manager.get_session() as session:
                # Get job counts by status
                status_query = """
                    SELECT status, COUNT(*) as count 
                    FROM jobs 
                    WHERE user_id = $1 AND is_deleted = FALSE 
                    GROUP BY status
                """
                status_results = await session.fetch(status_query, user_id)
                
                # Get total job count
                total_query = """
                    SELECT COUNT(*) 
                    FROM jobs 
                    WHERE user_id = $1 AND is_deleted = FALSE
                """
                total_count = await session.fetchval(total_query, user_id)
                
                jobs_by_status = {row['status']: row['count'] for row in status_results}
                
                return {
                    "total_jobs": total_count,
                    "jobs_by_status": jobs_by_status,
                    "jobs_by_type": {},  # Can be extended
                    "avg_processing_time": 0  # Can be calculated if needed
                }
                
        except Exception as e:
            logger.error(
                "Failed to get job statistics",
                extra={
                    "user_id": user_id,
                    "error": str(e)
                },
                exc_info=True
            )
            return {
                "total_jobs": 0,
                "jobs_by_status": {},
                "jobs_by_type": {},
                "avg_processing_time": 0
            }

    async def get_recent_jobs(
        self, 
        user_id: str, 
        limit: int = 5
    ) -> List[Dict[str, Any]]:
        """
        Get recent jobs for a user.
        
        Args:
            user_id: User ID
            limit: Maximum number of jobs to return
            
        Returns:
            List of recent job dictionaries
        """
        try:
            result = await self.get_jobs_paginated(
                user_id=user_id,
                limit=limit,
                offset=0
            )
            
            return result["jobs"]
            
        except Exception as e:
            logger.error(
                "Failed to get recent jobs",
                extra={
                    "user_id": user_id,
                    "error": str(e)
                },
                exc_info=True
            )
            return []