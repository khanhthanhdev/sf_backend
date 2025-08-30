"""
AWS Health Check API Endpoint

Provides health check endpoints for AWS services and configuration validation.
"""

from fastapi import APIRouter, HTTPException
from typing import Dict, Any
import logging

from config import AWSConfigManager, load_aws_config

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/health", tags=["health"])


@router.get("/aws")
async def health_check_aws() -> Dict[str, Any]:
    """
    Check AWS configuration and service connectivity
    
    Returns:
        Dict containing AWS health status
    """
    try:
        # Load AWS configuration
        config = load_aws_config()
        
        # Validate configuration
        AWSConfigManager.validate_config(config)
        
        # Test connectivity
        connectivity = await AWSConfigManager.test_aws_connectivity(config)
        
        # Get resource information
        resources = AWSConfigManager.get_environment_resources(config)
        
        # Determine overall health
        core_services_healthy = (
            connectivity.get('sts', {}).get('connected', False) and
            connectivity.get('s3', {}).get('connected', False)
        )
        
        rds_configured = connectivity.get('rds_postgres', {}).get('connected') is not None
        rds_healthy = connectivity.get('rds_postgres', {}).get('connected', True) if rds_configured else True
        
        all_services_healthy = core_services_healthy and rds_healthy
        
        # Determine status
        if all_services_healthy:
            status = "healthy"
        elif core_services_healthy:
            status = "degraded"  # Core services work but RDS might have issues
        else:
            status = "unhealthy"
        
        return {
            "status": status,
            "environment": config.environment,
            "region": config.region,
            "account_id": config.account_id,
            "services": {
                service: {
                    "connected": result.get('connected'),
                    "error": result.get('error'),
                    "details": result.get('details', {})
                }
                for service, result in connectivity.items()
            },
            "buckets": resources["buckets"],
            "rds_configured": bool(resources["rds"]),
            "core_services_healthy": core_services_healthy,
            "all_services_healthy": all_services_healthy,
            "timestamp": "2025-08-29T11:26:32Z"  # This would be dynamic in real implementation
        }
        
    except Exception as e:
        logger.error(f"AWS health check failed: {e}")
        raise HTTPException(
            status_code=503,
            detail={
                "status": "unhealthy",
                "error": str(e),
                "message": "AWS configuration or connectivity issue"
            }
        )


@router.get("/aws/config")
async def get_aws_config_info() -> Dict[str, Any]:
    """
    Get AWS configuration information (without sensitive data)
    
    Returns:
        Dict containing non-sensitive AWS configuration info
    """
    try:
        config = load_aws_config()
        resources = AWSConfigManager.get_environment_resources(config)
        
        return {
            "environment": config.environment,
            "region": config.region,
            "account_id": config.account_id,
            "buckets": resources["buckets"],
            "rds": {
                "configured": bool(resources["rds"]),
                "endpoint": resources["rds"]["endpoint"] if resources["rds"] else None,
                "database": resources["rds"]["database"] if resources["rds"] else None
            }
        }
        
    except Exception as e:
        logger.error(f"Failed to get AWS config info: {e}")
        raise HTTPException(
            status_code=500,
            detail={
                "error": str(e),
                "message": "Failed to retrieve AWS configuration"
            }
        )


@router.get("/aws/buckets")
async def validate_bucket_names() -> Dict[str, Any]:
    """
    Validate S3 bucket names according to AWS naming rules
    
    Returns:
        Dict containing bucket validation results
    """
    try:
        from config.aws_config import AWSConfigValidator
        
        config = load_aws_config()
        bucket_errors = AWSConfigValidator.validate_bucket_names(config.buckets)
        
        return {
            "valid": len(bucket_errors) == 0,
            "buckets": config.buckets,
            "errors": bucket_errors,
            "region_valid": AWSConfigValidator.validate_region(config.region)
        }
        
    except Exception as e:
        logger.error(f"Bucket validation failed: {e}")
        raise HTTPException(
            status_code=500,
            detail={
                "error": str(e),
                "message": "Failed to validate bucket names"
            }
        )