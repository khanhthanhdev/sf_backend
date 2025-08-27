#!/usr/bin/env python3
"""
Client SDK testing script for FastAPI Video Generation Backend.

This script tests the generated client SDKs to ensure they work correctly
with the API endpoints. It performs basic functionality tests and validates
the client-server communication.
"""

import os
import sys
import json
import time
import asyncio
import requests
import subprocess
from pathlib import Path
from typing import Dict, List, Optional, Any
import tempfile
import logging

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class ClientTester:
    """Test suite for generated client SDKs."""
    
    def __init__(self, api_url: str = "http://localhost:8000", clients_dir: str = "generated_clients"):
        self.api_url = api_url.rstrip("/")
        self.clients_dir = Path(clients_dir)
        self.test_results: Dict[str, Dict[str, Any]] = {}
        
    def check_api_availability(self) -> bool:
        """Check if the API server is running and accessible."""
        try:
            logger.info(f"Checking API availability at {self.api_url}")
            response = requests.get(f"{self.api_url}/health", timeout=10)
            response.raise_for_status()
            logger.info("API server is available")
            return True
        except requests.RequestException as e:
            logger.error(f"API server is not available: {e}")
            return False
    
    def test_openapi_spec(self) -> bool:
        """Test if OpenAPI specification is accessible."""
        try:
            logger.info("Testing OpenAPI specification accessibility")
            response = requests.get(f"{self.api_url}/openapi.json", timeout=10)
            response.raise_for_status()
            
            spec = response.json()
            
            # Validate basic OpenAPI structure
            required_fields = ["openapi", "info", "paths"]
            for field in required_fields:
                if field not in spec:
                    logger.error(f"OpenAPI spec missing required field: {field}")
                    return False
            
            logger.info("OpenAPI specification is valid")
            return True
            
        except requests.RequestException as e:
            logger.error(f"Failed to fetch OpenAPI specification: {e}")
            return False
        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON in OpenAPI specification: {e}")
            return False
    
    def test_typescript_client(self) -> Dict[str, Any]:
        """Test TypeScript client."""
        client_dir = self.clients_dir / "typescript"
        result = {
            "language": "typescript",
            "exists": False,
            "builds": False,
            "has_examples": False,
            "has_docs": False,
            "errors": []
        }
        
        try:
            if not client_dir.exists():
                result["errors"].append("Client directory does not exist")
                return result
            
            result["exists"] = True
            
            # Check for essential files
            essential_files = ["package.json", "README.md"]
            for file in essential_files:
                if not (client_dir / file).exists():
                    result["errors"].append(f"Missing {file}")
            
            # Check for example file
            if (client_dir / "example.ts").exists():
                result["has_examples"] = True
            
            # Check for documentation
            if (client_dir / "README.md").exists():
                result["has_docs"] = True
            
            # Try to build the client
            if (client_dir / "package.json").exists():
                logger.info("Testing TypeScript client build")
                
                # Install dependencies
                install_result = subprocess.run(
                    ["npm", "install"],
                    cwd=client_dir,
                    capture_output=True,
                    text=True,
                    timeout=120
                )
                
                if install_result.returncode != 0:
                    result["errors"].append(f"npm install failed: {install_result.stderr}")
                else:
                    # Try to build
                    build_result = subprocess.run(
                        ["npm", "run", "build"],
                        cwd=client_dir,
                        capture_output=True,
                        text=True,
                        timeout=60
                    )
                    
                    if build_result.returncode == 0:
                        result["builds"] = True
                    else:
                        result["errors"].append(f"Build failed: {build_result.stderr}")
            
        except subprocess.TimeoutExpired:
            result["errors"].append("Build timeout")
        except Exception as e:
            result["errors"].append(f"Unexpected error: {str(e)}")
        
        return result
    
    def test_python_client(self) -> Dict[str, Any]:
        """Test Python client."""
        client_dir = self.clients_dir / "python"
        result = {
            "language": "python",
            "exists": False,
            "installs": False,
            "imports": False,
            "has_examples": False,
            "has_docs": False,
            "errors": []
        }
        
        try:
            if not client_dir.exists():
                result["errors"].append("Client directory does not exist")
                return result
            
            result["exists"] = True
            
            # Check for essential files
            essential_files = ["setup.py", "README.md"]
            for file in essential_files:
                if not (client_dir / file).exists():
                    result["errors"].append(f"Missing {file}")
            
            # Check for example file
            if (client_dir / "example.py").exists():
                result["has_examples"] = True
            
            # Check for documentation
            if (client_dir / "README.md").exists():
                result["has_docs"] = True
            
            # Try to install the client in development mode
            if (client_dir / "setup.py").exists():
                logger.info("Testing Python client installation")
                
                install_result = subprocess.run(
                    [sys.executable, "setup.py", "develop", "--user"],
                    cwd=client_dir,
                    capture_output=True,
                    text=True,
                    timeout=120
                )
                
                if install_result.returncode == 0:
                    result["installs"] = True
                    
                    # Try to import the client
                    try:
                        import importlib.util
                        
                        # Find the main module
                        main_module_path = None
                        for py_file in client_dir.rglob("*.py"):
                            if "__init__.py" in py_file.name:
                                main_module_path = py_file
                                break
                        
                        if main_module_path:
                            spec = importlib.util.spec_from_file_location("test_client", main_module_path)
                            if spec and spec.loader:
                                module = importlib.util.module_from_spec(spec)
                                spec.loader.exec_module(module)
                                result["imports"] = True
                        
                    except Exception as e:
                        result["errors"].append(f"Import failed: {str(e)}")
                else:
                    result["errors"].append(f"Installation failed: {install_result.stderr}")
            
        except subprocess.TimeoutExpired:
            result["errors"].append("Installation timeout")
        except Exception as e:
            result["errors"].append(f"Unexpected error: {str(e)}")
        
        return result
    
    def test_java_client(self) -> Dict[str, Any]:
        """Test Java client."""
        client_dir = self.clients_dir / "java"
        result = {
            "language": "java",
            "exists": False,
            "compiles": False,
            "has_examples": False,
            "has_docs": False,
            "errors": []
        }
        
        try:
            if not client_dir.exists():
                result["errors"].append("Client directory does not exist")
                return result
            
            result["exists"] = True
            
            # Check for essential files
            essential_files = ["pom.xml", "README.md"]
            for file in essential_files:
                if not (client_dir / file).exists():
                    result["errors"].append(f"Missing {file}")
            
            # Check for example file
            if (client_dir / "example.java").exists():
                result["has_examples"] = True
            
            # Check for documentation
            if (client_dir / "README.md").exists():
                result["has_docs"] = True
            
            # Try to compile the client (if Maven is available)
            if (client_dir / "pom.xml").exists():
                logger.info("Testing Java client compilation")
                
                # Check if Maven is available
                maven_check = subprocess.run(
                    ["mvn", "--version"],
                    capture_output=True,
                    text=True,
                    timeout=10
                )
                
                if maven_check.returncode == 0:
                    compile_result = subprocess.run(
                        ["mvn", "compile"],
                        cwd=client_dir,
                        capture_output=True,
                        text=True,
                        timeout=180
                    )
                    
                    if compile_result.returncode == 0:
                        result["compiles"] = True
                    else:
                        result["errors"].append(f"Compilation failed: {compile_result.stderr}")
                else:
                    result["errors"].append("Maven not available for compilation test")
            
        except subprocess.TimeoutExpired:
            result["errors"].append("Compilation timeout")
        except Exception as e:
            result["errors"].append(f"Unexpected error: {str(e)}")
        
        return result
    
    def test_client_structure(self, language: str) -> Dict[str, Any]:
        """Test the structure of a generated client."""
        client_dir = self.clients_dir / language
        result = {
            "language": language,
            "exists": False,
            "structure_valid": False,
            "has_api_files": False,
            "has_model_files": False,
            "has_docs": False,
            "file_count": 0,
            "errors": []
        }
        
        try:
            if not client_dir.exists():
                result["errors"].append("Client directory does not exist")
                return result
            
            result["exists"] = True
            
            # Count files
            all_files = list(client_dir.rglob("*"))
            result["file_count"] = len([f for f in all_files if f.is_file()])
            
            # Check for API files
            api_files = list(client_dir.rglob("*api*"))
            if api_files:
                result["has_api_files"] = True
            
            # Check for model files
            model_files = list(client_dir.rglob("*model*"))
            if model_files:
                result["has_model_files"] = True
            
            # Check for documentation
            doc_files = list(client_dir.rglob("README*")) + list(client_dir.rglob("*.md"))
            if doc_files:
                result["has_docs"] = True
            
            # Basic structure validation
            if result["has_api_files"] and result["has_model_files"]:
                result["structure_valid"] = True
            
        except Exception as e:
            result["errors"].append(f"Unexpected error: {str(e)}")
        
        return result
    
    def run_functional_tests(self) -> Dict[str, Any]:
        """Run functional tests against the API using generated clients."""
        result = {
            "api_reachable": False,
            "openapi_valid": False,
            "endpoints_tested": 0,
            "endpoints_passed": 0,
            "errors": []
        }
        
        try:
            # Test API availability
            result["api_reachable"] = self.check_api_availability()
            
            # Test OpenAPI spec
            result["openapi_valid"] = self.test_openapi_spec()
            
            if not result["api_reachable"]:
                result["errors"].append("API not reachable - skipping functional tests")
                return result
            
            # Test basic endpoints
            endpoints_to_test = [
                {"method": "GET", "path": "/health", "expected_status": 200},
                {"method": "GET", "path": "/", "expected_status": 200},
                {"method": "GET", "path": "/openapi.json", "expected_status": 200},
            ]
            
            for endpoint in endpoints_to_test:
                try:
                    result["endpoints_tested"] += 1
                    
                    response = requests.request(
                        endpoint["method"],
                        f"{self.api_url}{endpoint['path']}",
                        timeout=10
                    )
                    
                    if response.status_code == endpoint["expected_status"]:
                        result["endpoints_passed"] += 1
                    else:
                        result["errors"].append(
                            f"{endpoint['method']} {endpoint['path']} returned {response.status_code}, "
                            f"expected {endpoint['expected_status']}"
                        )
                        
                except requests.RequestException as e:
                    result["errors"].append(f"Failed to test {endpoint['path']}: {str(e)}")
            
        except Exception as e:
            result["errors"].append(f"Functional test error: {str(e)}")
        
        return result
    
    def run_all_tests(self) -> Dict[str, Any]:
        """Run all client tests."""
        logger.info("Starting comprehensive client testing")
        
        # Test API functionality
        functional_results = self.run_functional_tests()
        
        # Test individual clients
        client_results = {}
        
        # Test TypeScript client
        if (self.clients_dir / "typescript").exists():
            logger.info("Testing TypeScript client")
            client_results["typescript"] = self.test_typescript_client()
        
        # Test Python client
        if (self.clients_dir / "python").exists():
            logger.info("Testing Python client")
            client_results["python"] = self.test_python_client()
        
        # Test Java client
        if (self.clients_dir / "java").exists():
            logger.info("Testing Java client")
            client_results["java"] = self.test_java_client()
        
        # Test structure for all clients
        structure_results = {}
        for client_dir in self.clients_dir.iterdir():
            if client_dir.is_dir():
                language = client_dir.name
                logger.info(f"Testing {language} client structure")
                structure_results[language] = self.test_client_structure(language)
        
        return {
            "functional_tests": functional_results,
            "client_tests": client_results,
            "structure_tests": structure_results,
            "summary": self._generate_summary(functional_results, client_results, structure_results)
        }
    
    def _generate_summary(self, functional: Dict, clients: Dict, structures: Dict) -> Dict[str, Any]:
        """Generate test summary."""
        total_clients = len(structures)
        working_clients = 0
        
        for language, result in clients.items():
            if language == "typescript" and result.get("builds", False):
                working_clients += 1
            elif language == "python" and result.get("imports", False):
                working_clients += 1
            elif language == "java" and result.get("compiles", False):
                working_clients += 1
        
        return {
            "total_clients_found": total_clients,
            "clients_tested": len(clients),
            "working_clients": working_clients,
            "api_functional": functional.get("api_reachable", False),
            "openapi_valid": functional.get("openapi_valid", False),
            "endpoints_success_rate": (
                functional.get("endpoints_passed", 0) / max(functional.get("endpoints_tested", 1), 1) * 100
            )
        }
    
    def print_results(self, results: Dict[str, Any]) -> None:
        """Print test results in a formatted way."""
        print("\n" + "="*60)
        print("CLIENT SDK TEST RESULTS")
        print("="*60)
        
        # Print summary
        summary = results["summary"]
        print(f"\nSUMMARY:")
        print(f"  Total clients found: {summary['total_clients_found']}")
        print(f"  Clients tested: {summary['clients_tested']}")
        print(f"  Working clients: {summary['working_clients']}")
        print(f"  API functional: {'✅' if summary['api_functional'] else '❌'}")
        print(f"  OpenAPI valid: {'✅' if summary['openapi_valid'] else '❌'}")
        print(f"  Endpoints success rate: {summary['endpoints_success_rate']:.1f}%")
        
        # Print functional test results
        print(f"\nFUNCTIONAL TESTS:")
        functional = results["functional_tests"]
        print(f"  API reachable: {'✅' if functional['api_reachable'] else '❌'}")
        print(f"  OpenAPI valid: {'✅' if functional['openapi_valid'] else '❌'}")
        print(f"  Endpoints tested: {functional['endpoints_tested']}")
        print(f"  Endpoints passed: {functional['endpoints_passed']}")
        
        if functional["errors"]:
            print("  Errors:")
            for error in functional["errors"]:
                print(f"    - {error}")
        
        # Print client test results
        print(f"\nCLIENT TESTS:")
        for language, result in results["client_tests"].items():
            print(f"\n  {language.upper()}:")
            print(f"    Exists: {'✅' if result['exists'] else '❌'}")
            
            if language == "typescript":
                print(f"    Builds: {'✅' if result['builds'] else '❌'}")
            elif language == "python":
                print(f"    Installs: {'✅' if result['installs'] else '❌'}")
                print(f"    Imports: {'✅' if result['imports'] else '❌'}")
            elif language == "java":
                print(f"    Compiles: {'✅' if result['compiles'] else '❌'}")
            
            print(f"    Has examples: {'✅' if result['has_examples'] else '❌'}")
            print(f"    Has docs: {'✅' if result['has_docs'] else '❌'}")
            
            if result["errors"]:
                print("    Errors:")
                for error in result["errors"]:
                    print(f"      - {error}")
        
        # Print structure test results
        print(f"\nSTRUCTURE TESTS:")
        for language, result in results["structure_tests"].items():
            print(f"\n  {language.upper()}:")
            print(f"    Exists: {'✅' if result['exists'] else '❌'}")
            print(f"    Structure valid: {'✅' if result['structure_valid'] else '❌'}")
            print(f"    Has API files: {'✅' if result['has_api_files'] else '❌'}")
            print(f"    Has model files: {'✅' if result['has_model_files'] else '❌'}")
            print(f"    Has docs: {'✅' if result['has_docs'] else '❌'}")
            print(f"    File count: {result['file_count']}")
            
            if result["errors"]:
                print("    Errors:")
                for error in result["errors"]:
                    print(f"      - {error}")
        
        print("\n" + "="*60)


def main():
    """Main function for command-line usage."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Test generated client SDKs")
    parser.add_argument(
        "--api-url",
        default="http://localhost:8000",
        help="Base URL of the API (default: http://localhost:8000)"
    )
    parser.add_argument(
        "--clients-dir",
        default="generated_clients",
        help="Directory containing generated clients (default: generated_clients)"
    )
    parser.add_argument(
        "--output-file",
        help="Save test results to JSON file"
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Enable verbose logging"
    )
    
    args = parser.parse_args()
    
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    
    # Create tester instance
    tester = ClientTester(args.api_url, args.clients_dir)
    
    # Run tests
    results = tester.run_all_tests()
    
    # Print results
    tester.print_results(results)
    
    # Save results to file if requested
    if args.output_file:
        with open(args.output_file, 'w') as f:
            json.dump(results, f, indent=2, default=str)
        logger.info(f"Test results saved to {args.output_file}")
    
    # Exit with error code if tests failed
    summary = results["summary"]
    if not summary["api_functional"] or summary["working_clients"] == 0:
        sys.exit(1)


if __name__ == "__main__":
    main()