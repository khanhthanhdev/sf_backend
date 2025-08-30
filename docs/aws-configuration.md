# AWS Configuration Guide

This guide explains how to configure and use the AWS infrastructure integration in the video generation application.

## Overview

The AWS configuration system provides:
- Environment-specific resource management
- Automatic bucket naming conventions
- Configuration validation and connectivity testing
- Integration with existing application configuration

## Configuration Files

### Environment Variables

Add the following variables to your `.env` file:

```bash
# AWS Credentials (REQUIRED)
AWS_ACCESS_KEY_ID=your_aws_access_key_id_here
AWS_SECRET_ACCESS_KEY=your_aws_secret_access_key_here
AWS_REGION=ap-southeast-1
AWS_ACCOUNT_ID=your_aws_account_id_here

# AWS RDS Database Settings
RDS_ENDPOINT=your_rds_endpoint_here
RDS_DATABASE=t2m_db
RDS_USERNAME=your_rds_username_here
RDS_PASSWORD=your_rds_password_here
```

### Supported Environments

- `development` - For local development
- `staging` - For staging/testing environment  
- `production` - For production deployment

## Bucket Naming Convention

Buckets are automatically named using the pattern:
```
{environment}-t2m-{type}-{region}-{account_id}
```

Example bucket names for development environment:
- `development-t2m-videos-ap-southeast-1-123456789012`
- `development-t2m-code-ap-southeast-1-123456789012`
- `development-t2m-thumbnails-ap-southeast-1-123456789012`
- `development-t2m-temp-ap-southeast-1-123456789012`

## Usage Examples

### Basic Configuration Loading

```python
from config import Config, load_aws_config

# Method 1: Using main Config class
aws_config = Config.get_aws_config()
print(f"Environment: {aws_config.environment}")
print(f"Video bucket: {aws_config.buckets['videos']}")

# Method 2: Direct loading
aws_config = load_aws_config(environment='production')
```

### Testing Configuration

```python
from config import AWSConfigManager

# Validate configuration
config = load_aws_config()
AWSConfigManager.validate_config(config)

# Test connectivity
connectivity = await AWSConfigManager.test_aws_connectivity(config)
print(f"S3 Status: {connectivity['s3']}")
```

### Environment Resources

```python
from config import AWSConfigManager

config = load_aws_config()
resources = AWSConfigManager.get_environment_resources(config)
print(f"Buckets: {resources['buckets']}")
```

## Testing

### Run Configuration Tests

```bash
# Test AWS configuration
python scripts/test_aws_config.py

# Run example usage
python examples/aws_config_example.py
```

### Test Output

The test script will validate:
- Configuration loading for all environments
- Bucket name validation
- AWS region format validation
- AWS service connectivity
- Integration with main Config class

## Configuration Classes

### AWSConfig

Data class containing all AWS configuration:
- `access_key_id`: AWS access key
- `secret_access_key`: AWS secret key
- `region`: AWS region
- `buckets`: Dictionary of bucket names by type
- `rds_endpoint`: RDS database endpoint
- `environment`: Current environment

### AWSConfigManager

Static methods for configuration management:
- `load_config()`: Load configuration from environment
- `validate_config()`: Validate configuration
- `test_aws_connectivity()`: Test AWS service connectivity
- `get_environment_resources()`: Get resource information

### AWSConfigValidator

Validation utilities:
- `validate_bucket_names()`: Validate S3 bucket names
- `validate_region()`: Validate AWS region format

## Error Handling

The configuration system handles various error scenarios:

- **Missing credentials**: Raises `ValueError` with clear message
- **Invalid environment**: Validates against supported environments
- **Connectivity issues**: Provides detailed connectivity status
- **Invalid bucket names**: Validates against AWS naming rules

## Integration Points

The AWS configuration integrates with:
- Main application configuration (`Config` class)
- Environment variable management
- Service factory pattern (for future service implementations)
- Health check systems

## Security Considerations

- Store AWS credentials securely (use IAM roles in production)
- Use least-privilege IAM policies
- Enable CloudTrail for audit logging
- Use encryption at rest and in transit
- Rotate credentials regularly

## Troubleshooting

### Common Issues

1. **"AWS credentials not found"**
   - Ensure `AWS_ACCESS_KEY_ID` and `AWS_SECRET_ACCESS_KEY` are set
   - Check `.env` file is loaded correctly

2. **"Invalid environment"**
   - Use one of: `development`, `staging`, `production`
   - Check `ENVIRONMENT` variable

3. **"Could not connect to endpoint"**
   - Verify AWS region is correct
   - Check internet connectivity
   - Verify AWS credentials have proper permissions

4. **"Bucket name validation failed"**
   - Bucket names must be 3-63 characters
   - Use only lowercase letters, numbers, hyphens
   - Cannot start/end with hyphen or period

### Debug Mode

Set `DEBUG=true` in environment to enable detailed logging:

```bash
DEBUG=true python scripts/test_aws_config.py
```

## Next Steps

After configuring AWS settings:

1. Implement S3 file service integration
2. Set up RDS database connections
3. Create service factory for AWS services
4. Add monitoring and logging integration
5. Implement data migration utilities