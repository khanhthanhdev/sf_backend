# Client SDK Generation Guide

This guide explains how to generate and use client SDKs for the Video Generation API.

## Overview

The Video Generation API supports automatic client SDK generation in multiple programming languages using OpenAPI Generator. This allows developers to quickly integrate with the API using idiomatic code in their preferred language.

## Supported Languages

- **TypeScript/JavaScript** - Modern TypeScript client with fetch API
- **Python** - Python client with requests library
- **Java** - Java client with OkHttp and Gson
- **C#** - .NET Standard 2.0 compatible client
- **Go** - Go client with native HTTP library
- **PHP** - PHP client with Guzzle HTTP
- **Ruby** - Ruby client with Faraday HTTP

## Prerequisites

### Required Tools

1. **Node.js and npm** - For OpenAPI Generator CLI
2. **OpenAPI Generator CLI** - For generating clients
3. **Language-specific tools** (optional, for testing):
   - TypeScript: Node.js, npm
   - Python: Python 3.7+, pip
   - Java: JDK 8+, Maven
   - C#: .NET Core SDK
   - Go: Go 1.16+
   - PHP: PHP 7.4+, Composer
   - Ruby: Ruby 2.7+, Bundler

### Installation

Install OpenAPI Generator CLI:

```bash
npm install -g @openapitools/openapi-generator-cli
```

## Quick Start

### Using the Python Script

The easiest way to generate clients is using the provided Python script:

```bash
# Generate all supported clients
python scripts/generate_clients.py

# Generate specific languages
python scripts/generate_clients.py --languages typescript python

# Use custom API URL
python scripts/generate_clients.py --api-url https://api.example.com

# Custom output directory
python scripts/generate_clients.py --output-dir my_clients
```

### Using the Shell Script

Alternatively, use the shell script:

```bash
# Generate all clients
./scripts/generate_clients.sh

# Generate specific languages
./scripts/generate_clients.sh typescript python java

# Use custom API URL
./scripts/generate_clients.sh --api-url https://api.example.com typescript
```

### Manual Generation

For manual control, use OpenAPI Generator CLI directly:

```bash
# Fetch OpenAPI specification
curl -o openapi.json http://localhost:8000/openapi.json

# Generate TypeScript client
openapi-generator-cli generate \
  -i openapi.json \
  -g typescript-fetch \
  -o clients/typescript \
  --package-name video-api-client

# Generate Python client
openapi-generator-cli generate \
  -i openapi.json \
  -g python \
  -o clients/python \
  --package-name video_api_client
```

## Generated Client Structure

Each generated client includes:

```
clients/
├── typescript/
│   ├── src/
│   │   ├── apis/
│   │   ├── models/
│   │   └── index.ts
│   ├── package.json
│   ├── README.md
│   └── example.ts
├── python/
│   ├── video_api_client/
│   │   ├── api/
│   │   ├── models/
│   │   └── __init__.py
│   ├── setup.py
│   ├── README.md
│   └── example.py
└── ...
```

## Usage Examples

### TypeScript

```typescript
import { Configuration, VideosApi } from 'video-api-client';

const config = new Configuration({
  basePath: 'https://api.example.com',
  accessToken: 'your-clerk-session-token'
});

const videosApi = new VideosApi(config);

async function generateVideo() {
  try {
    const jobResponse = await videosApi.createVideoGenerationJob({
      configuration: {
        topic: "Pythagorean Theorem",
        context: "Explain the mathematical proof",
        quality: "medium",
        use_rag: true
      }
    });
    
    console.log('Job created:', jobResponse.job_id);
    
    // Poll for completion
    let status = 'queued';
    while (status !== 'completed' && status !== 'failed') {
      await new Promise(resolve => setTimeout(resolve, 5000));
      
      const statusResponse = await videosApi.getVideoJobStatus(jobResponse.job_id);
      status = statusResponse.status;
      
      console.log(`Status: ${status} (${statusResponse.progress.percentage}%)`);
    }
    
    if (status === 'completed') {
      const videoBlob = await videosApi.downloadVideoFile(jobResponse.job_id);
      console.log('Video downloaded');
    }
    
  } catch (error) {
    console.error('Error:', error);
  }
}
```

### Python

```python
import time
from video_api_client import Configuration, ApiClient, VideosApi
from video_api_client.models import JobCreateRequest, JobConfiguration

configuration = Configuration(
    host="https://api.example.com",
    access_token="your-clerk-session-token"
)

with ApiClient(configuration) as api_client:
    videos_api = VideosApi(api_client)
    
    try:
        # Create job
        job_request = JobCreateRequest(
            configuration=JobConfiguration(
                topic="Pythagorean Theorem",
                context="Explain the mathematical proof",
                quality="medium",
                use_rag=True
            )
        )
        
        job_response = videos_api.create_video_generation_job(job_request)
        print(f"Job created: {job_response.job_id}")
        
        # Poll for completion
        status = "queued"
        while status not in ["completed", "failed"]:
            time.sleep(5)
            
            status_response = videos_api.get_video_job_status(job_response.job_id)
            status = status_response.status
            
            print(f"Status: {status} ({status_response.progress.percentage}%)")
        
        if status == "completed":
            video_data = videos_api.download_video_file(job_response.job_id)
            with open("video.mp4", "wb") as f:
                f.write(video_data)
            print("Video downloaded")
            
    except Exception as e:
        print(f"Error: {e}")
```

### Java

```java
import com.example.videoapiclient.ApiClient;
import com.example.videoapiclient.Configuration;
import com.example.videoapiclient.api.VideosApi;
import com.example.videoapiclient.model.*;

public class VideoApiExample {
    public static void main(String[] args) {
        ApiClient client = Configuration.getDefaultApiClient();
        client.setBasePath("https://api.example.com");
        client.setAccessToken("your-clerk-session-token");
        
        VideosApi videosApi = new VideosApi(client);
        
        try {
            JobConfiguration config = new JobConfiguration()
                .topic("Pythagorean Theorem")
                .context("Explain the mathematical proof")
                .quality(VideoQuality.MEDIUM)
                .useRag(true);
            
            JobCreateRequest request = new JobCreateRequest().configuration(config);
            JobResponse jobResponse = videosApi.createVideoGenerationJob(request);
            
            System.out.println("Job created: " + jobResponse.getJobId());
            
            // Poll for completion
            String status = "queued";
            while (!"completed".equals(status) && !"failed".equals(status)) {
                Thread.sleep(5000);
                
                JobStatusResponse statusResponse = videosApi.getVideoJobStatus(jobResponse.getJobId());
                status = statusResponse.getStatus().getValue();
                
                System.out.println("Status: " + status + " (" + 
                    statusResponse.getProgress().getPercentage() + "%)");
            }
            
            if ("completed".equals(status)) {
                System.out.println("Video generation completed!");
            }
            
        } catch (Exception e) {
            System.err.println("Error: " + e.getMessage());
        }
    }
}
```

## Authentication

All clients support Clerk authentication. Set your session token when configuring the client:

### TypeScript
```typescript
const config = new Configuration({
  accessToken: 'your-clerk-session-token'
});
```

### Python
```python
configuration.access_token = 'your-clerk-session-token'
```

### Java
```java
client.setAccessToken("your-clerk-session-token");
```

## Error Handling

All clients provide structured error handling:

### TypeScript
```typescript
try {
  const response = await api.createVideoGenerationJob(request);
} catch (error) {
  if (error.status === 422) {
    console.error('Validation error:', error.body);
  } else if (error.status === 429) {
    console.error('Rate limit exceeded');
  } else {
    console.error('API error:', error);
  }
}
```

### Python
```python
from video_api_client.exceptions import ApiException

try:
    response = api.create_video_generation_job(request)
except ApiException as e:
    if e.status == 422:
        print(f"Validation error: {e.body}")
    elif e.status == 429:
        print("Rate limit exceeded")
    else:
        print(f"API error: {e}")
```

## Testing Generated Clients

Use the provided testing script to validate generated clients:

```bash
# Test all generated clients
python scripts/test_clients.py

# Test with custom API URL
python scripts/test_clients.py --api-url https://api.example.com

# Save test results
python scripts/test_clients.py --output-file test_results.json

# Verbose output
python scripts/test_clients.py --verbose
```

The test script validates:
- Client structure and files
- Build/compilation success
- Import/usage capability
- API connectivity
- Basic functionality

## Customization

### Custom Templates

Create custom templates in the `templates/` directory:

```
templates/
├── typescript/
│   ├── api.mustache
│   ├── model.mustache
│   └── README.mustache
├── python/
│   ├── api.mustache
│   └── model.mustache
└── ...
```

### Configuration File

Modify `openapi-generator-config.yaml` to customize generation:

```yaml
typescript:
  generatorName: typescript-fetch
  additionalProperties:
    npmName: my-custom-client
    supportsES6: true
    withInterfaces: true
```

### Custom Properties

Pass additional properties during generation:

```bash
openapi-generator-cli generate \
  -i openapi.json \
  -g typescript-fetch \
  -o clients/typescript \
  --additional-properties=npmName=my-client,supportsES6=true
```

## Publishing Clients

### NPM (TypeScript/JavaScript)

```bash
cd clients/typescript
npm publish
```

### PyPI (Python)

```bash
cd clients/python
python setup.py sdist bdist_wheel
twine upload dist/*
```

### Maven Central (Java)

```bash
cd clients/java
mvn deploy
```

### NuGet (C#)

```bash
cd clients/csharp
dotnet pack
dotnet nuget push *.nupkg
```

## Troubleshooting

### Common Issues

1. **OpenAPI Generator not found**
   ```bash
   npm install -g @openapitools/openapi-generator-cli
   ```

2. **API server not running**
   ```bash
   # Start the API server first
   python -m uvicorn src.app.main:app --reload
   ```

3. **Build failures**
   - Check language-specific requirements
   - Verify generated code syntax
   - Review error messages in build logs

4. **Import errors**
   - Ensure proper installation
   - Check Python path and virtual environments
   - Verify package structure

### Debug Mode

Enable debug output for troubleshooting:

```bash
# Python script
python scripts/generate_clients.py --verbose

# OpenAPI Generator
openapi-generator-cli generate \
  --verbose \
  --debug-operations \
  -i openapi.json \
  -g typescript-fetch \
  -o clients/typescript
```

### Validation

Validate OpenAPI specification before generation:

```bash
# Using OpenAPI Generator
openapi-generator-cli validate -i openapi.json

# Using Swagger Editor online
# Visit: https://editor.swagger.io/
```

## Best Practices

1. **Version Management**
   - Tag client versions with API versions
   - Maintain backward compatibility
   - Document breaking changes

2. **Testing**
   - Test clients against real API
   - Include integration tests
   - Validate error handling

3. **Documentation**
   - Include usage examples
   - Document authentication setup
   - Provide troubleshooting guides

4. **Distribution**
   - Use semantic versioning
   - Publish to appropriate package managers
   - Maintain changelogs

## Support

For issues with client generation:

- Check the [OpenAPI Generator documentation](https://openapi-generator.tech/)
- Review API documentation at `/docs`
- Contact support at support@example.com
- File issues on GitHub

## Contributing

To contribute to client generation:

1. Fork the repository
2. Create custom templates or improve scripts
3. Test with multiple languages
4. Submit pull request with documentation

## License

Generated clients inherit the same license as the API project (MIT License).