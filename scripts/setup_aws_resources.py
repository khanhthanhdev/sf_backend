#!/usr/bin/env python3
"""
AWS Resources Setup Script

This script sets up the required AWS resources for the video generation application,
including S3 buckets and testing connectivity.
"""

import asyncio
import sys
import logging
from pathlib import Path

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from config import load_aws_config, AWSS3Manager, AWSRDSManager, AWSConfigManager

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


async def setup_s3_buckets():
    """Set up S3 buckets for the application"""
    print("=" * 60)
    print("S3 Buckets Setup")
    print("=" * 60)
    
    try:
        config = load_aws_config()
        print(f"Setting up S3 buckets for environment: {config.environment}")
        print(f"Region: {config.region}")
        
        # Create buckets
        print("\n1. Creating Application Buckets...")
        creation_results = AWSS3Manager.create_application_buckets(config)
        
        for bucket_type, result in creation_results.items():
            if result['created']:
                print(f"   ✓ Created {bucket_type} bucket: {config.buckets[bucket_type]}")
            elif result['existed']:
                print(f"   ✓ {bucket_type} bucket already exists: {config.buckets[bucket_type]}")
            else:
                print(f"   ✗ Failed to create {bucket_type} bucket: {result.get('error', 'Unknown error')}")
        
        # Test S3 operations after bucket creation
        print("\n2. Testing S3 Operations...")
        s3_test_result = AWSS3Manager.test_s3_operations(config)
        
        if s3_test_result['success']:
            print("   ✓ S3 operations test successful!")
            for op, details in s3_test_result['operations'].items():
                status = "✓" if details.get('success') else "✗"
                print(f"     {status} {op.capitalize()}: {'Success' if details.get('success') else 'Failed'}")
        else:
            print(f"   ✗ S3 operations test failed: {s3_test_result.get('error', 'Unknown error')}")
            
        return creation_results, s3_test_result
        
    except Exception as e:
        print(f"Error setting up S3 buckets: {e}")
        logger.exception("S3 setup failed")
        return None, None


async def test_rds_connectivity():
    """Test RDS connectivity and provide troubleshooting info"""
    print("\n" + "=" * 60)
    print("RDS Connectivity Test")
    print("=" * 60)
    
    try:
        config = load_aws_config()
        
        # Test RDS API connectivity
        print("1. Testing RDS API...")
        connectivity = await AWSConfigManager.test_aws_connectivity(config)
        rds_api_result = connectivity.get('rds_api', {})
        
        if rds_api_result.get('connected'):
            print("   ✓ RDS API connected successfully")
            instance_info = rds_api_result.get('details', {}).get('target_instance', {})
            if instance_info:
                print(f"   Database Instance: {instance_info.get('identifier')}")
                print(f"   Status: {instance_info.get('status')}")
                print(f"   Engine: {instance_info.get('engine')} {instance_info.get('engine_version')}")
                print(f"   Endpoint: {instance_info.get('endpoint')}")
                print(f"   Port: {instance_info.get('port')}")
                print(f"   Publicly Accessible: {instance_info.get('publicly_accessible')}")
                print(f"   Availability Zone: {instance_info.get('availability_zone')}")
        else:
            print(f"   ✗ RDS API connection failed: {rds_api_result.get('error')}")
            return
        
        # Test PostgreSQL connectivity
        print("\n2. Testing PostgreSQL Database Connection...")
        rds_postgres_result = connectivity.get('rds_postgres', {})
        
        if rds_postgres_result.get('connected'):
            print("   ✓ PostgreSQL connection successful!")
            details = rds_postgres_result.get('details', {})
            
            if 'server_version' in details:
                print(f"   Server Version: {details['server_version'][:100]}...")
            if 'database_size' in details:
                print(f"   Database Size: {details['database_size']}")
            if 'connection_info' in details:
                conn_info = details['connection_info']
                print(f"   Connection: {conn_info.get('user')}@{conn_info.get('host')}:{conn_info.get('port')}/{conn_info.get('database')}")
                print(f"   Backend PID: {conn_info.get('backend_pid')}")
            
            # Test database operations
            print("\n3. Testing Database Operations...")
            db_test_result = AWSRDSManager.test_database_operations(config)
            
            if db_test_result['success']:
                print("   ✓ Database operations test successful!")
                for op, details in db_test_result['operations'].items():
                    status = "✓" if details.get('success') else "✗"
                    print(f"     {status} {op.replace('_', ' ').title()}: {'Success' if details.get('success') else 'Failed'}")
            else:
                print(f"   ✗ Database operations test failed: {db_test_result.get('error')}")
                
        else:
            print(f"   ✗ PostgreSQL connection failed: {rds_postgres_result.get('error')}")
            print("\n   Troubleshooting Tips:")
            print("   1. Check if RDS instance is publicly accessible")
            print("   2. Verify security group allows inbound connections on port 5432")
            print("   3. Check VPC and subnet configuration")
            print("   4. Ensure your IP is whitelisted in security groups")
            print("   5. Verify RDS endpoint hostname resolution")
            
    except Exception as e:
        print(f"Error testing RDS connectivity: {e}")
        logger.exception("RDS connectivity test failed")


async def main():
    """Main setup function"""
    print("AWS Resources Setup")
    print("Setting up AWS resources for the video generation application...")
    
    try:
        # Setup S3 buckets
        bucket_results, s3_test = await setup_s3_buckets()
        
        # Test RDS connectivity
        await test_rds_connectivity()
        
        # Summary
        print("\n" + "=" * 60)
        print("Setup Summary")
        print("=" * 60)
        
        if bucket_results:
            buckets_created = sum(1 for result in bucket_results.values() if result['created'])
            buckets_existed = sum(1 for result in bucket_results.values() if result['existed'])
            buckets_failed = sum(1 for result in bucket_results.values() if result.get('error'))
            
            print(f"S3 Buckets:")
            print(f"  Created: {buckets_created}")
            print(f"  Already existed: {buckets_existed}")
            print(f"  Failed: {buckets_failed}")
            
            if s3_test and s3_test['success']:
                print(f"  Operations test: ✓ Passed")
            else:
                print(f"  Operations test: ✗ Failed")
        
        print("\nNext Steps:")
        print("1. If RDS connection failed, check security group settings")
        print("2. Run the main connectivity test: python scripts/test_aws_config.py")
        print("3. Use the health check API: /health/aws")
        
    except Exception as e:
        print(f"Setup failed: {e}")
        logger.exception("Setup failed")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())