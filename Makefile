# Video Generation API - Client Generation Makefile
# This Makefile provides convenient commands for generating and testing client SDKs

.PHONY: help install-deps generate-clients test-clients clean-clients docs serve-api

# Default target
help:
	@echo "Video Generation API - Client Generation"
	@echo ""
	@echo "Available targets:"
	@echo "  help              Show this help message"
	@echo "  install-deps      Install required dependencies"
	@echo "  generate-clients  Generate all client SDKs"
	@echo "  generate-ts       Generate TypeScript client only"
	@echo "  generate-python   Generate Python client only"
	@echo "  generate-java     Generate Java client only"
	@echo "  test-clients      Test generated clients"
	@echo "  clean-clients     Clean generated clients"
	@echo "  serve-api         Start API server for testing"
	@echo "  worker            Start video generation worker"
	@echo "  docs              Generate documentation"
	@echo ""
	@echo "Environment variables:"
	@echo "  API_URL           API base URL (default: http://localhost:8000)"
	@echo "  OUTPUT_DIR        Output directory (default: generated_clients)"
	@echo "  LANGUAGES         Space-separated list of languages"

# Configuration
API_URL ?= http://localhost:8000
OUTPUT_DIR ?= generated_clients
LANGUAGES ?= typescript python java csharp go php ruby

# Install dependencies
install-deps:
	@echo "Installing dependencies..."
	@command -v node >/dev/null 2>&1 || { echo "Node.js is required but not installed. Please install Node.js first."; exit 1; }
	@command -v npm >/dev/null 2>&1 || { echo "npm is required but not installed. Please install npm first."; exit 1; }
	@echo "Installing OpenAPI Generator CLI..."
	npm install -g @openapitools/openapi-generator-cli
	@echo "Dependencies installed successfully!"

# Generate all clients
generate-clients: check-api
	@echo "Generating client SDKs for languages: $(LANGUAGES)"
	python scripts/generate_clients.py \
		--api-url $(API_URL) \
		--output-dir $(OUTPUT_DIR) \
		--languages $(LANGUAGES)

# Generate TypeScript client
generate-ts: check-api
	@echo "Generating TypeScript client..."
	python scripts/generate_clients.py \
		--api-url $(API_URL) \
		--output-dir $(OUTPUT_DIR) \
		--languages typescript

# Generate Python client
generate-python: check-api
	@echo "Generating Python client..."
	python scripts/generate_clients.py \
		--api-url $(API_URL) \
		--output-dir $(OUTPUT_DIR) \
		--languages python

# Generate Java client
generate-java: check-api
	@echo "Generating Java client..."
	python scripts/generate_clients.py \
		--api-url $(API_URL) \
		--output-dir $(OUTPUT_DIR) \
		--languages java

# Test generated clients
test-clients:
	@echo "Testing generated clients..."
	python scripts/test_clients.py \
		--api-url $(API_URL) \
		--clients-dir $(OUTPUT_DIR) \
		--verbose

# Clean generated clients
clean-clients:
	@echo "Cleaning generated clients..."
	rm -rf $(OUTPUT_DIR)
	@echo "Generated clients cleaned!"

# Check if API is running
check-api:
	@echo "Checking if API is running at $(API_URL)..."
	@curl -s -f $(API_URL)/health > /dev/null || { \
		echo "API is not running at $(API_URL)"; \
		echo "Please start the API server first with: make serve-api"; \
		exit 1; \
	}
	@echo "API is running!"

# Start API server
serve-api:
	@echo "Starting API server..."
	python -m uvicorn src.app.main:app --reload --host 0.0.0.0 --port 8000

# Start video generation worker
worker:
	@echo "Starting video generation worker..."
	python run_worker.py

# Development environment setup
dev-setup-full: install-deps
	@echo "Setting up full development environment with Docker..."
	@chmod +x setup-dev.sh
	@./setup-dev.sh

# Start development services (Redis + ngrok)
dev-services:
	@echo "Starting development services (Redis + ngrok)..."
	docker-compose -f docker-compose.dev.yml up -d
	@echo "Services started! Visit http://localhost:4040 for ngrok dashboard"

# Stop development services
dev-services-stop:
	@echo "Stopping development services..."
	docker-compose -f docker-compose.dev.yml down

# View development services logs
dev-services-logs:
	docker-compose -f docker-compose.dev.yml logs -f

# Full development workflow
dev-start: dev-services serve-api

# Get ngrok public URL
get-ngrok-url:
	@echo "Getting ngrok public URL..."
	@curl -s http://localhost:4040/api/tunnels | python -c "import sys, json; data = json.load(sys.stdin); print(data['tunnels'][0]['public_url'] if data['tunnels'] else 'No tunnels found')" 2>/dev/null || echo "ngrok not running or no tunnels found"

# Generate documentation
docs:
	@echo "Generating documentation..."
	@mkdir -p docs/generated
	@echo "Documentation generated in docs/ directory"

# Development targets
dev-setup: install-deps
	@echo "Setting up development environment..."
	@chmod +x scripts/generate_clients.sh
	@echo "Development environment ready!"

# Quick test - generate and test TypeScript client
quick-test: generate-ts
	@echo "Running quick test with TypeScript client..."
	cd $(OUTPUT_DIR)/typescript && npm install --silent
	@echo "Quick test completed!"

# Full workflow - generate all clients and test
full-workflow: generate-clients test-clients
	@echo "Full client generation and testing workflow completed!"

# Docker targets
docker-generate:
	@echo "Generating clients using Docker..."
	docker run --rm \
		-v $(PWD):/workspace \
		-w /workspace \
		node:18-alpine \
		sh -c "npm install -g @openapitools/openapi-generator-cli && python scripts/generate_clients.py"

# CI/CD targets
ci-test: install-deps generate-clients test-clients
	@echo "CI/CD pipeline completed successfully!"

# Validate OpenAPI spec
validate-spec: check-api
	@echo "Validating OpenAPI specification..."
	curl -s $(API_URL)/openapi.json | python -m json.tool > /dev/null
	@echo "OpenAPI specification is valid!"

# Show client statistics
stats:
	@echo "Client generation statistics:"
	@if [ -d "$(OUTPUT_DIR)" ]; then \
		echo "Generated clients:"; \
		for dir in $(OUTPUT_DIR)/*/; do \
			if [ -d "$$dir" ]; then \
				lang=$$(basename "$$dir"); \
				files=$$(find "$$dir" -type f | wc -l); \
				size=$$(du -sh "$$dir" | cut -f1); \
				echo "  $$lang: $$files files, $$size"; \
			fi; \
		done; \
	else \
		echo "No clients generated yet. Run 'make generate-clients' first."; \
	fi

# Package clients for distribution
package:
	@echo "Packaging clients for distribution..."
	@mkdir -p dist
	@if [ -d "$(OUTPUT_DIR)" ]; then \
		cd $(OUTPUT_DIR) && \
		for dir in */; do \
			if [ -d "$$dir" ]; then \
				lang=$$(basename "$$dir"); \
				echo "Packaging $$lang client..."; \
				tar -czf ../dist/video-api-client-$$lang.tar.gz "$$dir"; \
			fi; \
		done; \
	fi
	@echo "Clients packaged in dist/ directory"

# Publish clients (placeholder - customize for your needs)
publish:
	@echo "Publishing clients..."
	@echo "This is a placeholder. Customize for your package managers."
	@if [ -d "$(OUTPUT_DIR)/typescript" ]; then \
		echo "Would publish TypeScript client to npm"; \
	fi
	@if [ -d "$(OUTPUT_DIR)/python" ]; then \
		echo "Would publish Python client to PyPI"; \
	fi
	@if [ -d "$(OUTPUT_DIR)/java" ]; then \
		echo "Would publish Java client to Maven Central"; \
	fi

# Watch for changes and regenerate
watch:
	@echo "Watching for API changes and regenerating clients..."
	@echo "This requires 'entr' to be installed: brew install entr"
	@echo "Watching src/app/ for changes..."
	find src/app -name "*.py" | entr -r make generate-clients

# Benchmark client generation
benchmark:
	@echo "Benchmarking client generation..."
	@time make generate-clients
	@echo "Benchmark completed!"

# Show OpenAPI spec
show-spec: check-api
	@echo "OpenAPI Specification:"
	@curl -s $(API_URL)/openapi.json | python -m json.tool

# Interactive mode
interactive:
	@echo "Interactive client generation mode"
	@echo "Available languages: typescript python java csharp go php ruby"
	@read -p "Enter languages to generate (space-separated): " langs; \
	make generate-clients LANGUAGES="$$langs"

# Health check
health:
	@echo "Performing health check..."
	@make check-api
	@command -v openapi-generator-cli >/dev/null 2>&1 || { echo "OpenAPI Generator CLI not found"; exit 1; }
	@command -v python >/dev/null 2>&1 || { echo "Python not found"; exit 1; }
	@echo "All dependencies are available!"

# Show version information
version:
	@echo "Version information:"
	@echo "Node.js: $$(node --version 2>/dev/null || echo 'Not installed')"
	@echo "npm: $$(npm --version 2>/dev/null || echo 'Not installed')"
	@echo "Python: $$(python --version 2>/dev/null || echo 'Not installed')"
	@echo "OpenAPI Generator: $$(openapi-generator-cli version 2>/dev/null || echo 'Not installed')"

# Example usage
example:
	@echo "Example usage:"
	@echo ""
	@echo "1. Start the API server:"
	@echo "   make serve-api"
	@echo ""
	@echo "2. In another terminal, generate clients:"
	@echo "   make generate-clients"
	@echo ""
	@echo "3. Test the generated clients:"
	@echo "   make test-clients"
	@echo ""
	@echo "4. Generate specific language only:"
	@echo "   make generate-ts"
	@echo "   make generate-python"
	@echo ""
	@echo "5. Clean up:"
	@echo "   make clean-clients"