"""
S3 File Organization and Management Utilities.

This module provides utilities for organizing files in S3 buckets,
managing file hierarchies, and implementing file lifecycle policies.
"""

import logging
import asyncio
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime, timedelta
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from enum import Enum

import boto3
from botocore.exceptions import ClientError

from src.config.aws_config import AWSConfig

logger = logging.getLogger(__name__)


class FileOrganizationLevel(str, Enum):
    """File organization hierarchy levels."""
    USER = "user"
    JOB = "job"
    TYPE = "type"
    SCENE = "scene"
    DATE = "date"


@dataclass
class S3ObjectInfo:
    """S3 object information."""
    bucket: str
    key: str
    size: int
    last_modified: datetime
    etag: str
    storage_class: str
    metadata: Dict[str, str]


@dataclass
class OrganizationRule:
    """File organization rule."""
    name: str
    pattern: str
    target_structure: str
    conditions: Dict[str, Any]
    enabled: bool = True


class S3FileOrganizer:
    """Manages S3 file organization and structure."""
    
    def __init__(self, aws_config: AWSConfig):
        """
        Initialize S3 file organizer.
        
        Args:
            aws_config: AWS configuration object
        """
        self.config = aws_config
        
        # Create thread-safe session
        self.session = boto3.Session(
            aws_access_key_id=aws_config.access_key_id,
            aws_secret_access_key=aws_config.secret_access_key,
            region_name=aws_config.region
        )
        self.s3_client = self.session.client('s3')
        
        # Default organization rules
        self.organization_rules = [
            OrganizationRule(
                name="video_by_job_and_scene",
                pattern="users/{user_id}/jobs/{job_id}/videos/scene_{scene_number:03d}/",
                target_structure="hierarchical",
                conditions={"file_type": "video", "has_job_id": True, "has_scene_number": True}
            ),
            OrganizationRule(
                name="code_by_job",
                pattern="users/{user_id}/jobs/{job_id}/code/",
                target_structure="hierarchical",
                conditions={"file_type": "code", "has_job_id": True}
            ),
            OrganizationRule(
                name="user_files_by_type",
                pattern="users/{user_id}/{file_type}/",
                target_structure="flat",
                conditions={"has_job_id": False}
            )
        ]
        
        logger.info("Initialized S3FileOrganizer")
    
    def generate_organized_key(
        self,
        user_id: str,
        filename: str,
        file_type: str,
        job_id: Optional[str] = None,
        scene_number: Optional[int] = None,
        custom_path: Optional[str] = None
    ) -> str:
        """
        Generate organized S3 key based on organization rules.
        
        Args:
            user_id: User identifier
            filename: Original filename
            file_type: Type of file
            job_id: Optional job identifier
            scene_number: Optional scene number
            custom_path: Optional custom path override
            
        Returns:
            str: Organized S3 key
        """
        if custom_path:
            return f"{custom_path.rstrip('/')}/{filename}"
        
        # Find matching organization rule
        context = {
            "file_type": file_type,
            "has_job_id": job_id is not None,
            "has_scene_number": scene_number is not None
        }
        
        matching_rule = None
        for rule in self.organization_rules:
            if rule.enabled and self._matches_conditions(context, rule.conditions):
                matching_rule = rule
                break
        
        if not matching_rule:
            # Default organization
            timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
            return f"users/{user_id}/{file_type}/{timestamp}_{filename}"
        
        # Apply organization rule
        try:
            if scene_number is not None:
                path = matching_rule.pattern.format(
                    user_id=user_id,
                    job_id=job_id or "unknown",
                    file_type=file_type,
                    scene_number=scene_number
                )
            else:
                path = matching_rule.pattern.format(
                    user_id=user_id,
                    job_id=job_id or "unknown",
                    file_type=file_type
                )
            
            # Add timestamp to filename to ensure uniqueness
            timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
            return f"{path.rstrip('/')}/{timestamp}_{filename}"
            
        except KeyError as e:
            logger.warning(f"Failed to apply organization rule {matching_rule.name}: {e}")
            # Fallback to default
            timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
            return f"users/{user_id}/{file_type}/{timestamp}_{filename}"
    
    def _matches_conditions(self, context: Dict[str, Any], conditions: Dict[str, Any]) -> bool:
        """
        Check if context matches rule conditions.
        
        Args:
            context: Current context
            conditions: Rule conditions
            
        Returns:
            bool: True if conditions match
        """
        for key, expected_value in conditions.items():
            if context.get(key) != expected_value:
                return False
        return True
    
    async def analyze_bucket_organization(self, bucket: str) -> Dict[str, Any]:
        """
        Analyze current organization of files in a bucket.
        
        Args:
            bucket: S3 bucket name
            
        Returns:
            Dict with organization analysis
        """
        try:
            analysis = {
                'total_objects': 0,
                'organization_levels': {},
                'file_types': {},
                'users': set(),
                'jobs': set(),
                'size_by_level': {},
                'recommendations': []
            }
            
            # List all objects in bucket
            objects = await self._list_all_objects(bucket)
            analysis['total_objects'] = len(objects)
            
            for obj in objects:
                key_parts = obj.key.split('/')
                
                # Analyze organization levels
                level_count = len(key_parts) - 1  # Exclude filename
                analysis['organization_levels'][level_count] = analysis['organization_levels'].get(level_count, 0) + 1
                
                # Extract information from key structure
                if len(key_parts) >= 2 and key_parts[0] == 'users':
                    user_id = key_parts[1]
                    analysis['users'].add(user_id)
                    
                    if len(key_parts) >= 4 and key_parts[2] == 'jobs':
                        job_id = key_parts[3]
                        analysis['jobs'].add(job_id)
                        
                        if len(key_parts) >= 5:
                            file_type = key_parts[4]
                            analysis['file_types'][file_type] = analysis['file_types'].get(file_type, 0) + 1
                    elif len(key_parts) >= 3:
                        file_type = key_parts[2]
                        analysis['file_types'][file_type] = analysis['file_types'].get(file_type, 0) + 1
                
                # Size analysis by level
                analysis['size_by_level'][level_count] = analysis['size_by_level'].get(level_count, 0) + obj.size
            
            # Convert sets to counts
            analysis['users'] = len(analysis['users'])
            analysis['jobs'] = len(analysis['jobs'])
            
            # Generate recommendations
            analysis['recommendations'] = self._generate_organization_recommendations(analysis)
            
            return analysis
            
        except Exception as e:
            logger.error(f"Failed to analyze bucket organization: {e}")
            return {'error': str(e)}
    
    def _generate_organization_recommendations(self, analysis: Dict[str, Any]) -> List[str]:
        """
        Generate organization recommendations based on analysis.
        
        Args:
            analysis: Bucket analysis results
            
        Returns:
            List of recommendation strings
        """
        recommendations = []
        
        # Check for deep nesting
        max_levels = max(analysis['organization_levels'].keys()) if analysis['organization_levels'] else 0
        if max_levels > 6:
            recommendations.append(f"Consider reducing nesting depth (current max: {max_levels} levels)")
        
        # Check for flat structure
        flat_files = analysis['organization_levels'].get(0, 0)
        if flat_files > analysis['total_objects'] * 0.1:
            recommendations.append(f"Consider organizing {flat_files} files in root directory")
        
        # Check file type distribution
        if len(analysis['file_types']) > 10:
            recommendations.append("Consider consolidating file types or improving categorization")
        
        # Check for large directories
        avg_files_per_level = analysis['total_objects'] / len(analysis['organization_levels']) if analysis['organization_levels'] else 0
        if avg_files_per_level > 1000:
            recommendations.append("Consider adding date-based sub-directories for large collections")
        
        return recommendations
    
    async def reorganize_files(
        self,
        bucket: str,
        dry_run: bool = True,
        batch_size: int = 100
    ) -> Dict[str, Any]:
        """
        Reorganize files in bucket according to organization rules.
        
        Args:
            bucket: S3 bucket name
            dry_run: If True, only simulate reorganization
            batch_size: Number of files to process in each batch
            
        Returns:
            Dict with reorganization results
        """
        try:
            results = {
                'processed': 0,
                'moved': 0,
                'errors': 0,
                'operations': [],
                'dry_run': dry_run
            }
            
            # Get all objects that need reorganization
            objects = await self._list_all_objects(bucket)
            
            # Process in batches
            for i in range(0, len(objects), batch_size):
                batch = objects[i:i + batch_size]
                batch_results = await self._reorganize_batch(bucket, batch, dry_run)
                
                results['processed'] += batch_results['processed']
                results['moved'] += batch_results['moved']
                results['errors'] += batch_results['errors']
                results['operations'].extend(batch_results['operations'])
            
            logger.info(f"Reorganization {'simulation' if dry_run else 'completed'}: "
                       f"{results['moved']} files moved, {results['errors']} errors")
            
            return results
            
        except Exception as e:
            logger.error(f"Failed to reorganize files: {e}")
            return {'error': str(e)}
    
    async def _reorganize_batch(
        self,
        bucket: str,
        objects: List[S3ObjectInfo],
        dry_run: bool
    ) -> Dict[str, Any]:
        """
        Reorganize a batch of files.
        
        Args:
            bucket: S3 bucket name
            objects: List of objects to reorganize
            dry_run: If True, only simulate reorganization
            
        Returns:
            Dict with batch results
        """
        results = {
            'processed': 0,
            'moved': 0,
            'errors': 0,
            'operations': []
        }
        
        for obj in objects:
            try:
                results['processed'] += 1
                
                # Parse current key to extract information
                key_info = self._parse_s3_key(obj.key)
                
                if not key_info:
                    continue
                
                # Generate new organized key
                new_key = self.generate_organized_key(
                    user_id=key_info['user_id'],
                    filename=key_info['filename'],
                    file_type=key_info['file_type'],
                    job_id=key_info.get('job_id'),
                    scene_number=key_info.get('scene_number')
                )
                
                # Check if reorganization is needed
                if new_key == obj.key:
                    continue
                
                operation = {
                    'action': 'move',
                    'from': obj.key,
                    'to': new_key,
                    'size': obj.size
                }
                
                if not dry_run:
                    # Perform the move operation
                    success = await self._move_s3_object(bucket, obj.key, new_key)
                    operation['success'] = success
                    
                    if success:
                        results['moved'] += 1
                    else:
                        results['errors'] += 1
                else:
                    operation['success'] = True  # Simulated success
                    results['moved'] += 1
                
                results['operations'].append(operation)
                
            except Exception as e:
                logger.error(f"Failed to reorganize object {obj.key}: {e}")
                results['errors'] += 1
                results['operations'].append({
                    'action': 'move',
                    'from': obj.key,
                    'to': 'error',
                    'error': str(e),
                    'success': False
                })
        
        return results
    
    def _parse_s3_key(self, key: str) -> Optional[Dict[str, Any]]:
        """
        Parse S3 key to extract organization information.
        
        Args:
            key: S3 key to parse
            
        Returns:
            Dict with parsed information or None if parsing fails
        """
        try:
            parts = key.split('/')
            filename = parts[-1]
            
            # Basic structure: users/{user_id}/...
            if len(parts) < 3 or parts[0] != 'users':
                return None
            
            info = {
                'filename': filename,
                'user_id': parts[1]
            }
            
            # Check for job structure: users/{user_id}/jobs/{job_id}/...
            if len(parts) >= 5 and parts[2] == 'jobs':
                info['job_id'] = parts[3]
                info['file_type'] = parts[4]
                
                # Check for scene structure
                if len(parts) >= 6 and parts[5].startswith('scene_'):
                    try:
                        scene_str = parts[5].replace('scene_', '')
                        info['scene_number'] = int(scene_str)
                    except ValueError:
                        pass
            elif len(parts) >= 3:
                # Direct file type structure: users/{user_id}/{file_type}/...
                info['file_type'] = parts[2]
            
            return info
            
        except Exception as e:
            logger.warning(f"Failed to parse S3 key {key}: {e}")
            return None
    
    async def _move_s3_object(self, bucket: str, source_key: str, dest_key: str) -> bool:
        """
        Move S3 object from source to destination key.
        
        Args:
            bucket: S3 bucket name
            source_key: Source object key
            dest_key: Destination object key
            
        Returns:
            bool: True if move was successful
        """
        try:
            # Copy object to new location
            copy_source = {'Bucket': bucket, 'Key': source_key}
            
            loop = asyncio.get_event_loop()
            with ThreadPoolExecutor() as executor:
                await loop.run_in_executor(
                    executor,
                    self.s3_client.copy_object,
                    {
                        'CopySource': copy_source,
                        'Bucket': bucket,
                        'Key': dest_key
                    }
                )
                
                # Delete original object
                await loop.run_in_executor(
                    executor,
                    self.s3_client.delete_object,
                    {'Bucket': bucket, 'Key': source_key}
                )
            
            logger.debug(f"Successfully moved {source_key} to {dest_key}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to move S3 object from {source_key} to {dest_key}: {e}")
            return False
    
    async def _list_all_objects(self, bucket: str, prefix: str = "") -> List[S3ObjectInfo]:
        """
        List all objects in bucket with given prefix.
        
        Args:
            bucket: S3 bucket name
            prefix: Key prefix filter
            
        Returns:
            List of S3ObjectInfo objects
        """
        objects = []
        continuation_token = None
        
        loop = asyncio.get_event_loop()
        with ThreadPoolExecutor() as executor:
            while True:
                try:
                    params = {
                        'Bucket': bucket,
                        'Prefix': prefix,
                        'MaxKeys': 1000
                    }
                    
                    if continuation_token:
                        params['ContinuationToken'] = continuation_token
                    
                    response = await loop.run_in_executor(
                        executor,
                        lambda: self.s3_client.list_objects_v2(**params)
                    )
                    
                    for obj in response.get('Contents', []):
                        objects.append(S3ObjectInfo(
                            bucket=bucket,
                            key=obj['Key'],
                            size=obj['Size'],
                            last_modified=obj['LastModified'],
                            etag=obj['ETag'].strip('"'),
                            storage_class=obj.get('StorageClass', 'STANDARD'),
                            metadata={}  # Would need separate head_object call for metadata
                        ))
                    
                    if not response.get('IsTruncated', False):
                        break
                    
                    continuation_token = response.get('NextContinuationToken')
                    
                except ClientError as e:
                    logger.error(f"Failed to list objects in bucket {bucket}: {e}")
                    break
        
        return objects
    
    async def implement_lifecycle_policies(self, bucket: str) -> Dict[str, Any]:
        """
        Implement lifecycle policies for file management.
        
        Args:
            bucket: S3 bucket name
            
        Returns:
            Dict with lifecycle policy results
        """
        try:
            # Define lifecycle rules
            lifecycle_rules = [
                {
                    'ID': 'temp-files-cleanup',
                    'Status': 'Enabled',
                    'Filter': {'Prefix': 'temp/'},
                    'Expiration': {'Days': 7}
                },
                {
                    'ID': 'old-versions-cleanup',
                    'Status': 'Enabled',
                    'Filter': {'Prefix': 'users/'},
                    'NoncurrentVersionExpiration': {'NoncurrentDays': 30}
                },
                {
                    'ID': 'multipart-cleanup',
                    'Status': 'Enabled',
                    'Filter': {},
                    'AbortIncompleteMultipartUpload': {'DaysAfterInitiation': 1}
                },
                {
                    'ID': 'archive-old-files',
                    'Status': 'Enabled',
                    'Filter': {'Prefix': 'users/'},
                    'Transitions': [
                        {
                            'Days': 90,
                            'StorageClass': 'STANDARD_IA'
                        },
                        {
                            'Days': 365,
                            'StorageClass': 'GLACIER'
                        }
                    ]
                }
            ]
            
            # Apply lifecycle configuration
            loop = asyncio.get_event_loop()
            with ThreadPoolExecutor() as executor:
                await loop.run_in_executor(
                    executor,
                    self.s3_client.put_bucket_lifecycle_configuration,
                    {
                        'Bucket': bucket,
                        'LifecycleConfiguration': {'Rules': lifecycle_rules}
                    }
                )
            
            logger.info(f"Successfully applied lifecycle policies to bucket: {bucket}")
            
            return {
                'success': True,
                'rules_applied': len(lifecycle_rules),
                'rules': [rule['ID'] for rule in lifecycle_rules]
            }
            
        except Exception as e:
            logger.error(f"Failed to implement lifecycle policies: {e}")
            return {'success': False, 'error': str(e)}


class S3StorageOptimizer:
    """Optimizes S3 storage costs and performance."""
    
    def __init__(self, aws_config: AWSConfig):
        """
        Initialize S3 storage optimizer.
        
        Args:
            aws_config: AWS configuration object
        """
        self.config = aws_config
        
        # Create thread-safe session
        self.session = boto3.Session(
            aws_access_key_id=aws_config.access_key_id,
            aws_secret_access_key=aws_config.secret_access_key,
            region_name=aws_config.region
        )
        self.s3_client = self.session.client('s3')
        
        logger.info("Initialized S3StorageOptimizer")
    
    async def analyze_storage_costs(self, bucket: str) -> Dict[str, Any]:
        """
        Analyze storage costs and optimization opportunities.
        
        Args:
            bucket: S3 bucket name
            
        Returns:
            Dict with cost analysis
        """
        try:
            analysis = {
                'total_objects': 0,
                'total_size': 0,
                'storage_classes': {},
                'size_distribution': {},
                'age_distribution': {},
                'optimization_opportunities': []
            }
            
            # Get bucket metrics
            organizer = S3FileOrganizer(self.config)
            objects = await organizer._list_all_objects(bucket)
            
            analysis['total_objects'] = len(objects)
            
            # Analyze objects
            now = datetime.utcnow()
            
            for obj in objects:
                analysis['total_size'] += obj.size
                
                # Storage class distribution
                storage_class = obj.storage_class
                analysis['storage_classes'][storage_class] = analysis['storage_classes'].get(storage_class, 0) + 1
                
                # Size distribution
                size_category = self._categorize_size(obj.size)
                analysis['size_distribution'][size_category] = analysis['size_distribution'].get(size_category, 0) + 1
                
                # Age distribution
                age_days = (now - obj.last_modified).days
                age_category = self._categorize_age(age_days)
                analysis['age_distribution'][age_category] = analysis['age_distribution'].get(age_category, 0) + 1
            
            # Generate optimization opportunities
            analysis['optimization_opportunities'] = self._identify_optimization_opportunities(analysis, objects)
            
            return analysis
            
        except Exception as e:
            logger.error(f"Failed to analyze storage costs: {e}")
            return {'error': str(e)}
    
    def _categorize_size(self, size: int) -> str:
        """Categorize file size."""
        if size < 1024:  # < 1KB
            return 'tiny'
        elif size < 1024 * 1024:  # < 1MB
            return 'small'
        elif size < 10 * 1024 * 1024:  # < 10MB
            return 'medium'
        elif size < 100 * 1024 * 1024:  # < 100MB
            return 'large'
        else:
            return 'huge'
    
    def _categorize_age(self, age_days: int) -> str:
        """Categorize file age."""
        if age_days < 7:
            return 'recent'
        elif age_days < 30:
            return 'current'
        elif age_days < 90:
            return 'aging'
        elif age_days < 365:
            return 'old'
        else:
            return 'ancient'
    
    def _identify_optimization_opportunities(
        self,
        analysis: Dict[str, Any],
        objects: List[S3ObjectInfo]
    ) -> List[str]:
        """Identify storage optimization opportunities."""
        opportunities = []
        
        # Check for files that could be moved to cheaper storage classes
        standard_objects = analysis['storage_classes'].get('STANDARD', 0)
        old_objects = analysis['age_distribution'].get('old', 0) + analysis['age_distribution'].get('ancient', 0)
        
        if old_objects > standard_objects * 0.2:
            opportunities.append(f"Consider moving {old_objects} old files to Standard-IA or Glacier")
        
        # Check for small files that could be consolidated
        tiny_objects = analysis['size_distribution'].get('tiny', 0)
        if tiny_objects > analysis['total_objects'] * 0.3:
            opportunities.append(f"Consider consolidating {tiny_objects} tiny files to reduce request costs")
        
        # Check for duplicate files (by size and potential naming patterns)
        size_groups = {}
        for obj in objects:
            size_groups.setdefault(obj.size, []).append(obj)
        
        potential_duplicates = sum(1 for group in size_groups.values() if len(group) > 1)
        if potential_duplicates > 0:
            opportunities.append(f"Found {potential_duplicates} potential duplicate files to review")
        
        return opportunities