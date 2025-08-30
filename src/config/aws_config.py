"""
AWS Configuration Management

This module provides AWS configuration classes and environment variable management
for the video generation application. It includes configuration validation,
AWS connectivity testing, and environment-specific resource identification.
"""

import os
import logging
import asyncio
from typing import Dict, Any, Optional, Tuple
from dataclasses import dataclass, field
from enum import Enum
import boto3
from botocore.exceptions import ClientError, NoCredentialsError, EndpointConnectionError
from dotenv import load_dotenv

# PostgreSQL connectivity imports
try:
    import psycopg2
    from psycopg2 import OperationalError as PgOperationalError
    from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT
    PSYCOPG2_AVAILABLE = True
except ImportError:
    PSYCOPG2_AVAILABLE = False
    psycopg2 = None
    PgOperationalError = Exception

# Load environment variables
load_dotenv()

logger = logging.getLogger(__name__)


class Environment(Enum):
    """Supported deployment environments"""
    DEVELOPMENT = "development"
    STAGING = "staging"
    PRODUCTION = "production"


@dataclass
class AWSConfig:
    """AWS configuration for different environments"""
    access_key_id: str
    secret_access_key: str
    region: str
    buckets: Dict[str, str] = field(default_factory=dict)
    rds_endpoint: str = ""
    rds_database: str = ""
    rds_username: str = ""
    rds_password: str = ""
    environment: str = "development"
    account_id: Optional[str] = None
    
    def __post_init__(self):
        """Initialize bucket names after object creation"""
        if not self.buckets:
            self.buckets = self._generate_bucket_names()
    
    def _generate_bucket_names(self) -> Dict[str, str]:
        """Generate environment-specific bucket names"""
        if not self.account_id:
            # Try to get account ID from STS if not provided
            try:
                session = boto3.Session(
                    aws_access_key_id=self.access_key_id,
                    aws_secret_access_key=self.secret_access_key,
                    region_name=self.region
                )
                sts_client = session.client('sts')
                self.account_id = sts_client.get_caller_identity()['Account']
            except Exception as e:
                logger.warning(f"Could not retrieve AWS account ID: {e}")
                self.account_id = "unknown"
        
        # Bucket naming convention: {env}-t2m-{type}-{region}-{account-id}
        base_name = f"{self.environment}-t2m"
        suffix = f"{self.region}-{self.account_id}"
        
        return {
            'videos': f"{base_name}-videos-{suffix}",
            'code': f"{base_name}-code-{suffix}",
            'thumbnails': f"{base_name}-thumbnails-{suffix}",
            'temp': f"{base_name}-temp-{suffix}"
        }


class AWSConfigManager:
    """Manages AWS configuration across environments"""
    
    @staticmethod
    def load_config(environment: Optional[str] = None) -> AWSConfig:
        """
        Load AWS configuration from environment variables
        
        Args:
            environment: Target environment (development, staging, production)
            
        Returns:
            AWSConfig: Configured AWS settings
            
        Raises:
            ValueError: If required configuration is missing
        """
        env = environment or os.getenv('ENVIRONMENT', 'development')
        
        # Validate environment
        try:
            Environment(env)
        except ValueError:
            raise ValueError(f"Invalid environment: {env}. Must be one of: {[e.value for e in Environment]}")
        
        # Load AWS credentials
        access_key_id = os.getenv('AWS_ACCESS_KEY_ID')
        secret_access_key = os.getenv('AWS_SECRET_ACCESS_KEY')
        region = os.getenv('AWS_REGION', 'us-east-1')
        
        if not access_key_id or not secret_access_key:
            raise ValueError("AWS credentials not found. Please set AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY")
        
        # Load RDS configuration
        rds_endpoint = os.getenv('RDS_ENDPOINT', '')
        rds_database = os.getenv('RDS_DATABASE', 't2m_db')
        rds_username = os.getenv('RDS_USERNAME', '')
        rds_password = os.getenv('RDS_PASSWORD', '')
        
        # Optional account ID for bucket naming
        account_id = os.getenv('AWS_ACCOUNT_ID')
        
        config = AWSConfig(
            access_key_id=access_key_id,
            secret_access_key=secret_access_key,
            region=region,
            rds_endpoint=rds_endpoint,
            rds_database=rds_database,
            rds_username=rds_username,
            rds_password=rds_password,
            environment=env,
            account_id=account_id
        )
        
        logger.info(f"Loaded AWS configuration for environment: {env}")
        return config
    
    @staticmethod
    def validate_config(config: AWSConfig) -> bool:
        """
        Validate AWS configuration
        
        Args:
            config: AWS configuration to validate
            
        Returns:
            bool: True if configuration is valid
            
        Raises:
            ValueError: If configuration is invalid
            ConnectionError: If AWS connectivity fails
        """
        # Check required fields
        required_fields = [
            ('access_key_id', config.access_key_id),
            ('secret_access_key', config.secret_access_key),
            ('region', config.region)
        ]
        
        missing_fields = [name for name, value in required_fields if not value]
        if missing_fields:
            raise ValueError(f"Missing required AWS configuration: {', '.join(missing_fields)}")
        
        # Validate RDS configuration if provided
        if config.rds_endpoint:
            rds_required = [
                ('rds_username', config.rds_username),
                ('rds_password', config.rds_password),
                ('rds_database', config.rds_database)
            ]
            missing_rds = [name for name, value in rds_required if not value]
            if missing_rds:
                raise ValueError(f"Missing required RDS configuration: {', '.join(missing_rds)}")
        
        logger.info("AWS configuration validation passed")
        return True
    
    @staticmethod
    async def test_aws_connectivity(config: AWSConfig) -> Dict[str, Any]:
        """
        Test AWS service connectivity with detailed results
        
        Args:
            config: AWS configuration to test
            
        Returns:
            Dict[str, Any]: Detailed service connectivity status
        """
        results = {
            'sts': {'connected': False, 'details': {}, 'error': None},
            's3': {'connected': False, 'details': {}, 'error': None},
            'rds_api': {'connected': False, 'details': {}, 'error': None},
            'rds_postgres': {'connected': False, 'details': {}, 'error': None}
        }
        
        try:
            # Create AWS session
            session = boto3.Session(
                aws_access_key_id=config.access_key_id,
                aws_secret_access_key=config.secret_access_key,
                region_name=config.region
            )
            
            # Test STS (Security Token Service) - basic AWS connectivity
            try:
                sts_client = session.client('sts')
                identity = sts_client.get_caller_identity()
                results['sts']['connected'] = True
                results['sts']['details'] = {
                    'account_id': identity.get('Account'),
                    'user_id': identity.get('UserId'),
                    'arn': identity.get('Arn')
                }
                logger.info(f"AWS STS connectivity successful. Account: {identity.get('Account')}")
            except Exception as e:
                results['sts']['error'] = str(e)
                logger.error(f"AWS STS connectivity failed: {e}")
            
            # Test S3 connectivity with comprehensive checks
            s3_result = await AWSConfigManager._test_s3_connectivity(session, config)
            results['s3'] = s3_result
            
            # Test RDS API connectivity
            rds_api_result = await AWSConfigManager._test_rds_api_connectivity(session, config)
            results['rds_api'] = rds_api_result
            
            # Test RDS PostgreSQL database connectivity
            if config.rds_endpoint and config.rds_username and config.rds_password:
                rds_postgres_result = await AWSConfigManager._test_rds_postgres_connectivity(config)
                results['rds_postgres'] = rds_postgres_result
            else:
                results['rds_postgres']['connected'] = None  # Not configured
                results['rds_postgres']['details']['message'] = "RDS configuration not provided"
                logger.info("RDS configuration not provided, skipping PostgreSQL connectivity test")
        
        except NoCredentialsError as e:
            error_msg = "AWS credentials not found or invalid"
            logger.error(error_msg)
            for service in results:
                results[service]['error'] = error_msg
            raise ConnectionError(error_msg)
        except Exception as e:
            error_msg = f"Unexpected error during AWS connectivity test: {e}"
            logger.error(error_msg)
            for service in results:
                if not results[service]['connected']:
                    results[service]['error'] = str(e)
            raise ConnectionError(error_msg)
        
        return results
    
    @staticmethod
    async def _test_s3_connectivity(session: boto3.Session, config: AWSConfig) -> Dict[str, Any]:
        """
        Test S3 connectivity with comprehensive checks
        
        Args:
            session: Boto3 session
            config: AWS configuration
            
        Returns:
            Dict containing S3 connectivity results
        """
        result = {'connected': False, 'details': {}, 'error': None}
        
        try:
            s3_client = session.client('s3')
            
            # Test 1: List buckets (basic connectivity)
            buckets_response = s3_client.list_buckets()
            result['details']['buckets_count'] = len(buckets_response.get('Buckets', []))
            result['details']['owner'] = buckets_response.get('Owner', {})
            
            # Test 2: Check if our application buckets exist
            existing_buckets = [bucket['Name'] for bucket in buckets_response.get('Buckets', [])]
            app_buckets_status = {}
            
            for bucket_type, bucket_name in config.buckets.items():
                bucket_exists = bucket_name in existing_buckets
                app_buckets_status[bucket_type] = {
                    'name': bucket_name,
                    'exists': bucket_exists
                }
                
                # Test 3: If bucket exists, test basic operations
                if bucket_exists:
                    try:
                        # Test head bucket (check permissions)
                        s3_client.head_bucket(Bucket=bucket_name)
                        app_buckets_status[bucket_type]['accessible'] = True
                        
                        # Test list objects (read permission)
                        s3_client.list_objects_v2(Bucket=bucket_name, MaxKeys=1)
                        app_buckets_status[bucket_type]['readable'] = True
                        
                    except ClientError as e:
                        error_code = e.response['Error']['Code']
                        app_buckets_status[bucket_type]['accessible'] = False
                        app_buckets_status[bucket_type]['error'] = f"{error_code}: {e.response['Error']['Message']}"
            
            result['details']['app_buckets'] = app_buckets_status
            result['connected'] = True
            logger.info("AWS S3 connectivity successful")
            
        except EndpointConnectionError as e:
            result['error'] = f"Cannot connect to S3 endpoint: {e}"
            logger.error(f"AWS S3 endpoint connection failed: {e}")
        except ClientError as e:
            error_code = e.response['Error']['Code']
            result['error'] = f"S3 API error {error_code}: {e.response['Error']['Message']}"
            logger.error(f"AWS S3 API error: {e}")
        except Exception as e:
            result['error'] = f"Unexpected S3 error: {e}"
            logger.error(f"AWS S3 connectivity failed: {e}")
        
        return result
    
    @staticmethod
    async def _test_rds_api_connectivity(session: boto3.Session, config: AWSConfig) -> Dict[str, Any]:
        """
        Test RDS API connectivity
        
        Args:
            session: Boto3 session
            config: AWS configuration
            
        Returns:
            Dict containing RDS API connectivity results
        """
        result = {'connected': False, 'details': {}, 'error': None}
        
        try:
            rds_client = session.client('rds')
            
            # Test 1: Basic RDS API connectivity
            db_instances = rds_client.describe_db_instances()
            result['details']['total_instances'] = len(db_instances.get('DBInstances', []))
            
            # Test 2: Check if our specific RDS instance exists
            if config.rds_endpoint:
                # Extract DB instance identifier from endpoint
                # Format: instance-name.random.region.rds.amazonaws.com
                db_identifier = config.rds_endpoint.split('.')[0]
                
                try:
                    specific_instance = rds_client.describe_db_instances(
                        DBInstanceIdentifier=db_identifier
                    )
                    
                    if specific_instance['DBInstances']:
                        instance_info = specific_instance['DBInstances'][0]
                        result['details']['target_instance'] = {
                            'identifier': instance_info.get('DBInstanceIdentifier'),
                            'status': instance_info.get('DBInstanceStatus'),
                            'engine': instance_info.get('Engine'),
                            'engine_version': instance_info.get('EngineVersion'),
                            'endpoint': instance_info.get('Endpoint', {}).get('Address'),
                            'port': instance_info.get('Endpoint', {}).get('Port'),
                            'availability_zone': instance_info.get('AvailabilityZone'),
                            'publicly_accessible': instance_info.get('PubliclyAccessible')
                        }
                        
                except ClientError as e:
                    if e.response['Error']['Code'] == 'DBInstanceNotFound':
                        result['details']['target_instance'] = {'error': 'Instance not found'}
                    else:
                        result['details']['target_instance'] = {'error': str(e)}
            
            result['connected'] = True
            logger.info("AWS RDS API connectivity successful")
            
        except Exception as e:
            result['error'] = f"RDS API error: {e}"
            logger.error(f"AWS RDS API connectivity failed: {e}")
        
        return result
    
    @staticmethod
    async def _test_rds_postgres_connectivity(config: AWSConfig) -> Dict[str, Any]:
        """
        Test direct PostgreSQL connectivity to RDS instance
        
        Args:
            config: AWS configuration
            
        Returns:
            Dict containing PostgreSQL connectivity results
        """
        result = {'connected': False, 'details': {}, 'error': None}
        
        if not PSYCOPG2_AVAILABLE:
            result['error'] = "psycopg2 not available. Install with: pip install psycopg2-binary"
            logger.error("psycopg2 not available for PostgreSQL connectivity test")
            return result
        
        # Extract port from endpoint if specified, default to 5432
        endpoint_parts = config.rds_endpoint.split(':')
        host = endpoint_parts[0]
        port = int(endpoint_parts[1]) if len(endpoint_parts) > 1 else 5432
        
        connection = None
        try:
            # Create connection string
            conn_params = {
                'host': host,
                'port': port,
                'dbname': config.rds_database,
                'user': config.rds_username,
                'password': config.rds_password,
                'connect_timeout': 10,  # 10 second timeout
                'sslmode': 'prefer'  # Prefer SSL but don't require it
            }
            
            # Test connection
            connection = psycopg2.connect(**conn_params)
            connection.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
            
            # Get database information
            with connection.cursor() as cursor:
                # Test 1: Basic connectivity and get server version
                cursor.execute("SELECT version();")
                version_info = cursor.fetchone()[0]
                result['details']['server_version'] = version_info
                
                # Test 2: Get database size
                cursor.execute("""
                    SELECT pg_size_pretty(pg_database_size(%s)) as db_size;
                """, (config.rds_database,))
                db_size = cursor.fetchone()[0]
                result['details']['database_size'] = db_size
                
                # Test 3: Check connection info
                result['details']['connection_info'] = {
                    'host': host,
                    'port': port,
                    'database': config.rds_database,
                    'user': config.rds_username,
                    'server_version_num': connection.server_version,
                    'protocol_version': connection.protocol_version,
                    'backend_pid': connection.get_backend_pid()
                }
                
                # Test 4: Check basic permissions
                try:
                    cursor.execute("SELECT current_user, session_user, current_database();")
                    user_info = cursor.fetchone()
                    result['details']['user_info'] = {
                        'current_user': user_info[0],
                        'session_user': user_info[1],
                        'current_database': user_info[2]
                    }
                except Exception as e:
                    result['details']['user_info_error'] = str(e)
                
                # Test 5: Check if we can create/drop tables (write permissions)
                try:
                    test_table = f"connectivity_test_{os.getpid()}"
                    cursor.execute(f"""
                        CREATE TEMP TABLE {test_table} (
                            id SERIAL PRIMARY KEY,
                            test_data TEXT
                        );
                    """)
                    cursor.execute(f"INSERT INTO {test_table} (test_data) VALUES (%s);", ("test",))
                    cursor.execute(f"SELECT COUNT(*) FROM {test_table};")
                    count = cursor.fetchone()[0]
                    cursor.execute(f"DROP TABLE {test_table};")
                    
                    result['details']['write_permissions'] = True
                    result['details']['test_operations'] = f"Created temp table, inserted 1 row, verified {count} rows, dropped table"
                    
                except Exception as e:
                    result['details']['write_permissions'] = False
                    result['details']['write_permissions_error'] = str(e)
            
            result['connected'] = True
            logger.info(f"PostgreSQL connectivity successful to {host}:{port}/{config.rds_database}")
            
        except PgOperationalError as e:
            # PostgreSQL specific errors
            result['error'] = f"PostgreSQL connection error: {e}"
            logger.error(f"PostgreSQL connectivity failed: {e}")
            
        except Exception as e:
            result['error'] = f"Database connectivity error: {e}"
            logger.error(f"RDS PostgreSQL connectivity failed: {e}")
            
        finally:
            if connection:
                try:
                    connection.close()
                except Exception:
                    pass  # Ignore errors when closing
        
        return result
    
    @staticmethod
    def get_environment_resources(config: AWSConfig) -> Dict[str, Any]:
        """
        Get environment-specific resource identifiers
        
        Args:
            config: AWS configuration
            
        Returns:
            Dict[str, Any]: Environment resource information
        """
        return {
            'environment': config.environment,
            'region': config.region,
            'account_id': config.account_id,
            'buckets': config.buckets,
            'rds': {
                'endpoint': config.rds_endpoint,
                'database': config.rds_database,
                'username': config.rds_username
            } if config.rds_endpoint else None
        }


class AWSS3Manager:
    """Manages S3 operations for the application"""
    
    @staticmethod
    def create_application_buckets(config: AWSConfig) -> Dict[str, Any]:
        """
        Create application S3 buckets if they don't exist
        
        Args:
            config: AWS configuration
            
        Returns:
            Dict containing creation results for each bucket
        """
        results = {}
        
        try:
            session = boto3.Session(
                aws_access_key_id=config.access_key_id,
                aws_secret_access_key=config.secret_access_key,
                region_name=config.region
            )
            s3_client = session.client('s3')
            
            for bucket_type, bucket_name in config.buckets.items():
                bucket_result = {'created': False, 'existed': False, 'error': None}
                
                try:
                    # Check if bucket exists
                    s3_client.head_bucket(Bucket=bucket_name)
                    bucket_result['existed'] = True
                    logger.info(f"Bucket {bucket_name} already exists")
                    
                except ClientError as e:
                    error_code = e.response['Error']['Code']
                    
                    if error_code == '404':
                        # Bucket doesn't exist, create it
                        try:
                            if config.region == 'us-east-1':
                                # us-east-1 doesn't need LocationConstraint
                                s3_client.create_bucket(Bucket=bucket_name)
                            else:
                                s3_client.create_bucket(
                                    Bucket=bucket_name,
                                    CreateBucketConfiguration={'LocationConstraint': config.region}
                                )
                            
                            bucket_result['created'] = True
                            logger.info(f"Successfully created bucket {bucket_name}")
                            
                        except ClientError as create_error:
                            bucket_result['error'] = f"Failed to create bucket: {create_error}"
                            logger.error(f"Failed to create bucket {bucket_name}: {create_error}")
                    else:
                        bucket_result['error'] = f"Error checking bucket: {e}"
                        logger.error(f"Error checking bucket {bucket_name}: {e}")
                
                results[bucket_type] = bucket_result
                
        except Exception as e:
            logger.error(f"Error in bucket creation process: {e}")
            for bucket_type in config.buckets:
                if bucket_type not in results:
                    results[bucket_type] = {'created': False, 'existed': False, 'error': str(e)}
        
        return results
    
    @staticmethod
    def test_s3_operations(config: AWSConfig, bucket_type: str = 'temp') -> Dict[str, Any]:
        """
        Test basic S3 operations (upload, download, delete)
        
        Args:
            config: AWS configuration
            bucket_type: Type of bucket to test (default: 'temp')
            
        Returns:
            Dict containing test results
        """
        result = {'success': False, 'operations': {}, 'error': None}
        
        if bucket_type not in config.buckets:
            result['error'] = f"Bucket type '{bucket_type}' not found in configuration"
            return result
        
        bucket_name = config.buckets[bucket_type]
        test_key = f"connectivity-test-{os.getpid()}.txt"
        test_content = f"AWS S3 connectivity test - {config.environment}"
        
        try:
            session = boto3.Session(
                aws_access_key_id=config.access_key_id,
                aws_secret_access_key=config.secret_access_key,
                region_name=config.region
            )
            s3_client = session.client('s3')
            
            # Test 1: Upload object
            try:
                s3_client.put_object(
                    Bucket=bucket_name,
                    Key=test_key,
                    Body=test_content.encode('utf-8'),
                    ContentType='text/plain'
                )
                result['operations']['upload'] = {'success': True, 'key': test_key}
                logger.info(f"Successfully uploaded test object to {bucket_name}/{test_key}")
            except Exception as e:
                result['operations']['upload'] = {'success': False, 'error': str(e)}
                logger.error(f"Failed to upload test object: {e}")
                return result
            
            # Test 2: Download object
            try:
                response = s3_client.get_object(Bucket=bucket_name, Key=test_key)
                downloaded_content = response['Body'].read().decode('utf-8')
                
                if downloaded_content == test_content:
                    result['operations']['download'] = {'success': True, 'content_match': True}
                    logger.info(f"Successfully downloaded and verified test object")
                else:
                    result['operations']['download'] = {
                        'success': True, 
                        'content_match': False,
                        'expected': test_content,
                        'actual': downloaded_content
                    }
            except Exception as e:
                result['operations']['download'] = {'success': False, 'error': str(e)}
                logger.error(f"Failed to download test object: {e}")
            
            # Test 3: List objects
            try:
                response = s3_client.list_objects_v2(Bucket=bucket_name, Prefix=test_key)
                objects_found = len(response.get('Contents', []))
                result['operations']['list'] = {'success': True, 'objects_found': objects_found}
                logger.info(f"Successfully listed objects, found {objects_found} matching objects")
            except Exception as e:
                result['operations']['list'] = {'success': False, 'error': str(e)}
                logger.error(f"Failed to list objects: {e}")
            
            # Test 4: Delete object (cleanup)
            try:
                s3_client.delete_object(Bucket=bucket_name, Key=test_key)
                result['operations']['delete'] = {'success': True}
                logger.info(f"Successfully deleted test object")
            except Exception as e:
                result['operations']['delete'] = {'success': False, 'error': str(e)}
                logger.error(f"Failed to delete test object: {e}")
            
            # Overall success if upload and download worked
            result['success'] = (
                result['operations'].get('upload', {}).get('success', False) and
                result['operations'].get('download', {}).get('success', False)
            )
            
        except Exception as e:
            result['error'] = f"S3 operations test failed: {e}"
            logger.error(f"S3 operations test failed: {e}")
        
        return result


class AWSRDSManager:
    """Manages RDS PostgreSQL operations for the application"""
    
    @staticmethod
    def test_database_operations(config: AWSConfig) -> Dict[str, Any]:
        """
        Test basic database operations (create table, insert, select, drop)
        
        Args:
            config: AWS configuration
            
        Returns:
            Dict containing test results
        """
        result = {'success': False, 'operations': {}, 'error': None}
        
        if not PSYCOPG2_AVAILABLE:
            result['error'] = "psycopg2 not available. Install with: pip install psycopg2-binary"
            return result
        
        if not all([config.rds_endpoint, config.rds_username, config.rds_password]):
            result['error'] = "RDS configuration incomplete"
            return result
        
        # Extract host and port
        endpoint_parts = config.rds_endpoint.split(':')
        host = endpoint_parts[0]
        port = int(endpoint_parts[1]) if len(endpoint_parts) > 1 else 5432
        
        connection = None
        test_table = f"connectivity_test_{os.getpid()}"
        
        try:
            # Connect to database
            conn_params = {
                'host': host,
                'port': port,
                'dbname': config.rds_database,
                'user': config.rds_username,
                'password': config.rds_password,
                'connect_timeout': 10,
                'sslmode': 'prefer'
            }
            
            connection = psycopg2.connect(**conn_params)
            connection.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
            
            with connection.cursor() as cursor:
                # Test 1: Create table
                try:
                    cursor.execute(f"""
                        CREATE TABLE {test_table} (
                            id SERIAL PRIMARY KEY,
                            name VARCHAR(100),
                            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                            data JSONB
                        );
                    """)
                    result['operations']['create_table'] = {'success': True, 'table': test_table}
                    logger.info(f"Successfully created test table {test_table}")
                except Exception as e:
                    result['operations']['create_table'] = {'success': False, 'error': str(e)}
                    logger.error(f"Failed to create test table: {e}")
                    return result
                
                # Test 2: Insert data
                try:
                    test_data = [
                        ('Test Record 1', '{"type": "test", "value": 1}'),
                        ('Test Record 2', '{"type": "test", "value": 2}'),
                        ('Test Record 3', '{"type": "test", "value": 3}')
                    ]
                    
                    cursor.executemany(f"""
                        INSERT INTO {test_table} (name, data) 
                        VALUES (%s, %s::jsonb);
                    """, test_data)
                    
                    result['operations']['insert'] = {'success': True, 'records_inserted': len(test_data)}
                    logger.info(f"Successfully inserted {len(test_data)} test records")
                except Exception as e:
                    result['operations']['insert'] = {'success': False, 'error': str(e)}
                    logger.error(f"Failed to insert test data: {e}")
                
                # Test 3: Select data
                try:
                    cursor.execute(f"""
                        SELECT id, name, created_at, data 
                        FROM {test_table} 
                        ORDER BY id;
                    """)
                    records = cursor.fetchall()
                    
                    result['operations']['select'] = {
                        'success': True, 
                        'records_found': len(records),
                        'sample_record': {
                            'id': records[0][0],
                            'name': records[0][1],
                            'created_at': records[0][2].isoformat() if records[0][2] else None,
                            'data': records[0][3]
                        } if records else None
                    }
                    logger.info(f"Successfully selected {len(records)} test records")
                except Exception as e:
                    result['operations']['select'] = {'success': False, 'error': str(e)}
                    logger.error(f"Failed to select test data: {e}")
                
                # Test 4: Update data
                try:
                    cursor.execute(f"""
                        UPDATE {test_table} 
                        SET data = data || '{{"updated": true}}'::jsonb 
                        WHERE id = 1;
                    """)
                    cursor.execute(f"SELECT data FROM {test_table} WHERE id = 1;")
                    updated_record = cursor.fetchone()
                    
                    result['operations']['update'] = {
                        'success': True,
                        'updated_data': updated_record[0] if updated_record else None
                    }
                    logger.info("Successfully updated test record")
                except Exception as e:
                    result['operations']['update'] = {'success': False, 'error': str(e)}
                    logger.error(f"Failed to update test data: {e}")
                
                # Test 5: Drop table (cleanup)
                try:
                    cursor.execute(f"DROP TABLE {test_table};")
                    result['operations']['drop_table'] = {'success': True}
                    logger.info(f"Successfully dropped test table {test_table}")
                except Exception as e:
                    result['operations']['drop_table'] = {'success': False, 'error': str(e)}
                    logger.error(f"Failed to drop test table: {e}")
            
            # Overall success if basic operations worked
            result['success'] = (
                result['operations'].get('create_table', {}).get('success', False) and
                result['operations'].get('insert', {}).get('success', False) and
                result['operations'].get('select', {}).get('success', False)
            )
            
        except Exception as e:
            result['error'] = f"Database operations test failed: {e}"
            logger.error(f"Database operations test failed: {e}")
            
        finally:
            if connection:
                try:
                    # Cleanup: try to drop table if it exists
                    with connection.cursor() as cursor:
                        cursor.execute(f"DROP TABLE IF EXISTS {test_table};")
                    connection.close()
                except Exception:
                    pass  # Ignore cleanup errors
        
        return result


class AWSConfigValidator:
    """Validates AWS configuration and provides detailed feedback"""
    
    @staticmethod
    def validate_bucket_names(buckets: Dict[str, str]) -> Dict[str, list]:
        """
        Validate S3 bucket names according to AWS naming rules
        
        Args:
            buckets: Dictionary of bucket names to validate
            
        Returns:
            Dict[str, list]: Validation results with any errors
        """
        errors = {}
        
        for bucket_type, bucket_name in buckets.items():
            bucket_errors = []
            
            # Check length (3-63 characters)
            if len(bucket_name) < 3 or len(bucket_name) > 63:
                bucket_errors.append("Bucket name must be between 3 and 63 characters")
            
            # Check for valid characters (lowercase letters, numbers, hyphens)
            if not bucket_name.replace('-', '').replace('.', '').isalnum():
                bucket_errors.append("Bucket name can only contain lowercase letters, numbers, hyphens, and periods")
            
            # Check that it doesn't start or end with hyphen or period
            if bucket_name.startswith('-') or bucket_name.endswith('-') or \
               bucket_name.startswith('.') or bucket_name.endswith('.'):
                bucket_errors.append("Bucket name cannot start or end with hyphen or period")
            
            # Check for consecutive periods
            if '..' in bucket_name:
                bucket_errors.append("Bucket name cannot contain consecutive periods")
            
            if bucket_errors:
                errors[bucket_type] = bucket_errors
        
        return errors
    
    @staticmethod
    def validate_region(region: str) -> bool:
        """
        Validate AWS region format
        
        Args:
            region: AWS region to validate
            
        Returns:
            bool: True if region format is valid
        """
        # Basic region format validation (e.g., us-east-1, eu-west-2)
        import re
        region_pattern = r'^[a-z]{2,}-[a-z]+-\d+$'
        return bool(re.match(region_pattern, region))


# Convenience function for quick configuration loading
def load_aws_config(environment: Optional[str] = None, validate: bool = True) -> AWSConfig:
    """
    Load and optionally validate AWS configuration
    
    Args:
        environment: Target environment
        validate: Whether to validate the configuration
        
    Returns:
        AWSConfig: Loaded configuration
    """
    config = AWSConfigManager.load_config(environment)
    
    if validate:
        AWSConfigManager.validate_config(config)
    
    return config