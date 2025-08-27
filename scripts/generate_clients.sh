#!/bin/bash

# Video Generation API Client Generator Script
# This script generates client SDKs for multiple programming languages

set -e  # Exit on any error

# Configuration
API_URL="${API_URL:-http://localhost:8000}"
OUTPUT_DIR="${OUTPUT_DIR:-generated_clients}"
CONFIG_FILE="openapi-generator-config.yaml"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Logging functions
log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Function to check if a command exists
command_exists() {
    command -v "$1" >/dev/null 2>&1
}

# Function to check prerequisites
check_prerequisites() {
    log_info "Checking prerequisites..."
    
    # Check if Node.js and npm are installed
    if ! command_exists node; then
        log_error "Node.js is not installed. Please install Node.js first."
        exit 1
    fi
    
    if ! command_exists npm; then
        log_error "npm is not installed. Please install npm first."
        exit 1
    fi
    
    # Check if OpenAPI Generator CLI is installed
    if ! command_exists openapi-generator-cli; then
        log_warning "OpenAPI Generator CLI not found. Installing..."
        npm install -g @openapitools/openapi-generator-cli
        
        if ! command_exists openapi-generator-cli; then
            log_error "Failed to install OpenAPI Generator CLI"
            exit 1
        fi
        log_success "OpenAPI Generator CLI installed successfully"
    else
        log_success "OpenAPI Generator CLI found"
    fi
    
    # Check if Python is available (for the Python script)
    if ! command_exists python3; then
        log_warning "Python 3 not found. Some features may not work."
    fi
}

# Function to fetch OpenAPI specification
fetch_openapi_spec() {
    log_info "Fetching OpenAPI specification from $API_URL..."
    
    # Create temporary directory
    TEMP_DIR=$(mktemp -d)
    OPENAPI_SPEC="$TEMP_DIR/openapi.json"
    
    # Fetch the OpenAPI spec
    if curl -s -f "$API_URL/openapi.json" -o "$OPENAPI_SPEC"; then
        log_success "OpenAPI specification fetched successfully"
        echo "$OPENAPI_SPEC"
    else
        log_error "Failed to fetch OpenAPI specification from $API_URL"
        log_error "Make sure the API server is running and accessible"
        exit 1
    fi
}

# Function to generate client for a specific language
generate_client() {
    local language=$1
    local spec_file=$2
    
    log_info "Generating $language client..."
    
    case $language in
        "typescript")
            openapi-generator-cli generate \
                -i "$spec_file" \
                -g typescript-fetch \
                -o "$OUTPUT_DIR/typescript" \
                --package-name video-api-client \
                --additional-properties=npmName=video-api-client,npmVersion=1.0.0,supportsES6=true,withInterfaces=true,typescriptThreePlus=true
            ;;
        "python")
            openapi-generator-cli generate \
                -i "$spec_file" \
                -g python \
                -o "$OUTPUT_DIR/python" \
                --package-name video_api_client \
                --additional-properties=packageName=video_api_client,projectName=video-api-client,packageVersion=1.0.0
            ;;
        "java")
            openapi-generator-cli generate \
                -i "$spec_file" \
                -g java \
                -o "$OUTPUT_DIR/java" \
                --package-name com.example.videoapiclient \
                --additional-properties=groupId=com.example,artifactId=video-api-client,artifactVersion=1.0.0,library=okhttp-gson,java8=true
            ;;
        "csharp")
            openapi-generator-cli generate \
                -i "$spec_file" \
                -g csharp \
                -o "$OUTPUT_DIR/csharp" \
                --package-name VideoApiClient \
                --additional-properties=packageName=VideoApiClient,packageVersion=1.0.0,clientPackage=VideoApiClient,targetFramework=netstandard2.0
            ;;
        "go")
            openapi-generator-cli generate \
                -i "$spec_file" \
                -g go \
                -o "$OUTPUT_DIR/go" \
                --package-name videoapiclient \
                --additional-properties=packageName=videoapiclient,packageVersion=1.0.0,packageUrl=github.com/example/video-api-client-go
            ;;
        "php")
            openapi-generator-cli generate \
                -i "$spec_file" \
                -g php \
                -o "$OUTPUT_DIR/php" \
                --package-name VideoApiClient \
                --additional-properties=packageName=VideoApiClient,composerVendorName=example,composerProjectName=video-api-client,packageVersion=1.0.0
            ;;
        "ruby")
            openapi-generator-cli generate \
                -i "$spec_file" \
                -g ruby \
                -o "$OUTPUT_DIR/ruby" \
                --package-name video_api_client \
                --additional-properties=gemName=video_api_client,gemVersion=1.0.0,moduleName=VideoApiClient
            ;;
        *)
            log_error "Unsupported language: $language"
            return 1
            ;;
    esac
    
    if [ $? -eq 0 ]; then
        log_success "$language client generated successfully"
        post_process_client "$language"
        return 0
    else
        log_error "Failed to generate $language client"
        return 1
    fi
}

# Function to post-process generated clients
post_process_client() {
    local language=$1
    local client_dir="$OUTPUT_DIR/$language"
    
    log_info "Post-processing $language client..."
    
    # Create README if it doesn't exist
    if [ ! -f "$client_dir/README.md" ]; then
        create_readme "$language" "$client_dir"
    fi
    
    # Create example file
    create_example "$language" "$client_dir"
    
    # Language-specific post-processing
    case $language in
        "typescript")
            post_process_typescript "$client_dir"
            ;;
        "python")
            post_process_python "$client_dir"
            ;;
        "java")
            post_process_java "$client_dir"
            ;;
    esac
}

# Function to create README for client
create_readme() {
    local language=$1
    local client_dir=$2
    
    cat > "$client_dir/README.md" << EOF
# Video Generation API Client - ${language^}

This is an auto-generated client library for the Video Generation API.

## Installation

See the installation instructions in the main documentation.

## Quick Start

\`\`\`${language}
// See example.${language} for usage examples
\`\`\`

## Authentication

This API uses Clerk authentication. You need to provide a valid Clerk session token.

## Documentation

For complete API documentation, visit: https://docs.example.com

## Support

- GitHub Issues: https://github.com/example/video-api-client-${language}/issues
- Documentation: https://docs.example.com
- Email: support@example.com

## License

MIT License - see LICENSE file for details.
EOF
}

# Function to create example file
create_example() {
    local language=$1
    local client_dir=$2
    
    case $language in
        "typescript")
            cat > "$client_dir/example.ts" << 'EOF'
import { Configuration, VideosApi } from './src';

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
  } catch (error) {
    console.error('Error:', error);
  }
}

generateVideo();
EOF
            ;;
        "python")
            cat > "$client_dir/example.py" << 'EOF'
from video_api_client import Configuration, ApiClient, VideosApi
from video_api_client.models import JobCreateRequest, JobConfiguration

configuration = Configuration(
    host="https://api.example.com",
    access_token="your-clerk-session-token"
)

with ApiClient(configuration) as api_client:
    videos_api = VideosApi(api_client)
    
    try:
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
        
    except Exception as e:
        print(f"Error: {e}")
EOF
            ;;
    esac
}

# Language-specific post-processing functions
post_process_typescript() {
    local client_dir=$1
    
    # Create package.json if it doesn't exist
    if [ ! -f "$client_dir/package.json" ]; then
        cat > "$client_dir/package.json" << 'EOF'
{
  "name": "video-api-client",
  "version": "1.0.0",
  "description": "TypeScript client for Video Generation API",
  "main": "dist/index.js",
  "types": "dist/index.d.ts",
  "scripts": {
    "build": "tsc",
    "test": "jest"
  },
  "dependencies": {
    "node-fetch": "^2.6.7"
  },
  "devDependencies": {
    "typescript": "^4.9.0",
    "@types/node": "^18.0.0"
  },
  "keywords": ["video", "api", "client", "typescript"],
  "author": "API Team",
  "license": "MIT"
}
EOF
    fi
}

post_process_python() {
    local client_dir=$1
    
    # Create setup.py if it doesn't exist
    if [ ! -f "$client_dir/setup.py" ]; then
        cat > "$client_dir/setup.py" << 'EOF'
from setuptools import setup, find_packages

setup(
    name="video-api-client",
    version="1.0.0",
    description="Python client for Video Generation API",
    packages=find_packages(),
    install_requires=[
        "requests>=2.25.0",
        "urllib3>=1.26.0",
        "python-dateutil>=2.8.0"
    ],
    author="API Team",
    author_email="api-team@example.com",
    license="MIT"
)
EOF
    fi
}

post_process_java() {
    local client_dir=$1
    
    # Java post-processing would go here
    log_info "Java client post-processing completed"
}

# Function to test generated clients
test_clients() {
    log_info "Testing generated clients..."
    
    # Test TypeScript client
    if [ -d "$OUTPUT_DIR/typescript" ]; then
        log_info "Testing TypeScript client..."
        cd "$OUTPUT_DIR/typescript"
        if [ -f "package.json" ]; then
            npm install --silent
            npm run build --silent 2>/dev/null || log_warning "TypeScript build failed"
        fi
        cd - > /dev/null
    fi
    
    # Test Python client
    if [ -d "$OUTPUT_DIR/python" ]; then
        log_info "Testing Python client..."
        cd "$OUTPUT_DIR/python"
        if [ -f "setup.py" ] && command_exists python3; then
            python3 setup.py check --quiet 2>/dev/null || log_warning "Python setup check failed"
        fi
        cd - > /dev/null
    fi
}

# Function to create documentation
create_documentation() {
    log_info "Creating client documentation..."
    
    cat > "$OUTPUT_DIR/README.md" << EOF
# Video Generation API Clients

This directory contains auto-generated client libraries for the Video Generation API in multiple programming languages.

## Available Clients

EOF
    
    for dir in "$OUTPUT_DIR"/*; do
        if [ -d "$dir" ]; then
            language=$(basename "$dir")
            echo "- [$language](./$language/)" >> "$OUTPUT_DIR/README.md"
        fi
    done
    
    cat >> "$OUTPUT_DIR/README.md" << EOF

## Quick Start

Each client directory contains:
- Generated API client code
- README with installation and usage instructions
- Example code demonstrating basic usage
- Package/project files for the respective language

## Authentication

All clients support Clerk authentication. Set your session token when configuring the client.

## Documentation

- API Documentation: https://docs.example.com
- OpenAPI Specification: $API_URL/openapi.json

## Support

For issues with the generated clients:
- Check the individual client README files
- Visit our documentation at https://docs.example.com
- Contact support at support@example.com

Generated on: $(date)
EOF
}

# Main function
main() {
    local languages=("$@")
    
    # Default to all languages if none specified
    if [ ${#languages[@]} -eq 0 ]; then
        languages=("typescript" "python" "java" "csharp" "go" "php" "ruby")
    fi
    
    log_info "Starting client generation for languages: ${languages[*]}"
    
    # Check prerequisites
    check_prerequisites
    
    # Fetch OpenAPI specification
    OPENAPI_SPEC=$(fetch_openapi_spec)
    
    # Create output directory
    mkdir -p "$OUTPUT_DIR"
    
    # Generate clients
    local successful=()
    local failed=()
    
    for language in "${languages[@]}"; do
        if generate_client "$language" "$OPENAPI_SPEC"; then
            successful+=("$language")
        else
            failed+=("$language")
        fi
    done
    
    # Test clients
    test_clients
    
    # Create documentation
    create_documentation
    
    # Print summary
    echo
    echo "=================================================="
    echo "CLIENT GENERATION SUMMARY"
    echo "=================================================="
    
    if [ ${#successful[@]} -gt 0 ]; then
        log_success "Successfully generated: ${successful[*]}"
    fi
    
    if [ ${#failed[@]} -gt 0 ]; then
        log_error "Failed to generate: ${failed[*]}"
    fi
    
    echo
    log_info "Generated clients are available in: $OUTPUT_DIR"
    
    # Cleanup
    rm -rf "$(dirname "$OPENAPI_SPEC")"
    
    # Exit with error if any generation failed
    if [ ${#failed[@]} -gt 0 ]; then
        exit 1
    fi
}

# Parse command line arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --api-url)
            API_URL="$2"
            shift 2
            ;;
        --output-dir)
            OUTPUT_DIR="$2"
            shift 2
            ;;
        --help)
            echo "Usage: $0 [OPTIONS] [LANGUAGES...]"
            echo ""
            echo "Generate client SDKs for Video Generation API"
            echo ""
            echo "Options:"
            echo "  --api-url URL      API base URL (default: http://localhost:8000)"
            echo "  --output-dir DIR   Output directory (default: generated_clients)"
            echo "  --help            Show this help message"
            echo ""
            echo "Languages:"
            echo "  typescript python java csharp go php ruby"
            echo ""
            echo "Examples:"
            echo "  $0                           # Generate all clients"
            echo "  $0 typescript python        # Generate only TypeScript and Python"
            echo "  $0 --api-url https://api.example.com typescript"
            exit 0
            ;;
        *)
            break
            ;;
    esac
done

# Run main function with remaining arguments as languages
main "$@"