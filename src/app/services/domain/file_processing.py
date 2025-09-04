"""
File Processing Domain Service - Pure business logic for file processing.

This service contains only the core business rules for file validation,
processing, and management without any infrastructure concerns.
"""

import logging
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
import mimetypes
from pathlib import Path

from ...models.file import FileMetadataResponse as FileMetadata, FileUploadRequest as UploadFileRequest
from ...models.user import ClerkUser
from ..interfaces.domain import IFileProcessingService
from ..interfaces.base import ServiceResult

logger = logging.getLogger(__name__)


class FileProcessingService(IFileProcessingService):
    """Domain service for file processing business logic."""
    
    @property
    def service_name(self) -> str:
        return "FileProcessingService"
    
    # File validation rules
    MAX_FILE_SIZE_BYTES = {
        "free": 50 * 1024 * 1024,      # 50MB
        "pro": 500 * 1024 * 1024,     # 500MB
        "enterprise": 2 * 1024 * 1024 * 1024  # 2GB
    }
    
    ALLOWED_FILE_TYPES = {
        "image": [".jpg", ".jpeg", ".png", ".gif", ".bmp", ".webp"],
        "video": [".mp4", ".avi", ".mov", ".wmv", ".flv", ".webm"],
        "audio": [".mp3", ".wav", ".flac", ".aac", ".ogg"],
        "document": [".pdf", ".txt", ".docx", ".doc", ".rtf"],
        "data": [".json", ".csv", ".xml", ".yaml", ".yml"]
    }
    
    # Storage quotas by subscription tier
    STORAGE_QUOTAS = {
        "free": 1 * 1024 * 1024 * 1024,        # 1GB
        "pro": 100 * 1024 * 1024 * 1024,       # 100GB
        "enterprise": 1000 * 1024 * 1024 * 1024  # 1TB
    }
    
    # File retention periods
    RETENTION_PERIODS = {
        "free": timedelta(days=30),
        "pro": timedelta(days=365),
        "enterprise": timedelta(days=1095)  # 3 years
    }
    
    async def validate_file_upload(
        self, 
        request: UploadFileRequest, 
        user: ClerkUser
    ) -> ServiceResult[Dict[str, Any]]:
        """Validate file upload according to business rules."""
        try:
            validation_errors = []
            warnings = []
            
            # File size validation
            max_size = self.MAX_FILE_SIZE_BYTES.get(user.subscription_tier, self.MAX_FILE_SIZE_BYTES["free"])
            if request.file_size > max_size:
                validation_errors.append(
                    f"File size {request.file_size} bytes exceeds limit of {max_size} bytes for {user.subscription_tier} tier"
                )
            
            # File type validation
            file_extension = Path(request.filename).suffix.lower()
            if not self._is_allowed_file_type(file_extension):
                validation_errors.append(f"File type '{file_extension}' is not allowed")
            
            # Filename validation
            if not self._is_valid_filename(request.filename):
                validation_errors.append("Invalid filename format")
            
            # Content type validation
            expected_content_type = mimetypes.guess_type(request.filename)[0]
            if request.content_type and request.content_type != expected_content_type:
                warnings.append(f"Content type mismatch: expected {expected_content_type}, got {request.content_type}")
            
            # Virus scanning placeholder (would integrate with actual scanner)
            scan_result = await self._simulate_virus_scan(request)
            if not scan_result:
                validation_errors.append("File failed security scan")
            
            # Storage quota check
            quota_result = await self.calculate_storage_quota(user)
            if quota_result.success:
                remaining_quota = quota_result.data.get("remaining", 0)
                if request.file_size > remaining_quota:
                    validation_errors.append(f"Insufficient storage quota. Required: {request.file_size}, Available: {remaining_quota}")
            
            if validation_errors:
                return ServiceResult.error(
                    error="; ".join(validation_errors),
                    error_code="FILE_VALIDATION_ERROR",
                    metadata={
                        "validation_errors": validation_errors,
                        "warnings": warnings
                    }
                )
            
            return ServiceResult.success({
                "valid": True,
                "file_category": self._get_file_category(file_extension),
                "processing_required": self._requires_processing(file_extension),
                "warnings": warnings
            })
            
        except Exception as e:
            logger.error(f"Error validating file upload: {e}")
            return ServiceResult.error(
                error="Failed to validate file upload",
                error_code="FILE_VALIDATION_SERVICE_ERROR"
            )
    
    async def calculate_storage_quota(
        self, 
        user: ClerkUser
    ) -> ServiceResult[Dict[str, int]]:
        """Calculate available storage quota for user."""
        try:
            total_quota = self.STORAGE_QUOTAS.get(
                user.subscription_tier, 
                self.STORAGE_QUOTAS["free"]
            )
            
            # In a real implementation, this would query the database
            # For now, simulate some used storage
            used_storage = self._simulate_used_storage(user)
            remaining_quota = max(0, total_quota - used_storage)
            
            return ServiceResult.success({
                "total": total_quota,
                "used": used_storage,
                "remaining": remaining_quota,
                "percentage_used": (used_storage / total_quota) * 100 if total_quota > 0 else 0
            })
            
        except Exception as e:
            logger.error(f"Error calculating storage quota: {e}")
            return ServiceResult.error(
                error="Failed to calculate storage quota",
                error_code="QUOTA_CALCULATION_ERROR"
            )
    
    async def determine_file_retention(
        self, 
        file_metadata: FileMetadata, 
        user: ClerkUser
    ) -> ServiceResult[datetime]:
        """Determine file retention period based on business rules."""
        try:
            retention_period = self.RETENTION_PERIODS.get(
                user.subscription_tier,
                self.RETENTION_PERIODS["free"]
            )
            
            # Apply special rules
            file_category = self._get_file_category(Path(file_metadata.filename).suffix.lower())
            
            # Important file types get extended retention
            if file_category in ["document", "data"]:
                retention_period = retention_period + timedelta(days=30)
            
            # Large files get shorter retention for free tier
            if user.subscription_tier == "free" and file_metadata.file_size > 10 * 1024 * 1024:  # 10MB
                retention_period = timedelta(days=7)
            
            expiration_date = file_metadata.created_at + retention_period
            
            return ServiceResult.success(
                expiration_date,
                metadata={
                    "retention_days": retention_period.days,
                    "file_category": file_category,
                    "subscription_tier": user.subscription_tier,
                    "created_at": file_metadata.created_at.isoformat()
                }
            )
            
        except Exception as e:
            logger.error(f"Error determining file retention: {e}")
            return ServiceResult.error(
                error="Failed to determine file retention",
                error_code="RETENTION_CALCULATION_ERROR"
            )
    
    def _is_allowed_file_type(self, file_extension: str) -> bool:
        """Check if file extension is allowed."""
        for category, extensions in self.ALLOWED_FILE_TYPES.items():
            if file_extension in extensions:
                return True
        return False
    
    def _get_file_category(self, file_extension: str) -> str:
        """Get file category from extension."""
        for category, extensions in self.ALLOWED_FILE_TYPES.items():
            if file_extension in extensions:
                return category
        return "unknown"
    
    def _is_valid_filename(self, filename: str) -> bool:
        """Validate filename format."""
        # Basic filename validation
        if not filename or len(filename) > 255:
            return False
        
        # Check for invalid characters
        invalid_chars = ['<', '>', ':', '"', '|', '?', '*', '\\', '/']
        if any(char in filename for char in invalid_chars):
            return False
        
        # Must have extension
        if '.' not in filename:
            return False
        
        return True
    
    def _requires_processing(self, file_extension: str) -> bool:
        """Check if file type requires additional processing."""
        processing_required = {
            ".pdf": True,   # Text extraction
            ".docx": True,  # Text extraction
            ".mp4": True,   # Thumbnail generation
            ".mov": True,   # Thumbnail generation
            ".jpg": True,   # Metadata extraction
            ".png": True,   # Metadata extraction
        }
        return processing_required.get(file_extension, False)
    
    async def _simulate_virus_scan(self, request: UploadFileRequest) -> bool:
        """Simulate virus scanning (would integrate with real scanner)."""
        # In real implementation, this would call external virus scanning service
        # For now, simulate based on filename patterns
        suspicious_patterns = ['.exe', '.bat', '.cmd', '.scr', '.vbs']
        return not any(pattern in request.filename.lower() for pattern in suspicious_patterns)
    
    def _simulate_used_storage(self, user: ClerkUser) -> int:
        """Simulate used storage calculation."""
        # In real implementation, this would query the database
        # For simulation, return different amounts based on subscription
        base_usage = {
            "free": 100 * 1024 * 1024,      # 100MB
            "pro": 10 * 1024 * 1024 * 1024,  # 10GB
            "enterprise": 50 * 1024 * 1024 * 1024  # 50GB
        }
        return base_usage.get(user.subscription_tier, 0)
