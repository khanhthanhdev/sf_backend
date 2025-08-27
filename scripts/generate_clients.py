#!/usr/bin/env python3
"""
Client SDK generation script for FastAPI Video Generation Backend.

This script generates client SDKs in multiple languages using OpenAPI Generator.
It fetches the OpenAPI specification from the running API and generates clients
for TypeScript, Python, Java, C#, Go, PHP, and Ruby.
"""

import os
import sys
import json
import subprocess
import argparse
import requests
from pathlib import Path
from typing import Dict, List, Optional
import tempfile
import shutil


class ClientGenerator:
    """Client SDK generator using OpenAPI Generator."""
    
    SUPPORTED_LANGUAGES = {
        "typescript": {
            "generator": "typescript-fetch",
            "output_dir": "clients/typescript",
            "package_name": "video-api-client",
            "additional_properties": {
                "npmName": "video-api-client",
                "npmVersion": "1.0.0",
                "supportsES6": "true",
                "withInterfaces": "true",
                "typescriptThreePlus": "true"
            }
        },
        "python": {
            "generator": "python",
            "output_dir": "clients/python",
            "package_name": "video_api_client",
            "additional_properties": {
                "packageName": "video_api_client",
                "projectName": "video-api-client",
                "packageVersion": "1.0.0",
                "packageUrl": "https://github.com/example/video-api-client-python"
            }
        },
        "java": {
            "generator": "java",
            "output_dir": "clients/java",
            "package_name": "com.example.videoapiclient",
            "additional_properties": {
                "groupId": "com.example",
                "artifactId": "video-api-client",
                "artifactVersion": "1.0.0",
                "library": "okhttp-gson",
                "java8": "true"
            }
        },
        "csharp": {
            "generator": "csharp",
            "output_dir": "clients/csharp",
            "package_name": "VideoApiClient",
            "additional_properties": {
                "packageName": "VideoApiClient",
                "packageVersion": "1.0.0",
                "clientPackage": "VideoApiClient",
                "packageCompany": "Example Inc",
                "packageAuthors": "API Team",
                "packageCopyright": "Copyright 2024",
                "packageDescription": "Video Generation API Client for .NET",
                "targetFramework": "netstandard2.0"
            }
        },
        "go": {
            "generator": "go",
            "output_dir": "clients/go",
            "package_name": "videoapiclient",
            "additional_properties": {
                "packageName": "videoapiclient",
                "packageVersion": "1.0.0",
                "packageUrl": "github.com/example/video-api-client-go"
            }
        },
        "php": {
            "generator": "php",
            "output_dir": "clients/php",
            "package_name": "VideoApiClient",
            "additional_properties": {
                "packageName": "VideoApiClient",
                "composerVendorName": "example",
                "composerProjectName": "video-api-client",
                "packageVersion": "1.0.0"
            }
        },
        "ruby": {
            "generator": "ruby",
            "output_dir": "clients/ruby",
            "package_name": "video_api_client",
            "additional_properties": {
                "gemName": "video_api_client",
                "gemVersion": "1.0.0",
                "gemHomepage": "https://github.com/example/video-api-client-ruby",
                "gemSummary": "Video Generation API Client for Ruby",
                "gemDescription": "Ruby client library for the Video Generation API"
            }
        }
    }
    
    def __init__(self, api_url: str = "http://localhost:8000", output_base_dir: str = "generated_clients"):
        self.api_url = api_url.rstrip("/")
        self.output_base_dir = Path(output_base_dir)
        self.openapi_spec_path: Optional[Path] = None
        
    def fetch_openapi_spec(self) -> Path:
        """Fetch OpenAPI specification from the API."""
        try:
            print(f"Fetching OpenAPI specification from {self.api_url}/openapi.json")
            response = requests.get(f"{self.api_url}/openapi.json", timeout=30)
            response.raise_for_status()
            
            # Create temporary file for OpenAPI spec
            temp_file = tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False)
            json.dump(response.json(), temp_file, indent=2)
            temp_file.close()
            
            self.openapi_spec_path = Path(temp_file.name)
            print(f"OpenAPI specification saved to {self.openapi_spec_path}")
            return self.openapi_spec_path
            
        except requests.RequestException as e:
            print(f"Error fetching OpenAPI specification: {e}")
            sys.exit(1)
    
    def check_openapi_generator(self) -> bool:
        """Check if OpenAPI Generator is available."""
        try:
            result = subprocess.run(
                ["openapi-generator-cli", "version"],
                capture_output=True,
                text=True,
                timeout=10
            )
            if result.returncode == 0:
                print(f"OpenAPI Generator found: {result.stdout.strip()}")
                return True
            else:
                print("OpenAPI Generator not found or not working properly")
                return False
        except (subprocess.TimeoutExpired, FileNotFoundError):
            print("OpenAPI Generator CLI not found")
            return False
    
    def install_openapi_generator(self) -> bool:
        """Install OpenAPI Generator CLI using npm."""
        try:
            print("Installing OpenAPI Generator CLI...")
            result = subprocess.run(
                ["npm", "install", "-g", "@openapitools/openapi-generator-cli"],
                capture_output=True,
                text=True,
                timeout=120
            )
            if result.returncode == 0:
                print("OpenAPI Generator CLI installed successfully")
                return True
            else:
                print(f"Failed to install OpenAPI Generator CLI: {result.stderr}")
                return False
        except (subprocess.TimeoutExpired, FileNotFoundError):
            print("npm not found. Please install Node.js and npm first.")
            return False
    
    def generate_client(self, language: str, custom_config: Optional[Dict] = None) -> bool:
        """Generate client SDK for specified language."""
        if language not in self.SUPPORTED_LANGUAGES:
            print(f"Unsupported language: {language}")
            return False
        
        config = self.SUPPORTED_LANGUAGES[language].copy()
        if custom_config:
            config.update(custom_config)
        
        output_dir = self.output_base_dir / config["output_dir"]
        output_dir.mkdir(parents=True, exist_ok=True)
        
        # Build OpenAPI Generator command
        cmd = [
            "openapi-generator-cli",
            "generate",
            "-i", str(self.openapi_spec_path),
            "-g", config["generator"],
            "-o", str(output_dir),
            "--package-name", config["package_name"]
        ]
        
        # Add additional properties
        if "additional_properties" in config:
            for key, value in config["additional_properties"].items():
                cmd.extend(["--additional-properties", f"{key}={value}"])
        
        # Add global properties for better client generation
        cmd.extend([
            "--global-property",
            "models,apis,supportingFiles,modelTests,apiTests,modelDocs,apiDocs"
        ])
        
        print(f"Generating {language} client...")
        print(f"Command: {' '.join(cmd)}")
        
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
            if result.returncode == 0:
                print(f"✅ {language} client generated successfully in {output_dir}")
                self._post_process_client(language, output_dir)
                return True
            else:
                print(f"❌ Failed to generate {language} client:")
                print(result.stderr)
                return False
        except subprocess.TimeoutExpired:
            print(f"❌ Timeout generating {language} client")
            return False
    
    def _post_process_client(self, language: str, output_dir: Path) -> None:
        """Post-process generated client with additional files and documentation."""
        # Create README for the client
        readme_content = self._generate_client_readme(language)
        readme_path = output_dir / "README.md"
        readme_path.write_text(readme_content)
        
        # Create example usage file
        example_content = self._generate_client_example(language)
        if example_content:
            example_extensions = {
                "typescript": "ts",
                "python": "py",
                "java": "java",
                "csharp": "cs",
                "go": "go",
                "php": "php",
                "ruby": "rb"
            }
            extension = example_extensions.get(language, "txt")
            example_path = output_dir / f"example.{extension}"
            example_path.write_text(example_content)
        
        # Language-specific post-processing
        if language == "typescript":
            self._post_process_typescript(output_dir)
        elif language == "python":
            self._post_process_python(output_dir)
    
    def _post_process_typescript(self, output_dir: Path) -> None:
        """Post-process TypeScript client."""
        # Create package.json if it doesn't exist
        package_json_path = output_dir / "package.json"
        if not package_json_path.exists():
            package_json = {
                "name": "video-api-client",
                "version": "1.0.0",
                "description": "TypeScript client for Video Generation API",
                "main": "dist/index.js",
                "types": "dist/index.d.ts",
                "scripts": {
                    "build": "tsc",
                    "test": "jest",
                    "lint": "eslint src/**/*.ts"
                },
                "dependencies": {
                    "node-fetch": "^2.6.7"
                },
                "devDependencies": {
                    "typescript": "^4.9.0",
                    "@types/node": "^18.0.0",
                    "jest": "^29.0.0",
                    "@types/jest": "^29.0.0",
                    "eslint": "^8.0.0",
                    "@typescript-eslint/eslint-plugin": "^5.0.0",
                    "@typescript-eslint/parser": "^5.0.0"
                },
                "keywords": ["video", "api", "client", "typescript"],
                "author": "API Team",
                "license": "MIT"
            }
            package_json_path.write_text(json.dumps(package_json, indent=2))
    
    def _post_process_python(self, output_dir: Path) -> None:
        """Post-process Python client."""
        # Create setup.py if it doesn't exist
        setup_py_path = output_dir / "setup.py"
        if not setup_py_path.exists():
            setup_py_content = '''
from setuptools import setup, find_packages

setup(
    name="video-api-client",
    version="1.0.0",
    description="Python client for Video Generation API",
    long_description=open("README.md").read(),
    long_description_content_type="text/markdown",
    author="API Team",
    author_email="api-team@example.com",
    url="https://github.com/example/video-api-client-python",
    packages=find_packages(),
    install_requires=[
        "requests>=2.25.0",
        "urllib3>=1.26.0",
        "python-dateutil>=2.8.0"
    ],
    extras_require={
        "dev": [
            "pytest>=6.0.0",
            "pytest-cov>=2.10.0",
            "black>=21.0.0",
            "flake8>=3.8.0",
            "mypy>=0.800"
        ]
    },
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.7",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
    ],
    python_requires=">=3.7",
)
'''
            setup_py_path.write_text(setup_py_content.strip())
    
    def _generate_client_readme(self, language: str) -> str:
        """Generate README content for client SDK."""
        return f"""# Video Generation API Client - {language.title()}

This is an auto-generated client library for the Video Generation API.

## Installation

### {language.title()}
{self._get_installation_instructions(language)}

## Quick Start

```{self._get_code_block_language(language)}
{self._get_quick_start_example(language)}
```

## Authentication

This API uses Clerk authentication. You need to provide a valid Clerk session token:

```{self._get_code_block_language(language)}
{self._get_auth_example(language)}
```

## API Documentation

For complete API documentation, visit: https://docs.example.com

## Examples

See `example.{self._get_file_extension(language)}` for more usage examples.

## Support

- GitHub Issues: https://github.com/example/video-api-client-{language}/issues
- Documentation: https://docs.example.com
- Email: support@example.com

## License

MIT License - see LICENSE file for details.
"""
    
    def _generate_client_example(self, language: str) -> Optional[str]:
        """Generate example usage code for client SDK."""
        examples = {
            "typescript": '''
import { Configuration, VideosApi, JobsApi } from './src';

// Configure the client
const config = new Configuration({
  basePath: 'https://api.example.com',
  accessToken: 'your-clerk-session-token'
});

const videosApi = new VideosApi(config);
const jobsApi = new JobsApi(config);

async function generateVideo() {
  try {
    // Create a video generation job
    const jobResponse = await videosApi.createVideoGenerationJob({
      configuration: {
        topic: "Pythagorean Theorem",
        context: "Explain the mathematical proof with visual demonstration",
        quality: "medium",
        use_rag: true
      }
    });
    
    console.log('Job created:', jobResponse.job_id);
    
    // Poll for job completion
    let status = 'queued';
    while (status !== 'completed' && status !== 'failed') {
      await new Promise(resolve => setTimeout(resolve, 5000)); // Wait 5 seconds
      
      const statusResponse = await videosApi.getVideoJobStatus(jobResponse.job_id);
      status = statusResponse.status;
      
      console.log(`Job status: ${status} (${statusResponse.progress.percentage}%)`);
    }
    
    if (status === 'completed') {
      console.log('Video generation completed!');
      // Download the video
      const videoBlob = await videosApi.downloadVideoFile(jobResponse.job_id);
      console.log('Video downloaded');
    } else {
      console.log('Video generation failed');
    }
    
  } catch (error) {
    console.error('Error:', error);
  }
}

generateVideo();
''',
            "python": '''
import time
from video_api_client import Configuration, ApiClient, VideosApi, JobsApi
from video_api_client.models import JobCreateRequest, JobConfiguration

# Configure the client
configuration = Configuration(
    host="https://api.example.com",
    access_token="your-clerk-session-token"
)

with ApiClient(configuration) as api_client:
    videos_api = VideosApi(api_client)
    jobs_api = JobsApi(api_client)
    
    try:
        # Create a video generation job
        job_request = JobCreateRequest(
            configuration=JobConfiguration(
                topic="Pythagorean Theorem",
                context="Explain the mathematical proof with visual demonstration",
                quality="medium",
                use_rag=True
            )
        )
        
        job_response = videos_api.create_video_generation_job(job_request)
        print(f"Job created: {job_response.job_id}")
        
        # Poll for job completion
        status = "queued"
        while status not in ["completed", "failed"]:
            time.sleep(5)  # Wait 5 seconds
            
            status_response = videos_api.get_video_job_status(job_response.job_id)
            status = status_response.status
            
            print(f"Job status: {status} ({status_response.progress.percentage}%)")
        
        if status == "completed":
            print("Video generation completed!")
            # Download the video
            video_data = videos_api.download_video_file(job_response.job_id)
            with open("generated_video.mp4", "wb") as f:
                f.write(video_data)
            print("Video downloaded as generated_video.mp4")
        else:
            print("Video generation failed")
            
    except Exception as e:
        print(f"Error: {e}")
''',
            "java": '''
import com.example.videoapiclient.ApiClient;
import com.example.videoapiclient.Configuration;
import com.example.videoapiclient.api.VideosApi;
import com.example.videoapiclient.api.JobsApi;
import com.example.videoapiclient.model.*;

public class VideoApiExample {
    public static void main(String[] args) {
        // Configure the client
        ApiClient client = Configuration.getDefaultApiClient();
        client.setBasePath("https://api.example.com");
        client.setAccessToken("your-clerk-session-token");
        
        VideosApi videosApi = new VideosApi(client);
        JobsApi jobsApi = new JobsApi(client);
        
        try {
            // Create a video generation job
            JobConfiguration config = new JobConfiguration()
                .topic("Pythagorean Theorem")
                .context("Explain the mathematical proof with visual demonstration")
                .quality(VideoQuality.MEDIUM)
                .useRag(true);
            
            JobCreateRequest request = new JobCreateRequest().configuration(config);
            JobResponse jobResponse = videosApi.createVideoGenerationJob(request);
            
            System.out.println("Job created: " + jobResponse.getJobId());
            
            // Poll for job completion
            String status = "queued";
            while (!"completed".equals(status) && !"failed".equals(status)) {
                Thread.sleep(5000); // Wait 5 seconds
                
                JobStatusResponse statusResponse = videosApi.getVideoJobStatus(jobResponse.getJobId());
                status = statusResponse.getStatus().getValue();
                
                System.out.println("Job status: " + status + " (" + 
                    statusResponse.getProgress().getPercentage() + "%)");
            }
            
            if ("completed".equals(status)) {
                System.out.println("Video generation completed!");
                // Download logic would go here
            } else {
                System.out.println("Video generation failed");
            }
            
        } catch (Exception e) {
            System.err.println("Error: " + e.getMessage());
        }
    }
}
'''
        }
        
        return examples.get(language)
    
    def _get_installation_instructions(self, language: str) -> str:
        """Get installation instructions for each language."""
        instructions = {
            "typescript": "```bash\nnpm install video-api-client\n```",
            "python": "```bash\npip install video-api-client\n```",
            "java": "Add to your `pom.xml`:\n```xml\n<dependency>\n  <groupId>com.example</groupId>\n  <artifactId>video-api-client</artifactId>\n  <version>1.0.0</version>\n</dependency>\n```",
            "csharp": "```bash\ndotnet add package VideoApiClient\n```",
            "go": "```bash\ngo get github.com/example/video-api-client-go\n```",
            "php": "```bash\ncomposer require example/video-api-client\n```",
            "ruby": "```bash\ngem install video_api_client\n```"
        }
        return instructions.get(language, "See documentation for installation instructions.")
    
    def _get_code_block_language(self, language: str) -> str:
        """Get code block language identifier."""
        mapping = {
            "typescript": "typescript",
            "python": "python",
            "java": "java",
            "csharp": "csharp",
            "go": "go",
            "php": "php",
            "ruby": "ruby"
        }
        return mapping.get(language, language)
    
    def _get_file_extension(self, language: str) -> str:
        """Get file extension for each language."""
        extensions = {
            "typescript": "ts",
            "python": "py",
            "java": "java",
            "csharp": "cs",
            "go": "go",
            "php": "php",
            "ruby": "rb"
        }
        return extensions.get(language, "txt")
    
    def _get_quick_start_example(self, language: str) -> str:
        """Get quick start example for each language."""
        examples = {
            "typescript": "import { VideosApi } from 'video-api-client';\n\nconst api = new VideosApi();\nconst job = await api.createVideoGenerationJob({...});",
            "python": "from video_api_client import VideosApi\n\napi = VideosApi()\njob = api.create_video_generation_job(...)",
            "java": "VideosApi api = new VideosApi();\nJobResponse job = api.createVideoGenerationJob(...);",
            "csharp": "var api = new VideosApi();\nvar job = await api.CreateVideoGenerationJobAsync(...);",
            "go": "client := videoapiclient.NewAPIClient(config)\njob, _, err := client.VideosApi.CreateVideoGenerationJob(...)",
            "php": "$api = new VideosApi();\n$job = $api->createVideoGenerationJob(...);",
            "ruby": "api = VideoApiClient::VideosApi.new\njob = api.create_video_generation_job(...)"
        }
        return examples.get(language, "// See documentation for usage examples")
    
    def _get_auth_example(self, language: str) -> str:
        """Get authentication example for each language."""
        examples = {
            "typescript": "const config = new Configuration({\n  accessToken: 'your-clerk-session-token'\n});",
            "python": "configuration.access_token = 'your-clerk-session-token'",
            "java": "client.setAccessToken(\"your-clerk-session-token\");",
            "csharp": "Configuration.Default.AccessToken = \"your-clerk-session-token\";",
            "go": "auth := context.WithValue(context.Background(), sw.ContextAccessToken, \"your-clerk-session-token\")",
            "php": "$config->setAccessToken('your-clerk-session-token');",
            "ruby": "VideoApiClient.configure { |c| c.access_token = 'your-clerk-session-token' }"
        }
        return examples.get(language, "// Set your authentication token")
    
    def generate_all_clients(self, languages: Optional[List[str]] = None) -> Dict[str, bool]:
        """Generate client SDKs for all specified languages."""
        if languages is None:
            languages = list(self.SUPPORTED_LANGUAGES.keys())
        
        # Ensure OpenAPI spec is available
        if not self.openapi_spec_path:
            self.fetch_openapi_spec()
        
        results = {}
        for language in languages:
            if language in self.SUPPORTED_LANGUAGES:
                results[language] = self.generate_client(language)
            else:
                print(f"Skipping unsupported language: {language}")
                results[language] = False
        
        return results
    
    def cleanup(self):
        """Clean up temporary files."""
        if self.openapi_spec_path and self.openapi_spec_path.exists():
            self.openapi_spec_path.unlink()
            print(f"Cleaned up temporary OpenAPI spec file")


def main():
    """Main function for command-line usage."""
    parser = argparse.ArgumentParser(description="Generate client SDKs for Video Generation API")
    parser.add_argument(
        "--api-url",
        default="http://localhost:8000",
        help="Base URL of the API (default: http://localhost:8000)"
    )
    parser.add_argument(
        "--output-dir",
        default="generated_clients",
        help="Output directory for generated clients (default: generated_clients)"
    )
    parser.add_argument(
        "--languages",
        nargs="+",
        choices=list(ClientGenerator.SUPPORTED_LANGUAGES.keys()),
        help="Languages to generate (default: all supported languages)"
    )
    parser.add_argument(
        "--install-generator",
        action="store_true",
        help="Install OpenAPI Generator CLI if not found"
    )
    
    args = parser.parse_args()
    
    generator = ClientGenerator(args.api_url, args.output_dir)
    
    # Check if OpenAPI Generator is available
    if not generator.check_openapi_generator():
        if args.install_generator:
            if not generator.install_openapi_generator():
                print("Failed to install OpenAPI Generator. Please install it manually.")
                sys.exit(1)
        else:
            print("OpenAPI Generator CLI not found. Use --install-generator to install it automatically.")
            sys.exit(1)
    
    try:
        # Generate clients
        results = generator.generate_all_clients(args.languages)
        
        # Print summary
        print("\n" + "="*50)
        print("CLIENT GENERATION SUMMARY")
        print("="*50)
        
        successful = []
        failed = []
        
        for language, success in results.items():
            if success:
                successful.append(language)
                print(f"✅ {language}: SUCCESS")
            else:
                failed.append(language)
                print(f"❌ {language}: FAILED")
        
        print(f"\nSuccessful: {len(successful)}")
        print(f"Failed: {len(failed)}")
        
        if successful:
            print(f"\nGenerated clients are available in: {generator.output_base_dir}")
        
        # Exit with error code if any generation failed
        sys.exit(1 if failed else 0)
        
    finally:
        generator.cleanup()


if __name__ == "__main__":
    main()