"""
Job-related value objects for the domain.

This module contains value objects specific to job processing,
including priority, status, and progress tracking.
"""

from dataclasses import dataclass
from decimal import Decimal
from enum import Enum
from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta

from ..common import ValueObject, BusinessRuleViolation


class JobStatus(str, Enum):
    """Job processing status with clear transitions."""
    CREATED = "created"
    QUEUED = "queued"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    ARCHIVED = "archived"


class JobPriority(str, Enum):
    """Job priority levels."""
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    URGENT = "urgent"


class JobType(str, Enum):
    """Types of jobs supported by the system."""
    VIDEO_GENERATION = "video_generation"
    BATCH_VIDEO_GENERATION = "batch_video_generation"
    FILE_PROCESSING = "file_processing"
    CONTENT_ANALYSIS = "content_analysis"


@dataclass(frozen=True)
class JobProgress(ValueObject):
    """
    Value object representing job progress with validation.
    
    Tracks percentage completion, current stage, and estimated completion time.
    """
    
    percentage: Decimal
    current_stage: Optional[str]
    stages_completed: List[str]
    estimated_completion: Optional[datetime]
    processing_time_seconds: Optional[Decimal]
    
    def validate(self) -> None:
        """Validate job progress values."""
        # Percentage validation
        if self.percentage < Decimal('0'):
            raise BusinessRuleViolation(
                "JobProgress.NegativePercentage",
                "Progress percentage cannot be negative"
            )
        
        if self.percentage > Decimal('100'):
            raise BusinessRuleViolation(
                "JobProgress.ExceedsMaximum",
                "Progress percentage cannot exceed 100"
            )
        
        # Current stage validation
        if self.current_stage is not None:
            if len(self.current_stage.strip()) == 0:
                raise BusinessRuleViolation(
                    "JobProgress.EmptyStage",
                    "Current stage cannot be empty if specified"
                )
            
            if len(self.current_stage) > 100:
                raise BusinessRuleViolation(
                    "JobProgress.StageTooLong",
                    "Current stage description cannot exceed 100 characters"
                )
        
        # Stages completed validation
        if len(self.stages_completed) > 50:
            raise BusinessRuleViolation(
                "JobProgress.TooManyStages",
                "Cannot have more than 50 completed stages"
            )
        
        for stage in self.stages_completed:
            if not stage or len(stage.strip()) == 0:
                raise BusinessRuleViolation(
                    "JobProgress.EmptyCompletedStage",
                    "Completed stages cannot be empty"
                )
        
        # Processing time validation
        if self.processing_time_seconds is not None:
            if self.processing_time_seconds < Decimal('0'):
                raise BusinessRuleViolation(
                    "JobProgress.NegativeProcessingTime",
                    "Processing time cannot be negative"
                )
            
            # Maximum processing time: 24 hours
            max_seconds = Decimal('86400')  # 24 hours
            if self.processing_time_seconds > max_seconds:
                raise BusinessRuleViolation(
                    "JobProgress.ProcessingTimeTooLong",
                    "Processing time cannot exceed 24 hours"
                )
        
        # Estimated completion validation
        if self.estimated_completion is not None:
            # Cannot be in the past (with 1 minute tolerance)
            now = datetime.utcnow()
            if self.estimated_completion < now - timedelta(minutes=1):
                raise BusinessRuleViolation(
                    "JobProgress.EstimatedCompletionInPast",
                    "Estimated completion cannot be in the past"
                )
            
            # Cannot be too far in the future (max 7 days)
            max_future = now + timedelta(days=7)
            if self.estimated_completion > max_future:
                raise BusinessRuleViolation(
                    "JobProgress.EstimatedCompletionTooFar",
                    "Estimated completion cannot be more than 7 days in the future"
                )
    
    @classmethod
    def initial(cls) -> "JobProgress":
        """Create initial job progress (0%)."""
        return cls(
            percentage=Decimal('0'),
            current_stage=None,
            stages_completed=[],
            estimated_completion=None,
            processing_time_seconds=None
        )
    
    @classmethod
    def completed(cls, processing_time_seconds: Optional[Decimal] = None) -> "JobProgress":
        """Create completed job progress (100%)."""
        return cls(
            percentage=Decimal('100'),
            current_stage="Completed",
            stages_completed=["initialization", "processing", "finalization"],
            estimated_completion=None,
            processing_time_seconds=processing_time_seconds
        )
    
    def with_percentage(self, percentage: Decimal) -> "JobProgress":
        """Create a new JobProgress with updated percentage."""
        return JobProgress(
            percentage=percentage,
            current_stage=self.current_stage,
            stages_completed=self.stages_completed,
            estimated_completion=self.estimated_completion,
            processing_time_seconds=self.processing_time_seconds
        )
    
    def with_stage(self, stage: str) -> "JobProgress":
        """Create a new JobProgress with updated current stage."""
        return JobProgress(
            percentage=self.percentage,
            current_stage=stage,
            stages_completed=self.stages_completed,
            estimated_completion=self.estimated_completion,
            processing_time_seconds=self.processing_time_seconds
        )
    
    def complete_stage(self, stage: str) -> "JobProgress":
        """Create a new JobProgress with a completed stage."""
        new_stages = self.stages_completed + [stage]
        return JobProgress(
            percentage=self.percentage,
            current_stage=self.current_stage,
            stages_completed=new_stages,
            estimated_completion=self.estimated_completion,
            processing_time_seconds=self.processing_time_seconds
        )
    
    @property
    def is_complete(self) -> bool:
        """Check if progress is 100% complete."""
        return self.percentage >= Decimal('100')
    
    @property
    def is_started(self) -> bool:
        """Check if progress has started (> 0%)."""
        return self.percentage > Decimal('0')
    
    @property
    def remaining_percentage(self) -> Decimal:
        """Get remaining percentage to completion."""
        return Decimal('100') - self.percentage
    
    def __repr__(self) -> str:
        return f"JobProgress({self.percentage}%, stage='{self.current_stage}')"


@dataclass(frozen=True)
class JobError(ValueObject):
    """
    Value object representing job error information.
    
    Provides structured error information for failed jobs.
    """
    
    error_code: str
    error_message: str
    error_details: Optional[Dict[str, Any]]
    occurred_at: datetime
    is_retryable: bool
    
    def validate(self) -> None:
        """Validate job error information."""
        if not self.error_code:
            raise BusinessRuleViolation(
                "JobError.MissingCode",
                "Error code is required"
            )
        
        if len(self.error_code) > 50:
            raise BusinessRuleViolation(
                "JobError.CodeTooLong",
                "Error code cannot exceed 50 characters"
            )
        
        if not self.error_message:
            raise BusinessRuleViolation(
                "JobError.MissingMessage",
                "Error message is required"
            )
        
        if len(self.error_message) > 1000:
            raise BusinessRuleViolation(
                "JobError.MessageTooLong",
                "Error message cannot exceed 1000 characters"
            )
        
        # Validate error details if provided
        if self.error_details is not None:
            if not isinstance(self.error_details, dict):
                raise BusinessRuleViolation(
                    "JobError.InvalidDetails",
                    "Error details must be a dictionary"
                )
    
    @classmethod
    def create(
        cls,
        error_code: str,
        error_message: str,
        is_retryable: bool = False,
        error_details: Optional[Dict[str, Any]] = None
    ) -> "JobError":
        """Create a new job error with current timestamp."""
        return cls(
            error_code=error_code,
            error_message=error_message,
            error_details=error_details,
            occurred_at=datetime.utcnow(),
            is_retryable=is_retryable
        )
    
    @property
    def short_description(self) -> str:
        """Get a short description of the error."""
        return f"{self.error_code}: {self.error_message[:100]}"
    
    def __repr__(self) -> str:
        return f"JobError(code='{self.error_code}', retryable={self.is_retryable})"


@dataclass(frozen=True)
class JobMetrics(ValueObject):
    """
    Value object representing job performance metrics.
    
    Tracks resource usage, timing, and other performance indicators.
    """
    
    cpu_usage_percent: Optional[Decimal]
    memory_usage_mb: Optional[Decimal]
    processing_time_seconds: Optional[Decimal]
    queue_wait_time_seconds: Optional[Decimal]
    resource_costs: Optional[Dict[str, Decimal]]
    throughput_metrics: Optional[Dict[str, Any]]
    
    def validate(self) -> None:
        """Validate job metrics."""
        # CPU usage validation
        if self.cpu_usage_percent is not None:
            if self.cpu_usage_percent < Decimal('0') or self.cpu_usage_percent > Decimal('100'):
                raise BusinessRuleViolation(
                    "JobMetrics.InvalidCpuUsage",
                    "CPU usage must be between 0 and 100 percent"
                )
        
        # Memory usage validation
        if self.memory_usage_mb is not None:
            if self.memory_usage_mb < Decimal('0'):
                raise BusinessRuleViolation(
                    "JobMetrics.NegativeMemoryUsage",
                    "Memory usage cannot be negative"
                )
            
            # Maximum 32GB memory usage
            max_memory = Decimal('32768')  # 32GB in MB
            if self.memory_usage_mb > max_memory:
                raise BusinessRuleViolation(
                    "JobMetrics.ExcessiveMemoryUsage",
                    f"Memory usage cannot exceed {max_memory} MB"
                )
        
        # Processing time validation
        if self.processing_time_seconds is not None:
            if self.processing_time_seconds < Decimal('0'):
                raise BusinessRuleViolation(
                    "JobMetrics.NegativeProcessingTime",
                    "Processing time cannot be negative"
                )
        
        # Queue wait time validation
        if self.queue_wait_time_seconds is not None:
            if self.queue_wait_time_seconds < Decimal('0'):
                raise BusinessRuleViolation(
                    "JobMetrics.NegativeQueueTime",
                    "Queue wait time cannot be negative"
                )
        
        # Resource costs validation
        if self.resource_costs is not None:
            for resource, cost in self.resource_costs.items():
                if cost < Decimal('0'):
                    raise BusinessRuleViolation(
                        "JobMetrics.NegativeResourceCost",
                        f"Resource cost for {resource} cannot be negative"
                    )
    
    @classmethod
    def empty(cls) -> "JobMetrics":
        """Create empty job metrics."""
        return cls(
            cpu_usage_percent=None,
            memory_usage_mb=None,
            processing_time_seconds=None,
            queue_wait_time_seconds=None,
            resource_costs=None,
            throughput_metrics=None
        )
    
    @property
    def has_performance_data(self) -> bool:
        """Check if metrics contain performance data."""
        return any([
            self.cpu_usage_percent is not None,
            self.memory_usage_mb is not None,
            self.processing_time_seconds is not None
        ])
    
    @property
    def total_cost(self) -> Optional[Decimal]:
        """Get total resource cost if available."""
        if self.resource_costs is None:
            return None
        return sum(self.resource_costs.values())
    
    def __repr__(self) -> str:
        return (f"JobMetrics(cpu={self.cpu_usage_percent}%, "
                f"memory={self.memory_usage_mb}MB, "
                f"time={self.processing_time_seconds}s)")


@dataclass(frozen=True)
class JobConfiguration(ValueObject):
    """
    Value object representing job configuration with validation.
    
    Contains all configuration needed to execute a job.
    """
    
    config_data: Dict[str, Any]
    
    @classmethod
    def create(cls, config_data: Dict[str, Any]) -> "Result[JobConfiguration]":
        """
        Create job configuration with validation.
        
        Args:
            config_data: Dictionary containing job configuration
            
        Returns:
            Result containing JobConfiguration or error
        """
        from .. import Result
        
        try:
            if not isinstance(config_data, dict):
                return Result.fail("Configuration must be a dictionary")
            
            if not config_data:
                return Result.fail("Configuration cannot be empty")
            
            # Validate configuration structure
            instance = cls(config_data=config_data.copy())
            instance.validate()
            
            return Result.ok(instance)
            
        except Exception as e:
            return Result.fail(f"Invalid job configuration: {str(e)}")
    
    def validate(self) -> None:
        """Validate job configuration."""
        if not isinstance(self.config_data, dict):
            raise BusinessRuleViolation(
                "JobConfiguration.InvalidType",
                "Configuration data must be a dictionary"
            )
        
        # Check maximum depth to prevent infinite nesting
        max_depth = 10
        if self._get_dict_depth(self.config_data) > max_depth:
            raise BusinessRuleViolation(
                "JobConfiguration.TooDeep",
                f"Configuration nesting cannot exceed {max_depth} levels"
            )
        
        # Check serializable data types
        try:
            import json
            json.dumps(self.config_data)
        except (TypeError, ValueError) as e:
            raise BusinessRuleViolation(
                "JobConfiguration.NotSerializable",
                f"Configuration must contain only JSON-serializable data: {str(e)}"
            )
    
    def _get_dict_depth(self, d: Dict[str, Any], current_depth: int = 0) -> int:
        """Calculate maximum depth of nested dictionary."""
        if not isinstance(d, dict):
            return current_depth
        
        max_depth = current_depth
        for value in d.values():
            if isinstance(value, dict):
                depth = self._get_dict_depth(value, current_depth + 1)
                max_depth = max(max_depth, depth)
        
        return max_depth
    
    def get(self, key: str, default: Any = None) -> Any:
        """Get configuration value by key."""
        return self.config_data.get(key, default)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return self.config_data.copy()
    
    def update(self, updates: Dict[str, Any]) -> "JobConfiguration":
        """Create new configuration with updates."""
        new_data = self.config_data.copy()
        new_data.update(updates)
        
        result = self.create(new_data)
        if result.success:
            return result.value
        else:
            raise BusinessRuleViolation(
                "JobConfiguration.UpdateFailed",
                f"Failed to update configuration: {result.error}"
            )
    
    def __repr__(self) -> str:
        return f"JobConfiguration(keys={list(self.config_data.keys())})"
