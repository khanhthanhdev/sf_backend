"""
Job domain entity.

This module defines the Job aggregate root with business logic,
validation rules, and domain events for job processing management.
"""

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any
from uuid import UUID, uuid4

from ..common import AggregateRoot, DomainEvent, BusinessRuleViolation, Result
from ..value_objects import (
    JobId, UserId, VideoId, JobStatus, JobPriority, JobType, 
    JobProgress, JobError, JobMetrics
)


@dataclass(frozen=True)
class JobCreated(DomainEvent):
    """Domain event raised when a job is created."""
    job_id: JobId
    user_id: UserId
    job_type: JobType
    priority: JobPriority


@dataclass(frozen=True)
class JobStarted(DomainEvent):
    """Domain event raised when a job starts processing."""
    job_id: JobId
    worker_id: Optional[str]
    processing_node: Optional[str]


@dataclass(frozen=True)
class JobProgressUpdated(DomainEvent):
    """Domain event raised when job progress is updated."""
    job_id: JobId
    progress: JobProgress


@dataclass(frozen=True)
class JobCompleted(DomainEvent):
    """Domain event raised when a job completes successfully."""
    job_id: JobId
    result_url: Optional[str]
    metrics: JobMetrics


@dataclass(frozen=True)
class JobFailed(DomainEvent):
    """Domain event raised when a job fails."""
    job_id: JobId
    error: JobError
    is_retryable: bool


@dataclass(frozen=True)
class JobCancelled(DomainEvent):
    """Domain event raised when a job is cancelled."""
    job_id: JobId
    cancelled_by: UserId
    reason: str


class Job(AggregateRoot):
    """
    Job aggregate root representing a processing job in the system.
    
    Jobs are created to handle various types of processing tasks,
    primarily video generation, and track their progress through
    the processing pipeline.
    
    Business Rules:
    - Must have a valid configuration for the job type
    - Can only be cancelled before completion
    - Cannot be restarted once completed successfully
    - Progress must be monotonically increasing
    - Retry count cannot exceed maximum retries
    """
    
    def __init__(
        self,
        job_id: JobId,
        user_id: UserId,
        job_type: JobType,
        configuration: Dict[str, Any],
        priority: JobPriority = JobPriority.NORMAL,
        status: JobStatus = JobStatus.CREATED,
        progress: Optional[JobProgress] = None,
        estimated_completion: Optional[datetime] = None,
        result_url: Optional[str] = None,
        error_info: Optional[JobError] = None,
        metrics: Optional[JobMetrics] = None,
        batch_id: Optional[UUID] = None,
        parent_job_id: Optional[JobId] = None,
        worker_id: Optional[str] = None,
        processing_node: Optional[str] = None,
        created_at: Optional[datetime] = None,
        started_at: Optional[datetime] = None,
        completed_at: Optional[datetime] = None,
        retry_count: int = 0,
        max_retries: int = 3
    ):
        super().__init__(job_id.value)
        
        self._job_id = job_id
        self._user_id = user_id
        self._job_type = job_type
        self._configuration = configuration
        self._priority = priority
        self._status = status
        self._progress = progress or JobProgress.initial()
        self._estimated_completion = estimated_completion
        self._result_url = result_url
        self._error_info = error_info
        self._metrics = metrics or JobMetrics.empty()
        self._batch_id = batch_id
        self._parent_job_id = parent_job_id
        self._worker_id = worker_id
        self._processing_node = processing_node
        self._created_at = created_at or datetime.utcnow()
        self._updated_at = datetime.utcnow()
        self._started_at = started_at
        self._completed_at = completed_at
        self._retry_count = retry_count
        self._max_retries = max_retries
        self._is_deleted = False
        self._deleted_at = None
        
        # Validate business rules
        self._validate_business_rules()
    
    @classmethod
    def create(
        cls,
        user_id: UserId,
        job_type: JobType,
        configuration: Dict[str, Any],
        priority: JobPriority = JobPriority.NORMAL,
        batch_id: Optional[UUID] = None,
        parent_job_id: Optional[JobId] = None
    ) -> Result["Job"]:
        """
        Create a new job with business rule validation.
        
        Returns:
            Result containing the created Job or error message
        """
        try:
            # Generate new job ID
            job_id = JobId.generate()
            
            # Create job instance
            job = cls(
                job_id=job_id,
                user_id=user_id,
                job_type=job_type,
                configuration=configuration,
                priority=priority,
                batch_id=batch_id,
                parent_job_id=parent_job_id
            )
            
            # Add domain event
            job.add_domain_event(JobCreated(
                event_id=uuid4(),
                occurred_at=datetime.utcnow(),
                aggregate_id=job.id,
                version=job.version,
                job_id=job_id,
                user_id=user_id,
                job_type=job_type,
                priority=priority
            ))
            
            return Result.ok(job)
            
        except BusinessRuleViolation as e:
            return Result.fail(str(e))
    
    # Properties
    @property
    def job_id(self) -> JobId:
        """Get the job ID."""
        return self._job_id
    
    @property
    def user_id(self) -> UserId:
        """Get the user ID who owns this job."""
        return self._user_id
    
    @property
    def job_type(self) -> JobType:
        """Get the job type."""
        return self._job_type
    
    @property
    def configuration(self) -> Dict[str, Any]:
        """Get the job configuration."""
        return self._configuration.copy()
    
    @property
    def priority(self) -> JobPriority:
        """Get the job priority."""
        return self._priority
    
    @property
    def status(self) -> JobStatus:
        """Get the job status."""
        return self._status
    
    @property
    def progress(self) -> JobProgress:
        """Get the job progress."""
        return self._progress
    
    @property
    def estimated_completion(self) -> Optional[datetime]:
        """Get the estimated completion time."""
        return self._estimated_completion
    
    @property
    def result_url(self) -> Optional[str]:
        """Get the result URL if job is completed."""
        return self._result_url
    
    @property
    def error_info(self) -> Optional[JobError]:
        """Get the error information if job failed."""
        return self._error_info
    
    @property
    def metrics(self) -> JobMetrics:
        """Get the job metrics."""
        return self._metrics
    
    @property
    def batch_id(self) -> Optional[UUID]:
        """Get the batch ID if job is part of a batch."""
        return self._batch_id
    
    @property
    def parent_job_id(self) -> Optional[JobId]:
        """Get the parent job ID if this is a child job."""
        return self._parent_job_id
    
    @property
    def worker_id(self) -> Optional[str]:
        """Get the worker ID processing this job."""
        return self._worker_id
    
    @property
    def processing_node(self) -> Optional[str]:
        """Get the processing node handling this job."""
        return self._processing_node
    
    @property
    def created_at(self) -> datetime:
        """Get creation timestamp."""
        return self._created_at
    
    @property
    def updated_at(self) -> datetime:
        """Get last update timestamp."""
        return self._updated_at
    
    @property
    def started_at(self) -> Optional[datetime]:
        """Get processing start timestamp."""
        return self._started_at
    
    @property
    def completed_at(self) -> Optional[datetime]:
        """Get completion timestamp."""
        return self._completed_at
    
    @property
    def processing_duration_seconds(self) -> Optional[int]:
        """Get processing duration in seconds if completed."""
        if self._started_at and self._completed_at:
            duration = self._completed_at - self._started_at
            return int(duration.total_seconds())
        return None
    
    @property
    def queue_wait_time_seconds(self) -> Optional[int]:
        """Get queue wait time in seconds if started."""
        if self._started_at:
            wait_time = self._started_at - self._created_at
            return int(wait_time.total_seconds())
        return None
    
    @property
    def retry_count(self) -> int:
        """Get the current retry count."""
        return self._retry_count
    
    @property
    def max_retries(self) -> int:
        """Get the maximum number of retries."""
        return self._max_retries
    
    @property
    def is_deleted(self) -> bool:
        """Check if job is soft deleted."""
        return self._is_deleted
    
    @property
    def deleted_at(self) -> Optional[datetime]:
        """Get deletion timestamp."""
        return self._deleted_at
    
    # Business logic methods
    def can_be_started(self) -> bool:
        """Check if the job can be started."""
        return self._status in [JobStatus.CREATED, JobStatus.QUEUED]
    
    def can_be_cancelled(self) -> bool:
        """Check if the job can be cancelled."""
        return self._status in [JobStatus.CREATED, JobStatus.QUEUED, JobStatus.PROCESSING]
    
    def can_be_retried(self) -> bool:
        """Check if the job can be retried."""
        return (self._status == JobStatus.FAILED and 
                self._retry_count < self._max_retries and
                self._error_info and self._error_info.is_retryable)
    
    def is_terminal_state(self) -> bool:
        """Check if the job is in a terminal state."""
        return self._status in [JobStatus.COMPLETED, JobStatus.CANCELLED]
    
    def is_processing(self) -> bool:
        """Check if the job is currently processing."""
        return self._status == JobStatus.PROCESSING
    
    def is_complete(self) -> bool:
        """Check if the job completed successfully."""
        return self._status == JobStatus.COMPLETED
    
    def has_failed(self) -> bool:
        """Check if the job has failed."""
        return self._status == JobStatus.FAILED
    
    def needs_retry(self) -> bool:
        """Check if the job needs to be retried."""
        return self.has_failed() and self.can_be_retried()
    
    def is_high_priority(self) -> bool:
        """Check if the job has high or urgent priority."""
        return self._priority in [JobPriority.HIGH, JobPriority.URGENT]
    
    def is_batch_job(self) -> bool:
        """Check if this job is part of a batch."""
        return self._batch_id is not None
    
    def is_child_job(self) -> bool:
        """Check if this job is a child of another job."""
        return self._parent_job_id is not None
    
    # Mutation methods
    def queue(self) -> Result[None]:
        """Queue the job for processing."""
        try:
            if self._status != JobStatus.CREATED:
                raise BusinessRuleViolation(
                    "Job.CannotQueue",
                    f"Cannot queue job in status: {self._status}"
                )
            
            self._status = JobStatus.QUEUED
            self._updated_at = datetime.utcnow()
            self.increment_version()
            
            return Result.ok(None)
            
        except BusinessRuleViolation as e:
            return Result.fail(str(e))
    
    def start_processing(
        self,
        worker_id: Optional[str] = None,
        processing_node: Optional[str] = None,
        estimated_completion: Optional[datetime] = None
    ) -> Result[None]:
        """Start processing the job."""
        try:
            if not self.can_be_started():
                raise BusinessRuleViolation(
                    "Job.CannotStart",
                    f"Cannot start job in status: {self._status}"
                )
            
            self._status = JobStatus.PROCESSING
            self._worker_id = worker_id
            self._processing_node = processing_node
            self._started_at = datetime.utcnow()
            self._estimated_completion = estimated_completion
            self._updated_at = datetime.utcnow()
            self.increment_version()
            
            self.add_domain_event(JobStarted(
                event_id=uuid4(),
                occurred_at=datetime.utcnow(),
                aggregate_id=self.id,
                version=self.version,
                job_id=self._job_id,
                worker_id=worker_id,
                processing_node=processing_node
            ))
            
            return Result.ok(None)
            
        except BusinessRuleViolation as e:
            return Result.fail(str(e))
    
    def update_progress(self, progress: JobProgress) -> Result[None]:
        """Update job progress."""
        try:
            if self._status != JobStatus.PROCESSING:
                raise BusinessRuleViolation(
                    "Job.NotProcessing",
                    "Cannot update progress for non-processing job"
                )
            
            # Business rule: Progress must be monotonically increasing
            if progress.percentage < self._progress.percentage:
                raise BusinessRuleViolation(
                    "Job.ProgressCannotDecrease",
                    "Job progress cannot decrease"
                )
            
            self._progress = progress
            self._updated_at = datetime.utcnow()
            self.increment_version()
            
            self.add_domain_event(JobProgressUpdated(
                event_id=uuid4(),
                occurred_at=datetime.utcnow(),
                aggregate_id=self.id,
                version=self.version,
                job_id=self._job_id,
                progress=progress
            ))
            
            return Result.ok(None)
            
        except BusinessRuleViolation as e:
            return Result.fail(str(e))
    
    def complete(
        self,
        result_url: Optional[str] = None,
        metrics: Optional[JobMetrics] = None
    ) -> Result[None]:
        """Complete the job successfully."""
        try:
            if self._status != JobStatus.PROCESSING:
                raise BusinessRuleViolation(
                    "Job.NotProcessing",
                    "Cannot complete non-processing job"
                )
            
            self._status = JobStatus.COMPLETED
            self._result_url = result_url
            self._completed_at = datetime.utcnow()
            self._progress = JobProgress.completed(
                processing_time_seconds=self._progress.processing_time_seconds
            )
            
            if metrics:
                self._metrics = metrics
            
            # Update metrics with processing time if not provided
            if self._started_at:
                processing_time = (self._completed_at - self._started_at).total_seconds()
                if not self._metrics.processing_time_seconds:
                    from decimal import Decimal
                    self._metrics = JobMetrics(
                        cpu_usage_percent=self._metrics.cpu_usage_percent,
                        memory_usage_mb=self._metrics.memory_usage_mb,
                        processing_time_seconds=Decimal(str(processing_time)),
                        queue_wait_time_seconds=self._metrics.queue_wait_time_seconds,
                        resource_costs=self._metrics.resource_costs,
                        throughput_metrics=self._metrics.throughput_metrics
                    )
            
            self._updated_at = datetime.utcnow()
            self.increment_version()
            
            self.add_domain_event(JobCompleted(
                event_id=uuid4(),
                occurred_at=datetime.utcnow(),
                aggregate_id=self.id,
                version=self.version,
                job_id=self._job_id,
                result_url=result_url,
                metrics=self._metrics
            ))
            
            return Result.ok(None)
            
        except BusinessRuleViolation as e:
            return Result.fail(str(e))
    
    def fail(self, error: JobError) -> Result[None]:
        """Mark the job as failed."""
        try:
            if self._status not in [JobStatus.PROCESSING, JobStatus.QUEUED]:
                raise BusinessRuleViolation(
                    "Job.CannotFail",
                    f"Cannot fail job in status: {self._status}"
                )
            
            self._status = JobStatus.FAILED
            self._error_info = error
            self._updated_at = datetime.utcnow()
            
            if error.is_retryable and self._retry_count < self._max_retries:
                self._retry_count += 1
            
            self.increment_version()
            
            self.add_domain_event(JobFailed(
                event_id=uuid4(),
                occurred_at=datetime.utcnow(),
                aggregate_id=self.id,
                version=self.version,
                job_id=self._job_id,
                error=error,
                is_retryable=self.can_be_retried()
            ))
            
            return Result.ok(None)
            
        except BusinessRuleViolation as e:
            return Result.fail(str(e))
    
    def cancel(self, cancelled_by: UserId, reason: str) -> Result[None]:
        """Cancel the job."""
        try:
            if not self.can_be_cancelled():
                raise BusinessRuleViolation(
                    "Job.CannotCancel",
                    f"Cannot cancel job in status: {self._status}"
                )
            
            if not reason or len(reason.strip()) == 0:
                raise BusinessRuleViolation(
                    "Job.CancelReasonRequired",
                    "Cancel reason is required"
                )
            
            self._status = JobStatus.CANCELLED
            self._completed_at = datetime.utcnow()
            self._updated_at = datetime.utcnow()
            self.increment_version()
            
            self.add_domain_event(JobCancelled(
                event_id=uuid4(),
                occurred_at=datetime.utcnow(),
                aggregate_id=self.id,
                version=self.version,
                job_id=self._job_id,
                cancelled_by=cancelled_by,
                reason=reason
            ))
            
            return Result.ok(None)
            
        except BusinessRuleViolation as e:
            return Result.fail(str(e))
    
    def retry(self) -> Result[None]:
        """Retry the failed job."""
        try:
            if not self.can_be_retried():
                raise BusinessRuleViolation(
                    "Job.CannotRetry",
                    "Job cannot be retried"
                )
            
            self._status = JobStatus.CREATED
            self._progress = JobProgress.initial()
            self._error_info = None
            self._worker_id = None
            self._processing_node = None
            self._started_at = None
            self._completed_at = None
            self._estimated_completion = None
            self._updated_at = datetime.utcnow()
            self.increment_version()
            
            return Result.ok(None)
            
        except BusinessRuleViolation as e:
            return Result.fail(str(e))
    
    def update_priority(self, new_priority: JobPriority) -> Result[None]:
        """Update job priority if not in terminal state."""
        try:
            if self.is_terminal_state():
                raise BusinessRuleViolation(
                    "Job.CannotChangePriorityInTerminalState",
                    "Cannot change priority of completed or cancelled job"
                )
            
            if new_priority != self._priority:
                self._priority = new_priority
                self._updated_at = datetime.utcnow()
                self.increment_version()
            
            return Result.ok(None)
            
        except BusinessRuleViolation as e:
            return Result.fail(str(e))
    
    def soft_delete(self) -> Result[None]:
        """Soft delete the job."""
        try:
            if self.is_processing():
                raise BusinessRuleViolation(
                    "Job.CannotDeleteWhileProcessing",
                    "Cannot delete job while processing"
                )
            
            self._is_deleted = True
            self._deleted_at = datetime.utcnow()
            self._updated_at = datetime.utcnow()
            self.increment_version()
            
            return Result.ok(None)
            
        except BusinessRuleViolation as e:
            return Result.fail(str(e))
    
    # Validation methods
    def _validate_business_rules(self) -> None:
        """Validate all business rules for the job."""
        self._validate_configuration()
        self._validate_priority()
        self._validate_status()
        self._validate_retry_count()
        if self._estimated_completion:
            self._validate_estimated_completion()
    
    def _validate_configuration(self) -> None:
        """Validate job configuration."""
        if not self._configuration:
            raise BusinessRuleViolation(
                "Job.ConfigurationRequired",
                "Job configuration is required"
            )
        
        if not isinstance(self._configuration, dict):
            raise BusinessRuleViolation(
                "Job.InvalidConfiguration",
                "Job configuration must be a dictionary"
            )
        
        # Validate required fields based on job type
        if self._job_type == JobType.VIDEO_GENERATION:
            required_fields = ["topic", "context"]
            for field in required_fields:
                if field not in self._configuration:
                    raise BusinessRuleViolation(
                        "Job.MissingConfigurationField",
                        f"Required configuration field missing: {field}"
                    )
    
    def _validate_priority(self) -> None:
        """Validate job priority."""
        valid_priorities = [
            JobPriority.LOW,
            JobPriority.NORMAL,
            JobPriority.HIGH,
            JobPriority.URGENT
        ]
        if self._priority not in valid_priorities:
            raise BusinessRuleViolation(
                "Job.InvalidPriority",
                f"Invalid job priority: {self._priority}"
            )
    
    def _validate_status(self) -> None:
        """Validate job status."""
        valid_statuses = [
            JobStatus.CREATED,
            JobStatus.QUEUED,
            JobStatus.PROCESSING,
            JobStatus.COMPLETED,
            JobStatus.FAILED,
            JobStatus.CANCELLED
        ]
        if self._status not in valid_statuses:
            raise BusinessRuleViolation(
                "Job.InvalidStatus",
                f"Invalid job status: {self._status}"
            )
    
    def _validate_retry_count(self) -> None:
        """Validate retry count."""
        if self._retry_count < 0:
            raise BusinessRuleViolation(
                "Job.NegativeRetryCount",
                "Retry count cannot be negative"
            )
        
        if self._retry_count > self._max_retries:
            raise BusinessRuleViolation(
                "Job.ExceedsMaxRetries",
                f"Retry count ({self._retry_count}) exceeds maximum ({self._max_retries})"
            )
    
    def _validate_estimated_completion(self) -> None:
        """Validate estimated completion time."""
        if self._estimated_completion <= self._created_at:
            raise BusinessRuleViolation(
                "Job.InvalidEstimatedCompletion",
                "Estimated completion must be after creation time"
            )
        
        # Maximum 24 hours from creation
        max_completion = self._created_at + timedelta(hours=24)
        if self._estimated_completion > max_completion:
            raise BusinessRuleViolation(
                "Job.EstimatedCompletionTooFar",
                "Estimated completion cannot be more than 24 hours from creation"
            )
    
    def __repr__(self) -> str:
        return f"Job(id={self._job_id}, type={self._job_type}, status={self._status})"
