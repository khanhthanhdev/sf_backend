#!/usr/bin/env python3
"""
AWS Configuration Test Script

This script tests the AWS configuration setup, validates connectivity,
and provides detailed feedback about the AWS integration status.
"""

import asyncio
import sys
import logging
from pathlib import Path

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from config.aws_config import AWSConfigManager, AWSConfigValidator, load_aws_config
from config.config import Config

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


async def test_aws_configuration():
    """Test AWS configuration and connectivity"""
    print("=" * 60)
    print("AWS Configuration Test")
    print("=" * 60)
    
    try:
        # Load configuration
        print("\n1. Loading AWS Configuration...")
        config = load_aws_config()
        print(f"   ✓ Environment: {config.environment}")
        print(f"   ✓ Region: {config.region}")
        print(f"   ✓ Account ID: {config.account_id or 'Not specified'}")
        
        # Validate configuration
        print("\n2. Validating Configuration...")
        AWSConfigManager.validate_config(config)
        print("   ✓ Configuration validation passed")
        
        # Validate bucket names
        print("\n3. Validating Bucket Names...")
        bucket_errors = AWSConfigValidator.validate_bucket_names(config.buckets)
        if bucket_errors:
            print("   ✗ Bucket name validation failed:")
            for bucket_type, errors in bucket_errors.items():
                print(f"     {bucket_type}: {', '.join(errors)}")
        else:
            print("   ✓ Bucket name validation passed")
            for bucket_type, bucket_name in config.buckets.items():
                print(f"     {bucket_type}: {bucket_name}")
        
        # Validate region
        print("\n4. Validating Region...")
        if AWSConfigValidator.validate_region(config.region):
            print(f"   ✓ Region format valid: {config.region}")
        else:
            print(f"   ✗ Invalid region format: {config.region}")
        
        # Test AWS connectivity
        print("\n5. Testing AWS Connectivity...")
        connectivity_results = await AWSConfigManager.test_aws_connectivity(config)
        
        # Display detailed connectivity results
        for service, result in connectivity_results.items():
            if result['connected'] is True:
                print(f"   ✓ {service.upper()}: Connected")
                if result['details']:
                    for key, value in result['details'].items():
                        if isinstance(value, dict):
                            print(f"     {key}:")
                            for sub_key, sub_value in value.items():
                                print(f"       {sub_key}: {sub_value}")
                        else:
                            print(f"     {key}: {value}")
            elif result['connected'] is False:
                print(f"   ✗ {service.upper()}: Failed")
                if result['error']:
                    print(f"     Error: {result['error']}")
            else:  # None - not configured
                print(f"   - {service.upper()}: Not configured")
                if result['details'].get('message'):
                    print(f"     {result['details']['message']}")
        
        # Test S3 operations if S3 is connected
        if connectivity_results['s3']['connected']:
            print("\n6. Testing S3 Operations...")
            from config.aws_config import AWSS3Manager
            s3_test_result = AWSS3Manager.test_s3_operations(config)
            
            if s3_test_result['success']:
                print("   ✓ S3 Operations: All tests passed")
                for op, result in s3_test_result['operations'].items():
                    status = "✓" if result.get('success') else "✗"
                    print(f"     {status} {op.capitalize()}: {'Success' if result.get('success') else 'Failed'}")
            else:
                print("   ✗ S3 Operations: Some tests failed")
                if s3_test_result['error']:
                    print(f"     Error: {s3_test_result['error']}")
        
        # Test RDS operations if PostgreSQL is connected
        if connectivity_results['rds_postgres']['connected']:
            print("\n7. Testing RDS Database Operations...")
            from config.aws_config import AWSRDSManager
            rds_test_result = AWSRDSManager.test_database_operations(config)
            
            if rds_test_result['success']:
                print("   ✓ Database Operations: All tests passed")
                for op, result in rds_test_result['operations'].items():
                    status = "✓" if result.get('success') else "✗"
                    print(f"     {status} {op.replace('_', ' ').title()}: {'Success' if result.get('success') else 'Failed'}")
            else:
                print("   ✗ Database Operations: Some tests failed")
                if rds_test_result['error']:
                    print(f"     Error: {rds_test_result['error']}")
        
        # Display environment resources
        print(f"\n{8 if connectivity_results['rds_postgres']['connected'] else 7}. Environment Resources...")
        resources = AWSConfigManager.get_environment_resources(config)
        print(f"   Environment: {resources['environment']}")
        print(f"   Region: {resources['region']}")
        print(f"   Account ID: {resources['account_id'] or 'Unknown'}")
        print("   S3 Buckets:")
        for bucket_type, bucket_name in resources['buckets'].items():
            print(f"     {bucket_type}: {bucket_name}")
        
        if resources['rds']:
            print("   RDS Configuration:")
            print(f"     Endpoint: {resources['rds']['endpoint']}")
            print(f"     Database: {resources['rds']['database']}")
            print(f"     Username: {resources['rds']['username']}")
        else:
            print("   RDS: Not configured")
        
        # Test integration with main Config class
        next_section = 9 if connectivity_results['rds_postgres']['connected'] else 8
        print(f"\n{next_section}. Testing Config Integration...")
        main_config_aws = Config.get_aws_config()
        print(f"   ✓ Main Config AWS integration working")
        print(f"   ✓ Environment: {main_config_aws.environment}")
        
        # Overall status
        print("\n" + "=" * 60)
        
        # Calculate overall success
        core_services_connected = (
            connectivity_results['sts']['connected'] and
            connectivity_results['s3']['connected']
        )
        
        rds_configured = connectivity_results['rds_postgres']['connected'] is not None
        rds_connected = connectivity_results['rds_postgres']['connected'] if rds_configured else True
        
        all_connected = core_services_connected and rds_connected
        
        if all_connected and not bucket_errors:
            print("✓ AWS Configuration Test: PASSED")
            print("  All services are properly configured and accessible.")
        elif core_services_connected and not bucket_errors:
            print("✓ AWS Configuration Test: MOSTLY PASSED")
            print("  Core AWS services (STS, S3) are accessible.")
            if not rds_connected:
                print("  RDS connectivity issues detected.")
        else:
            print("✗ AWS Configuration Test: PARTIAL")
            if not core_services_connected:
                print("  Core AWS services are not accessible.")
            if bucket_errors:
                print("  Some bucket names have validation errors.")
        print("=" * 60)
        
        return all_connected and not bucket_errors
        
    except Exception as e:
        print(f"\n✗ AWS Configuration Test: FAILED")
        print(f"  Error: {e}")
        logger.exception("AWS configuration test failed")
        return False


def test_environment_switching():
    """Test switching between different environments"""
    print("\n" + "=" * 60)
    print("Environment Switching Test")
    print("=" * 60)
    
    environments = ['development', 'staging', 'production']
    
    for env in environments:
        try:
            print(f"\nTesting environment: {env}")
            config = load_aws_config(environment=env, validate=False)
            print(f"   ✓ Environment: {config.environment}")
            print(f"   ✓ Buckets generated for {env}:")
            for bucket_type, bucket_name in config.buckets.items():
                print(f"     {bucket_type}: {bucket_name}")
        except Exception as e:
            print(f"   ✗ Failed to load {env} environment: {e}")


if __name__ == "__main__":
    print("Starting AWS Configuration Tests...")
    
    # Test environment switching
    test_environment_switching()
    
    # Test main configuration
    success = asyncio.run(test_aws_configuration())
    
    # Exit with appropriate code
    sys.exit(0 if success else 1)