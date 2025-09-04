"""
Mappers for converting between domain entities and database models.

This module provides bidirectional mapping between rich domain entities
and SQLAlchemy database models, maintaining separation of concerns
between the domain layer and infrastructure layer.
"""

from typing import Optional, List, Dict, Any
from datetime import datetime
from uuid import UUID

from sqlalchemy.orm import Session
from sqlalchemy import text

from ...app.database.models import User as UserModel, Job as JobModel, FileMetadata as FileModel
from ...domain.entities import User, Video, Job, File
from ...domain.value_objects import (
    UserId, VideoId, JobId, FileId, EmailAddress, PhoneNumber,
    VideoTitle, VideoDescription, VideoTopic, VideoContext, VideoStatus,
    VideoProcessingConfig, VideoQuality, VideoFormat, VideoResolution,
    JobStatus, JobPriority, JobType, JobProgress, JobConfiguration,
    FileSize, FileType, FilePath, S3Location
)
from ...domain import Result


class EntityMapper:
    """Base class for entity mapping operations."""
    
    @staticmethod
    def safe_uuid(value: Any) -> Optional[UUID]:
        """Safely convert value to UUID."""
        if value is None:
            return None
        if isinstance(value, UUID):
            return value
        if isinstance(value, str):
            try:
                return UUID(value)
            except ValueError:
                return None
        return None


class UserMapper(EntityMapper):
    """Mapper for User domain entity and UserModel database model."""
    
    @staticmethod
    def to_domain(db_user: UserModel) -> Result[User]:
        """Convert database model to domain entity."""
        try:
            # Map email addresses
            email_addresses = []
            if db_user.email_addresses:
                for email_data in db_user.email_addresses:
                    if isinstance(email_data, dict) and 'email_address' in email_data:
                        email_result = EmailAddress.create(email_data['email_address'])
                        if email_result.success:
                            email_addresses.append(email_result.value)
            
            # Map phone numbers
            phone_numbers = []
            if db_user.phone_numbers:
                for phone_data in db_user.phone_numbers:
                    if isinstance(phone_data, dict) and 'phone_number' in phone_data:
                        phone_result = PhoneNumber.create(phone_data['phone_number'])
                        if phone_result.success:
                            phone_numbers.append(phone_result.value)
            
            # Create primary email if available
            primary_email = None
            if db_user.primary_email:
                email_result = EmailAddress.create(db_user.primary_email)
                if email_result.success:
                    primary_email = email_result.value
            
            # Create primary phone if available
            primary_phone = None
            if db_user.primary_phone:
                phone_result = PhoneNumber.create(db_user.primary_phone)
                if phone_result.success:
                    primary_phone = phone_result.value
            
            user = User(
                user_id=UserId(str(db_user.id)),
                clerk_user_id=db_user.clerk_user_id,
                username=db_user.username,
                first_name=db_user.first_name,
                last_name=db_user.last_name,
                image_url=db_user.image_url,
                email_addresses=email_addresses,
                phone_numbers=phone_numbers,
                primary_email=primary_email,
                primary_phone=primary_phone,
                email_verified=db_user.email_verified,
                phone_verified=db_user.phone_verified,
                two_factor_enabled=db_user.two_factor_enabled,
                role=db_user.role,
                status=db_user.status,
                user_metadata=db_user.user_metadata or {},
                created_at=db_user.created_at,
                last_sign_in_at=db_user.last_sign_in_at,
                last_active_at=db_user.last_active_at,
                is_deleted=db_user.is_deleted,
                deleted_at=db_user.deleted_at
            )
            
            return Result.ok(user)
            
        except Exception as e:
            return Result.fail(f"Failed to map user from database: {str(e)}")
    
    @staticmethod
    def to_database(user: User) -> Dict[str, Any]:
        """Convert domain entity to database model data."""
        # Convert email addresses to database format
        email_addresses = []
        for email in user.email_addresses:
            email_addresses.append({
                'email_address': email.value,
                'verified': True  # Domain entity stores verified emails
            })
        
        # Convert phone numbers to database format
        phone_numbers = []
        for phone in user.phone_numbers:
            phone_numbers.append({
                'phone_number': phone.value,
                'verified': True  # Domain entity stores verified phones
            })
        
        return {
            'id': UUID(user.user_id.value),
            'clerk_user_id': user.clerk_user_id,
            'username': user.username,
            'first_name': user.first_name,
            'last_name': user.last_name,
            'image_url': user.image_url,
            'email_addresses': email_addresses,
            'phone_numbers': phone_numbers,
            'primary_email': user.primary_email.value if user.primary_email else None,
            'primary_phone': user.primary_phone.value if user.primary_phone else None,
            'email_verified': user.email_verified,
            'phone_verified': user.phone_verified,
            'two_factor_enabled': user.two_factor_enabled,
            'role': user.role,
            'status': user.status,
            'user_metadata': user.user_metadata,
            'created_at': user.created_at,
            'updated_at': user.updated_at,
            'last_sign_in_at': user.last_sign_in_at,
            'last_active_at': user.last_active_at,
            'is_deleted': user.is_deleted,
            'deleted_at': user.deleted_at
        }


class JobMapper(EntityMapper):
    """Mapper for Job domain entity and JobModel database model."""
    
    @staticmethod
    def to_domain(db_job: JobModel) -> Result[Job]:
        """Convert database model to domain entity."""
        try:
            # Map job configuration
            config_result = JobConfiguration.create(db_job.configuration or {})
            if not config_result.success:
                return Result.fail(f"Invalid job configuration: {config_result.error}")
            
            # Map job progress
            progress = JobProgress(
                percentage=float(db_job.progress_percentage or 0),
                current_stage=db_job.current_stage,
                stages_completed=db_job.stages_completed or [],
                estimated_completion=db_job.estimated_completion,
                processing_time_seconds=float(db_job.processing_time_seconds or 0)
            )
            
            job = Job(
                job_id=JobId(str(db_job.id)),
                user_id=UserId(str(db_job.user_id)),
                job_type=JobType(db_job.job_type),
                priority=JobPriority(db_job.priority),
                configuration=config_result.value,
                status=JobStatus(db_job.status),
                progress=progress,
                error_info=db_job.error_info,
                metrics=db_job.metrics or {},
                result_url=db_job.result_url,
                created_at=db_job.created_at,
                started_at=db_job.started_at,
                completed_at=db_job.completed_at,
                batch_id=str(db_job.batch_id) if db_job.batch_id else None,
                parent_job_id=JobId(str(db_job.parent_job_id)) if db_job.parent_job_id else None,
                is_deleted=db_job.is_deleted,
                deleted_at=db_job.deleted_at
            )
            
            return Result.ok(job)
            
        except Exception as e:
            return Result.fail(f"Failed to map job from database: {str(e)}")
    
    @staticmethod
    def to_database(job: Job) -> Dict[str, Any]:
        """Convert domain entity to database model data."""
        return {
            'id': UUID(job.job_id.value),
            'user_id': UUID(job.user_id.value),
            'job_type': job.job_type.value,
            'priority': job.priority.value,
            'configuration': job.configuration if isinstance(job.configuration, dict) else job.configuration.to_dict(),
            'status': job.status.value,
            'progress_percentage': job.progress.percentage,
            'current_stage': job.progress.current_stage,
            'stages_completed': job.progress.stages_completed,
            'estimated_completion': job.progress.estimated_completion,
            'processing_time_seconds': job.progress.processing_time_seconds,
            'error_info': job.error_info,
            'metrics': job.metrics,
            'result_url': job.result_url,
            'created_at': job.created_at,
            'updated_at': job.updated_at,
            'started_at': job.started_at,
            'completed_at': job.completed_at,
            'batch_id': UUID(job.batch_id) if job.batch_id else None,
            'parent_job_id': UUID(job.parent_job_id.value) if job.parent_job_id else None,
            'is_deleted': job.is_deleted,
            'deleted_at': job.deleted_at
        }


class FileMapper(EntityMapper):
    """Mapper for File domain entity and FileModel database model."""
    
    @staticmethod
    def to_domain(db_file: FileModel) -> Result[File]:
        """Convert database model to domain entity."""
        try:
            # Map file size
            size_result = FileSize.create(db_file.file_size)
            if not size_result.success:
                return Result.fail(f"Invalid file size: {size_result.error}")
            
            # Map file type
            type_result = FileType.create(db_file.file_type)
            if not type_result.success:
                return Result.fail(f"Invalid file type: {type_result.error}")
            
            # Map file path
            path_result = FilePath.create(db_file.s3_key)
            if not path_result.success:
                return Result.fail(f"Invalid file path: {path_result.error}")
            
            # Map S3 location
            s3_location = S3Location(
                bucket=db_file.s3_bucket,
                key=db_file.s3_key,
                version_id=db_file.s3_version_id
            )
            
            file_entity = File(
                file_id=FileId(str(db_file.id)),
                user_id=UserId(str(db_file.user_id)),
                job_id=JobId(str(db_file.job_id)) if db_file.job_id else None,
                file_type=type_result.value,
                original_filename=db_file.original_filename,
                stored_filename=db_file.stored_filename,
                s3_location=s3_location,
                file_size=size_result.value,
                content_type=db_file.content_type,
                checksum=db_file.checksum,
                file_metadata=db_file.file_metadata or {},
                description=db_file.description,
                tags=db_file.tags or [],
                created_at=db_file.created_at,
                last_accessed_at=db_file.last_accessed_at,
                is_deleted=db_file.is_deleted,
                deleted_at=db_file.deleted_at
            )
            
            return Result.ok(file_entity)
            
        except Exception as e:
            return Result.fail(f"Failed to map file from database: {str(e)}")
    
    @staticmethod
    def to_database(file_entity: File) -> Dict[str, Any]:
        """Convert domain entity to database model data."""
        return {
            'id': UUID(file_entity.file_id.value),
            'user_id': UUID(file_entity.user_id.value),
            'job_id': UUID(file_entity.job_id.value) if file_entity.job_id else None,
            'file_type': file_entity.file_type.value,
            'original_filename': file_entity.original_filename,
            'stored_filename': file_entity.stored_filename,
            's3_bucket': file_entity.s3_location.bucket,
            's3_key': file_entity.s3_location.key,
            's3_version_id': file_entity.s3_location.version_id,
            'file_size': file_entity.file_size.bytes,
            'content_type': file_entity.content_type,
            'checksum': file_entity.checksum,
            'file_metadata': file_entity.file_metadata,
            'description': file_entity.description,
            'tags': file_entity.tags,
            'created_at': file_entity.created_at,
            'updated_at': file_entity.updated_at,
            'last_accessed_at': file_entity.last_accessed_at,
            'is_deleted': file_entity.is_deleted,
            'deleted_at': file_entity.deleted_at
        }


class VideoMapper(EntityMapper):
    """
    Mapper for Video domain entity.
    
    Note: Videos don't have a direct database table yet but are stored
    as job configurations. This mapper handles the video data within jobs.
    """
    
    @staticmethod
    def extract_video_from_job(job: Job) -> Result[Optional[Video]]:
        """Extract video information from a job configuration."""
        try:
            if job.job_type.value != 'video_generation':
                return Result.ok(None)
            
            config_dict = job.configuration if isinstance(job.configuration, dict) else job.configuration.to_dict()
            
            # Extract video information from job configuration
            if 'video_config' not in config_dict:
                return Result.ok(None)
            
            video_config = config_dict['video_config']
            
            # Create value objects
            title_result = VideoTitle.create(video_config.get('title', ''))
            if not title_result.success:
                return Result.fail(f"Invalid video title: {title_result.error}")
            
            topic_result = VideoTopic.create(video_config.get('topic', ''))
            if not topic_result.success:
                return Result.fail(f"Invalid video topic: {topic_result.error}")
            
            context_result = VideoContext.create(video_config.get('context', ''))
            if not context_result.success:
                return Result.fail(f"Invalid video context: {context_result.error}")
            
            # Create processing config
            processing_config = VideoProcessingConfig(
                quality=VideoQuality(video_config.get('quality', 'high')),
                format=VideoFormat(video_config.get('format', 'mp4')),
                resolution=VideoResolution(video_config.get('resolution', '1080p')),
                include_subtitles=video_config.get('include_subtitles', False),
                include_thumbnail=video_config.get('include_thumbnail', True)
            )
            
            # Map job status to video status
            video_status_map = {
                'queued': VideoStatus.CREATED,
                'processing': VideoStatus.PROCESSING,
                'completed': VideoStatus.COMPLETED,
                'failed': VideoStatus.FAILED,
                'cancelled': VideoStatus.FAILED
            }
            
            video_status = video_status_map.get(job.status.value, VideoStatus.CREATED)
            
            # Create description if available
            description = None
            if video_config.get('description'):
                desc_result = VideoDescription.create(video_config['description'])
                if desc_result.success:
                    description = desc_result.value
            
            video = Video(
                video_id=VideoId(job.job_id.value),  # Use job ID as video ID
                user_id=job.user_id,
                title=title_result.value,
                topic=topic_result.value,
                context=context_result.value,
                processing_config=processing_config,
                description=description,
                status=video_status,
                result_url=job.result_url,
                tags=video_config.get('tags', []),
                metadata=video_config.get('metadata', {}),
                created_at=job.created_at,
                processing_started_at=job.started_at,
                processing_completed_at=job.completed_at,
                last_error=job.error_info.get('message') if job.error_info else None
            )
            
            return Result.ok(video)
            
        except Exception as e:
            return Result.fail(f"Failed to extract video from job: {str(e)}")
    
    @staticmethod
    def video_to_job_config(video: Video) -> Dict[str, Any]:
        """Convert video domain entity to job configuration."""
        return {
            'video_config': {
                'title': video.title.value,
                'description': video.description.value if video.description else '',
                'topic': video.topic.value,
                'context': video.context.value,
                'quality': video.processing_config.quality.value,
                'format': video.processing_config.format.value,
                'resolution': video.processing_config.resolution.value,
                'include_subtitles': video.processing_config.include_subtitles,
                'include_thumbnail': video.processing_config.include_thumbnail,
                'tags': video.tags,
                'metadata': video.metadata
            }
        }
