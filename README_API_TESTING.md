# T2M API Testing Guide

This directory contains comprehensive test scripts for the T2M API endpoints.

## Files

- `test_api_endpoints.py` - Main test script with full endpoint coverage
- `run_api_tests.py` - Simple runner using configuration file
- `test_config.json` - Configuration file for API settings
- `requirements-test.txt` - Python dependencies for testing

## Quick Start

### 1. Install Dependencies

```bash
pip install -r requirements-test.txt
```

### 2. Configure API Settings

Edit `test_config.json` with your API details:

```json
{
  "api_config": {
    "base_url": "https://your-api-domain.com/api/v1",
    "token": "your-actual-bearer-token"
  }
}
```

### 3. Run Tests

**Option A: Using configuration file**
```bash
python run_api_tests.py
```

**Option B: Direct command line**
```bash
python test_api_endpoints.py --base-url https://your-api-domain.com/api/v1 --token your-token
```

**Option C: Token from file**
```bash
echo "your-token-here" > token.txt
python test_api_endpoints.py --base-url https://your-api-domain.com/api/v1 --token-file token.txt
```

## Test Coverage

The test script covers all major API endpoints:

### 🔓 Public Endpoints (No Auth Required)
- `GET /auth/health` - Authentication service health
- `GET /system/health` - System health check

### 🔐 Authentication Endpoints
- `GET /auth/status` - Authentication status
- `GET /auth/profile` - User profile
- `GET /auth/permissions` - User permissions
- `GET /auth/test/protected` - Protected endpoint test
- `GET /auth/test/verified` - Verified user test
- `POST /auth/verify` - Token verification

### 📁 File Management Endpoints
- `POST /files/upload` - Single file upload
- `GET /files` - List files with pagination
- `GET /files/{id}` - File details
- `GET /files/{id}/metadata` - File metadata
- `GET /files/{id}/thumbnail` - File thumbnail
- `GET /files/stats` - File statistics
- `DELETE /files/{id}` - File deletion (cleanup)

### ⚙️ Job Management Endpoints
- `GET /jobs` - List jobs
- `GET /jobs/{id}` - Job details
- `GET /jobs/{id}/logs` - Job logs
- `POST /jobs/{id}/cancel` - Cancel job (cleanup)
- `DELETE /jobs/{id}` - Delete job (cleanup)

### 🖥️ System Monitoring Endpoints
- `GET /system/metrics` - System metrics
- `GET /system/queue` - Queue status
- `GET /system/cache` - Cache information
- `GET /system/cache/metrics` - Cache metrics
- `GET /system/cache/report` - Cache report
- `GET /system/performance` - Performance summary
- `GET /system/connections` - Connection statistics
- `GET /system/async` - Async statistics
- `GET /system/deduplication` - Deduplication statistics

### 🎥 Video Processing Endpoints
- `POST /videos/generate` - Generate video
- `GET /videos/{id}/status` - Video job status
- `GET /videos/{id}/metadata` - Video metadata
- `GET /videos/{id}/thumbnail` - Video thumbnail

## Test Results

After running tests, you'll get:

1. **Console output** with real-time test results
2. **Summary statistics** showing pass/fail rates
3. **JSON report** saved to `api_test_results.json`

### Example Output

```
🚀 Starting T2M API Endpoint Tests
Base URL: https://api.example.com/api/v1
Token: Provided

🔓 Testing Public Endpoints
✅ PASS GET /auth/health
    Status: 200
✅ PASS GET /system/health
    Status: 200

🔐 Testing Authentication Endpoints
✅ PASS GET /auth/status
    Status: 200
✅ PASS GET /auth/profile
    Status: 200

📊 TEST SUMMARY
==================================================
Total Tests: 25
Passed: 23 ✅
Failed: 2 ❌
Success Rate: 92.0%
```

## Test Features

### 🧹 Automatic Cleanup
- Deletes uploaded test files
- Cancels/deletes created jobs
- Prevents resource accumulation

### 📊 Comprehensive Reporting
- Real-time console feedback
- Detailed JSON results file
- Pass/fail statistics
- Error details for debugging

### 🔧 Flexible Configuration
- Command line arguments
- Configuration file support
- Token file support
- Environment variable support

### 🛡️ Error Handling
- Network timeout handling
- Graceful failure handling
- Detailed error reporting
- Resource cleanup on failure

## Advanced Usage

### Testing Specific Endpoints

You can modify the test script to focus on specific endpoint groups:

```python
# Only test public endpoints
tester.test_public_endpoints()

# Only test file operations
tester.test_file_endpoints()

# Only test system monitoring
tester.test_system_endpoints()
```

### Custom Test Data

Modify `test_config.json` to customize test parameters:

```json
{
  "test_data": {
    "video_generation": {
      "prompt": "Your custom test prompt",
      "duration": 10,
      "quality": "1080p"
    }
  }
}
```

### Environment Variables

You can also use environment variables:

```bash
export T2M_API_URL="https://your-api-domain.com/api/v1"
export T2M_API_TOKEN="your-token-here"
python test_api_endpoints.py --base-url $T2M_API_URL --token $T2M_API_TOKEN
```

## Troubleshooting

### Common Issues

**Connection Errors**
- Verify the base URL is correct
- Check network connectivity
- Ensure API server is running

**Authentication Errors**
- Verify token is valid and not expired
- Check token format (should be just the token, not "Bearer token")
- Ensure user has required permissions

**Rate Limiting**
- Tests may hit rate limits on busy servers
- Add delays between requests if needed
- Run tests during off-peak hours

**Resource Cleanup Failures**
- Some resources may not be cleaned up if tests fail
- Manually delete test files/jobs if needed
- Check API logs for cleanup issues

### Debug Mode

For more detailed debugging, modify the test script to add verbose logging:

```python
import logging
logging.basicConfig(level=logging.DEBUG)
```

## Integration with CI/CD

The test script returns appropriate exit codes for CI/CD integration:

```bash
# Run tests and capture exit code
python test_api_endpoints.py --base-url $API_URL --token $API_TOKEN
if [ $? -eq 0 ]; then
    echo "All tests passed"
else
    echo "Some tests failed"
    exit 1
fi
```

## Contributing

To add new test cases:

1. Add the endpoint to the appropriate test method
2. Follow the existing pattern for error handling
3. Add cleanup logic if the endpoint creates resources
4. Update this README with the new endpoint coverage