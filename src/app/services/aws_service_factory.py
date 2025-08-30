"""
AWS Service Factory for creating and managing AWS-integrated services.

This factory provides centralized creation and configuration of AWS services
including video, file, job, and user services with proper dependency injection,
health monitoring, and CloudWatch integration.
"""

import logging
import asyncio
from typing import Optional, Dict, Any
from datetime import datetime, timedelta
import boto3
from botocore.exceptions import ClientError
import redis.asyncio as redis

from .aws_video_service import AWSVideoService
from .aws_s3_file_service import AWSS3FileService
from .aws_job_service import AWSJobService
from .aws_user_service import AWSUserService
from ..database.connection import RDSConnectionManager
from src.config.aws_config import AWSConfig, AWSConfigManager

logger = logging.getLogger(__name__)


class AWSServiceFactory:
    """
    Factory for creating AWS-integrated services with proper configuration and dependencies.
    
    Manages service lifecycle, health checks, and provides centralized access
    to all AWS-integrated application services.
    """
    
    def __init__(self, config: Optional[AWSConfig] = None):
        """
        Initialize the AWS service factory.
        
        Args:
            config: AWS configuration (will be loaded from environment if not provided)
        """
        self.config = config or AWSConfigManager.load_config()
        self.rds_manager: Optional[RDSConnectionManager] = None
        self.redis_client: Optional[redis.Redis] = None
        self.cloudwatch_client: Optional[Any] = None
        self._services: Dict[str, Any] = {}
        self._initialized = False
        self._monitoring_enabled = False
        
        logger.info(f"Initialized AWS Service Factory for environment: {self.config.environment}")
    
    async def initialize(self) -> bool:
        """
        Initialize all AWS services and dependencies.
        
        Returns:
            bool: True if initialization successful, False otherwise
        """
        try:
            logger.info("Initializing AWS Service Factory...")
            
            # Validate AWS configuration
            AWSConfigManager.validate_config(self.config)
            
            # Initialize RDS connection manager
            await self._initialize_rds_manager()
            
            # Initialize Redis client (optional)
            await self._initialize_redis_client()
            
            # Initialize CloudWatch client for monitoring
            await self._initialize_cloudwatch_client()
            
            # Test AWS connectivity
            connectivity_results = await AWSConfigManager.test_aws_connectivity(self.config)
            
            # Check if critical services are available
            if not connectivity_results['s3']['connected']:
                raise ConnectionError("S3 connectivity failed")
            
            if not connectivity_results['rds_postgres']['connected']:
                raise ConnectionError("RDS PostgreSQL connectivity failed")
            
            self._initialized = True
            logger.info("AWS Service Factory initialized successfully")
            return True
            
        except Exception as e:
            logger.error(f"Failed to initialize AWS Service Factory: {e}")
            await self.close()
            return False
    
    async def _initialize_rds_manager(self):
        """Initialize RDS connection manager."""
        try:
            from ..database.connection import ConnectionConfig
            
            # Create connection configuration
            connection_config = ConnectionConfig(
                host=self.config.rds_endpoint.split(':')[0],
                port=int(self.config.rds_endpoint.split(':')[1]) if ':' in self.config.rds_endpoint else 5432,
                database=self.config.rds_database,
                username=self.config.rds_username,
                password=self.config.rds_password,
                min_connections=5,
                max_connections=20,
                connection_timeout=30
            )
            
            self.rds_manager = RDSConnectionManager(connection_config)
            
            # Initialize the connection manager
            success = await self.rds_manager.initialize()
            if not success:
                raise ConnectionError("Failed to initialize RDS connection manager")
            
            logger.info("RDS connection manager initialized successfully")
            
        except Exception as e:
            logger.error(f"Failed to initialize RDS manager: {e}")
            raise
    
    async def _initialize_redis_client(self):
        """Initialize Redis client if configured."""
        try:
            import os
            redis_url = os.getenv('REDIS_URL')
            
            if redis_url:
                self.redis_client = redis.from_url(redis_url)
                
                # Test Redis connectivity
                await self.redis_client.ping()
                logger.info("Redis client initialized successfully")
            else:
                logger.info("Redis URL not configured, skipping Redis initialization")
                
        except Exception as e:
            logger.warning(f"Failed to initialize Redis client: {e}")
            # Redis is optional, so we don't raise an exception
            self.redis_client = None
    
    async def _initialize_cloudwatch_client(self):
        """Initialize CloudWatch client for monitoring."""
        try:
            session = boto3.Session(
                aws_access_key_id=self.config.access_key_id,
                aws_secret_access_key=self.config.secret_access_key,
                region_name=self.config.region
            )
            self.cloudwatch_client = session.client('cloudwatch')
            
            # Test CloudWatch connectivity
            await asyncio.get_event_loop().run_in_executor(
                None, lambda: self.cloudwatch_client.list_metrics(MaxRecords=1)
            )
            
            self._monitoring_enabled = True
            logger.info("CloudWatch client initialized successfully")
            
        except Exception as e:
            logger.warning(f"Failed to initialize CloudWatch client: {e}")
            # CloudWatch is optional for basic functionality
            self.cloudwatch_client = None
            self._monitoring_enabled = False
    
    def create_video_service(self) -> AWSVideoService:
        """
        Create AWS S3-based video service.
        
        Returns:
            AWSVideoService: Configured video service instance
            
        Raises:
            RuntimeError: If factory not initialized or dependencies missing
        """
        if not self._initialized:
            raise RuntimeError("Service factory not initialized. Call initialize() first.")
        
        if not self.rds_manager:
            raise RuntimeError("RDS manager not available")
        
        service_key = 'video_service'
        
        if service_key not in self._services:
            self._services[service_key] = AWSVideoService(
                aws_config=self.config,
                db_manager=self.rds_manager
            )
            logger.info("Created AWS Video Service")
        
        return self._services[service_key]
    
    def create_file_service(self) -> AWSS3FileService:
        """
        Create AWS S3-based file service.
        
        Returns:
            AWSS3FileService: Configured file service instance
            
        Raises:
            RuntimeError: If factory not initialized
        """
        if not self._initialized:
            raise RuntimeError("Service factory not initialized. Call initialize() first.")
        
        service_key = 'file_service'
        
        if service_key not in self._services:
            self._services[service_key] = AWSS3FileService(
                aws_config=self.config
            )
            logger.info("Created AWS S3 File Service")
        
        return self._services[service_key]
    
    def create_job_service(self) -> AWSJobService:
        """
        Create RDS-based job service.
        
        Returns:
            AWSJobService: Configured job service instance
            
        Raises:
            RuntimeError: If factory not initialized or dependencies missing
        """
        if not self._initialized:
            raise RuntimeError("Service factory not initialized. Call initialize() first.")
        
        if not self.rds_manager:
            raise RuntimeError("RDS manager not available")
        
        service_key = 'job_service'
        
        if service_key not in self._services:
            self._services[service_key] = AWSJobService(
                db_manager=self.rds_manager,
                redis_client=self.redis_client
            )
            logger.info("Created AWS Job Service")
        
        return self._services[service_key]
    
    def create_user_service(self) -> AWSUserService:
        """
        Create RDS-based user service.
        
        Returns:
            AWSUserService: Configured user service instance
            
        Raises:
            RuntimeError: If factory not initialized or dependencies missing
        """
        if not self._initialized:
            raise RuntimeError("Service factory not initialized. Call initialize() first.")
        
        if not self.rds_manager:
            raise RuntimeError("RDS manager not available")
        
        service_key = 'user_service'
        
        if service_key not in self._services:
            self._services[service_key] = AWSUserService(
                db_manager=self.rds_manager,
                redis_client=self.redis_client
            )
            logger.info("Created AWS User Service")
        
        return self._services[service_key]
    
    async def health_check(self) -> Dict[str, Any]:
        """
        Check health of all AWS services and dependencies.
        
        Returns:
            Dict containing comprehensive health status
        """
        health_status = {
            'factory': 'AWSServiceFactory',
            'initialized': self._initialized,
            'environment': self.config.environment,
            'services': {},
            'dependencies': {},
            'overall_status': 'healthy',
            'timestamp': None
        }
        
        try:
            from datetime import datetime
            health_status['timestamp'] = datetime.utcnow().isoformat()
            
            # Check RDS health
            if self.rds_manager:
                rds_healthy = await self.rds_manager.health_check()
                health_status['dependencies']['rds'] = {
                    'status': 'healthy' if rds_healthy else 'unhealthy',
                    'connected': rds_healthy
                }
                if not rds_healthy:
                    health_status['overall_status'] = 'unhealthy'
            else:
                health_status['dependencies']['rds'] = {'status': 'not_initialized'}
                health_status['overall_status'] = 'unhealthy'
            
            # Check Redis health
            if self.redis_client:
                try:
                    await self.redis_client.ping()
                    health_status['dependencies']['redis'] = {'status': 'healthy'}
                except Exception as e:
                    health_status['dependencies']['redis'] = {'status': 'unhealthy', 'error': str(e)}
            else:
                health_status['dependencies']['redis'] = {'status': 'not_configured'}
            
            # Check AWS connectivity
            try:
                connectivity_results = await AWSConfigManager.test_aws_connectivity(self.config)
                
                health_status['dependencies']['aws'] = {
                    's3': connectivity_results['s3'],
                    'rds_api': connectivity_results['rds_api'],
                    'sts': connectivity_results['sts']
                }
                
                # Mark as unhealthy if critical AWS services are down
                if not connectivity_results['s3']['connected']:
                    health_status['overall_status'] = 'unhealthy'
                    
            except Exception as e:
                health_status['dependencies']['aws'] = {'status': 'error', 'error': str(e)}
                health_status['overall_status'] = 'unhealthy'
            
            # Check individual service health
            for service_name, service in self._services.items():
                if hasattr(service, 'health_check'):
                    try:
                        service_health = await service.health_check()
                        health_status['services'][service_name] = service_health
                        
                        if service_health.get('status') != 'healthy':
                            health_status['overall_status'] = 'unhealthy'
                            
                    except Exception as e:
                        health_status['services'][service_name] = {
                            'status': 'error',
                            'error': str(e)
                        }
                        health_status['overall_status'] = 'unhealthy'
                else:
                    health_status['services'][service_name] = {'status': 'no_health_check'}
            
            # Check CloudWatch monitoring status
            health_status['dependencies']['cloudwatch'] = {
                'status': 'healthy' if self._monitoring_enabled else 'not_configured',
                'enabled': self._monitoring_enabled
            }
            
            # Send health metrics to CloudWatch if enabled
            if self._monitoring_enabled:
                await self._send_health_metrics(health_status)
            
        except Exception as e:
            health_status['overall_status'] = 'error'
            health_status['error'] = str(e)
            logger.error(f"Health check failed: {e}")
        
        return health_status
    
    async def _send_health_metrics(self, health_status: Dict[str, Any]):
        """Send health metrics to CloudWatch."""
        if not self.cloudwatch_client:
            return
        
        try:
            namespace = f"T2M/{self.config.environment}"
            timestamp = datetime.utcnow()
            
            # Overall health metric
            overall_healthy = 1 if health_status['overall_status'] == 'healthy' else 0
            
            # Service-specific metrics
            metrics_data = [
                {
                    'MetricName': 'ServiceFactoryHealth',
                    'Value': overall_healthy,
                    'Unit': 'Count',
                    'Timestamp': timestamp,
                    'Dimensions': [
                        {'Name': 'Environment', 'Value': self.config.environment},
                        {'Name': 'ServiceFactory', 'Value': 'AWSServiceFactory'}
                    ]
                }
            ]
            
            # Add individual service health metrics
            for service_name, service_health in health_status.get('services', {}).items():
                service_healthy = 1 if service_health.get('status') == 'healthy' else 0
                metrics_data.append({
                    'MetricName': 'ServiceHealth',
                    'Value': service_healthy,
                    'Unit': 'Count',
                    'Timestamp': timestamp,
                    'Dimensions': [
                        {'Name': 'Environment', 'Value': self.config.environment},
                        {'Name': 'ServiceName', 'Value': service_name}
                    ]
                })
            
            # Add dependency health metrics
            for dep_name, dep_health in health_status.get('dependencies', {}).items():
                if isinstance(dep_health, dict) and 'status' in dep_health:
                    dep_healthy = 1 if dep_health['status'] == 'healthy' else 0
                    metrics_data.append({
                        'MetricName': 'DependencyHealth',
                        'Value': dep_healthy,
                        'Unit': 'Count',
                        'Timestamp': timestamp,
                        'Dimensions': [
                            {'Name': 'Environment', 'Value': self.config.environment},
                            {'Name': 'DependencyName', 'Value': dep_name}
                        ]
                    })
            
            # Send metrics in batches (CloudWatch limit is 20 metrics per call)
            for i in range(0, len(metrics_data), 20):
                batch = metrics_data[i:i+20]
                await asyncio.get_event_loop().run_in_executor(
                    None,
                    self.cloudwatch_client.put_metric_data,
                    {'Namespace': namespace, 'MetricData': batch}
                )
            
            logger.debug(f"Sent {len(metrics_data)} health metrics to CloudWatch")
            
        except Exception as e:
            logger.warning(f"Failed to send health metrics to CloudWatch: {e}")
    
    async def send_custom_metric(self, metric_name: str, value: float, unit: str = 'Count',
                                dimensions: Optional[Dict[str, str]] = None):
        """
        Send custom metric to CloudWatch.
        
        Args:
            metric_name: Name of the metric
            value: Metric value
            unit: Metric unit (Count, Seconds, Bytes, etc.)
            dimensions: Optional metric dimensions
        """
        if not self.cloudwatch_client:
            logger.warning("CloudWatch client not available for custom metrics")
            return
        
        try:
            namespace = f"T2M/{self.config.environment}"
            
            # Prepare dimensions
            metric_dimensions = [
                {'Name': 'Environment', 'Value': self.config.environment}
            ]
            
            if dimensions:
                for key, value in dimensions.items():
                    metric_dimensions.append({'Name': key, 'Value': value})
            
            metric_data = {
                'MetricName': metric_name,
                'Value': value,
                'Unit': unit,
                'Timestamp': datetime.utcnow(),
                'Dimensions': metric_dimensions
            }
            
            await asyncio.get_event_loop().run_in_executor(
                None,
                self.cloudwatch_client.put_metric_data,
                {'Namespace': namespace, 'MetricData': [metric_data]}
            )
            
            logger.debug(f"Sent custom metric {metric_name}={value} to CloudWatch")
            
        except Exception as e:
            logger.error(f"Failed to send custom metric {metric_name}: {e}")
    
    async def validate_service_configuration(self) -> Dict[str, Any]:
        """
        Validate configuration for all AWS services.
        
        Returns:
            Dict containing validation results for each service
        """
        validation_results = {
            'overall_valid': True,
            'services': {},
            'dependencies': {},
            'warnings': [],
            'errors': []
        }
        
        try:
            # Validate AWS configuration
            try:
                AWSConfigManager.validate_config(self.config)
                validation_results['dependencies']['aws_config'] = {
                    'valid': True,
                    'message': 'AWS configuration is valid'
                }
            except Exception as e:
                validation_results['dependencies']['aws_config'] = {
                    'valid': False,
                    'error': str(e)
                }
                validation_results['overall_valid'] = False
                validation_results['errors'].append(f"AWS configuration invalid: {e}")
            
            # Validate S3 buckets exist and are accessible
            s3_validation = await self._validate_s3_configuration()
            validation_results['dependencies']['s3'] = s3_validation
            if not s3_validation['valid']:
                validation_results['overall_valid'] = False
            
            # Validate RDS connectivity and schema
            rds_validation = await self._validate_rds_configuration()
            validation_results['dependencies']['rds'] = rds_validation
            if not rds_validation['valid']:
                validation_results['overall_valid'] = False
            
            # Validate Redis if configured
            if self.redis_client:
                redis_validation = await self._validate_redis_configuration()
                validation_results['dependencies']['redis'] = redis_validation
                if not redis_validation['valid']:
                    validation_results['warnings'].append("Redis validation failed")
            
            # Validate CloudWatch if enabled
            if self.cloudwatch_client:
                cw_validation = await self._validate_cloudwatch_configuration()
                validation_results['dependencies']['cloudwatch'] = cw_validation
                if not cw_validation['valid']:
                    validation_results['warnings'].append("CloudWatch validation failed")
            
            # Validate individual services if they exist
            for service_name, service in self._services.items():
                if hasattr(service, 'validate_configuration'):
                    try:
                        service_validation = await service.validate_configuration()
                        validation_results['services'][service_name] = service_validation
                        if not service_validation.get('valid', True):
                            validation_results['overall_valid'] = False
                    except Exception as e:
                        validation_results['services'][service_name] = {
                            'valid': False,
                            'error': str(e)
                        }
                        validation_results['overall_valid'] = False
            
        except Exception as e:
            validation_results['overall_valid'] = False
            validation_results['errors'].append(f"Configuration validation failed: {e}")
            logger.error(f"Service configuration validation failed: {e}")
        
        return validation_results
    
    async def _validate_s3_configuration(self) -> Dict[str, Any]:
        """Validate S3 bucket configuration."""
        try:
            session = boto3.Session(
                aws_access_key_id=self.config.access_key_id,
                aws_secret_access_key=self.config.secret_access_key,
                region_name=self.config.region
            )
            s3_client = session.client('s3')
            
            bucket_status = {}
            all_valid = True
            
            for bucket_type, bucket_name in self.config.buckets.items():
                try:
                    await asyncio.get_event_loop().run_in_executor(
                        None, s3_client.head_bucket, {'Bucket': bucket_name}
                    )
                    bucket_status[bucket_type] = {'exists': True, 'accessible': True}
                except ClientError as e:
                    error_code = e.response['Error']['Code']
                    if error_code == '404':
                        bucket_status[bucket_type] = {'exists': False, 'accessible': False}
                    else:
                        bucket_status[bucket_type] = {'exists': True, 'accessible': False, 'error': str(e)}
                    all_valid = False
            
            return {
                'valid': all_valid,
                'bucket_status': bucket_status,
                'message': 'All S3 buckets are accessible' if all_valid else 'Some S3 buckets are not accessible'
            }
            
        except Exception as e:
            return {
                'valid': False,
                'error': str(e),
                'message': 'S3 configuration validation failed'
            }
    
    async def _validate_rds_configuration(self) -> Dict[str, Any]:
        """Validate RDS configuration."""
        try:
            if not self.rds_manager:
                return {
                    'valid': False,
                    'message': 'RDS manager not initialized'
                }
            
            # Test database connectivity
            health_check = await self.rds_manager.health_check()
            
            return {
                'valid': health_check,
                'message': 'RDS connection is healthy' if health_check else 'RDS connection failed'
            }
            
        except Exception as e:
            return {
                'valid': False,
                'error': str(e),
                'message': 'RDS configuration validation failed'
            }
    
    async def _validate_redis_configuration(self) -> Dict[str, Any]:
        """Validate Redis configuration."""
        try:
            if not self.redis_client:
                return {
                    'valid': False,
                    'message': 'Redis client not initialized'
                }
            
            await self.redis_client.ping()
            return {
                'valid': True,
                'message': 'Redis connection is healthy'
            }
            
        except Exception as e:
            return {
                'valid': False,
                'error': str(e),
                'message': 'Redis configuration validation failed'
            }
    
    async def _validate_cloudwatch_configuration(self) -> Dict[str, Any]:
        """Validate CloudWatch configuration."""
        try:
            if not self.cloudwatch_client:
                return {
                    'valid': False,
                    'message': 'CloudWatch client not initialized'
                }
            
            # Test CloudWatch connectivity
            await asyncio.get_event_loop().run_in_executor(
                None, lambda: self.cloudwatch_client.list_metrics(MaxRecords=1)
            )
            
            return {
                'valid': True,
                'message': 'CloudWatch connection is healthy'
            }
            
        except Exception as e:
            return {
                'valid': False,
                'error': str(e),
                'message': 'CloudWatch configuration validation failed'
            }
    
    async def close(self):
        """
        Close all services and clean up resources.
        """
        try:
            logger.info("Closing AWS Service Factory...")
            
            # Close individual services
            for service_name, service in self._services.items():
                if hasattr(service, 'close'):
                    try:
                        await service.close()
                        logger.info(f"Closed {service_name}")
                    except Exception as e:
                        logger.warning(f"Error closing {service_name}: {e}")
            
            # Close RDS manager
            if self.rds_manager:
                try:
                    await self.rds_manager.close()
                    logger.info("Closed RDS connection manager")
                except Exception as e:
                    logger.warning(f"Error closing RDS manager: {e}")
            
            # Close Redis client
            if self.redis_client:
                try:
                    await self.redis_client.close()
                    logger.info("Closed Redis client")
                except Exception as e:
                    logger.warning(f"Error closing Redis client: {e}")
            
            # Close CloudWatch client (boto3 clients don't need explicit closing)
            if self.cloudwatch_client:
                self.cloudwatch_client = None
                logger.info("Closed CloudWatch client")
            
            self._services.clear()
            self._initialized = False
            self._monitoring_enabled = False
            
            logger.info("AWS Service Factory closed successfully")
            
        except Exception as e:
            logger.error(f"Error during service factory cleanup: {e}")
    
    def get_config(self) -> AWSConfig:
        """
        Get the current AWS configuration.
        
        Returns:
            AWSConfig: Current configuration
        """
        return self.config
    
    def is_initialized(self) -> bool:
        """
        Check if the service factory is initialized.
        
        Returns:
            bool: True if initialized, False otherwise
        """
        return self._initialized
    
    def list_services(self) -> Dict[str, str]:
        """
        List all created services.
        
        Returns:
            Dict mapping service names to their class names
        """
        return {
            name: service.__class__.__name__ 
            for name, service in self._services.items()
        }
    
    def get_service_count(self) -> int:
        """
        Get the number of created services.
        
        Returns:
            int: Number of services created
        """
        return len(self._services)
    
    def is_monitoring_enabled(self) -> bool:
        """
        Check if CloudWatch monitoring is enabled.
        
        Returns:
            bool: True if monitoring is enabled
        """
        return self._monitoring_enabled
    
    async def restart_service(self, service_name: str) -> bool:
        """
        Restart a specific service.
        
        Args:
            service_name: Name of the service to restart
            
        Returns:
            bool: True if restart successful
        """
        if service_name not in self._services:
            logger.warning(f"Service {service_name} not found for restart")
            return False
        
        try:
            # Close the existing service
            service = self._services[service_name]
            if hasattr(service, 'close'):
                await service.close()
            
            # Remove from services dict
            del self._services[service_name]
            
            # Recreate the service
            if service_name == 'video_service':
                self.create_video_service()
            elif service_name == 'file_service':
                self.create_file_service()
            elif service_name == 'job_service':
                self.create_job_service()
            elif service_name == 'user_service':
                self.create_user_service()
            else:
                logger.error(f"Unknown service type for restart: {service_name}")
                return False
            
            logger.info(f"Successfully restarted service: {service_name}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to restart service {service_name}: {e}")
            return False
    
    async def get_service_metrics(self) -> Dict[str, Any]:
        """
        Get metrics for all services.
        
        Returns:
            Dict containing service metrics
        """
        metrics = {
            'factory': {
                'initialized': self._initialized,
                'monitoring_enabled': self._monitoring_enabled,
                'service_count': len(self._services),
                'environment': self.config.environment
            },
            'services': {}
        }
        
        # Get metrics from individual services
        for service_name, service in self._services.items():
            if hasattr(service, 'get_metrics'):
                try:
                    service_metrics = await service.get_metrics()
                    metrics['services'][service_name] = service_metrics
                except Exception as e:
                    metrics['services'][service_name] = {
                        'error': str(e),
                        'status': 'metrics_unavailable'
                    }
            else:
                metrics['services'][service_name] = {
                    'status': 'no_metrics_available'
                }
        
        return metrics


# Global service factory instance
_service_factory: Optional[AWSServiceFactory] = None


async def get_service_factory() -> AWSServiceFactory:
    """
    Get the global AWS service factory instance.
    
    Returns:
        AWSServiceFactory: Global service factory instance
        
    Raises:
        RuntimeError: If factory not initialized
    """
    global _service_factory
    
    if _service_factory is None:
        _service_factory = AWSServiceFactory()
        success = await _service_factory.initialize()
        
        if not success:
            _service_factory = None
            raise RuntimeError("Failed to initialize AWS service factory")
    
    return _service_factory


async def close_service_factory():
    """Close the global service factory instance."""
    global _service_factory
    
    if _service_factory:
        await _service_factory.close()
        _service_factory = None