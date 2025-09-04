#!/usr/bin/env python3
"""
Development setup script.
Creates necessary directories and validates configuration.
"""

import os
import sys
from pathlib import Path


def create_directories():
    """Create necessary directories for the application."""
    directories = [
        "uploads",
        "videos", 
        "logs",
        "data",
    ]
    
    for directory in directories:
        Path(directory).mkdir(exist_ok=True)
        print(f"✓ Created directory: {directory}")


def check_env_file():
    """Check if .env file exists and create from example if not."""
    env_file = Path(".env")
    env_example = Path(".env.example")
    
    if not env_file.exists():
        if env_example.exists():
            # Copy example to .env
            env_file.write_text(env_example.read_text())
            print("✓ Created .env file from .env.example")
            print("⚠️  Please update the .env file with your actual configuration values")
        else:
            print("❌ .env.example file not found")
            return False
    else:
        print("✓ .env file already exists")
    
    return True


def validate_required_env_vars():
    """Validate that required environment variables are set."""
    from dotenv import load_dotenv
    
    load_dotenv()
    
    required_vars = [
        "CLERK_SECRET_KEY",
        "CLERK_PUBLISHABLE_KEY", 
        "SECRET_KEY",
    ]
    
    missing_vars = []
    for var in required_vars:
        if not os.getenv(var) or os.getenv(var) == f"your_{var.lower()}_here":
            missing_vars.append(var)
    
    if missing_vars:
        print("❌ Missing required environment variables:")
        for var in missing_vars:
            print(f"   - {var}")
        print("\nPlease update your .env file with actual values.")
        return False
    
    print("✓ All required environment variables are set")
    return True


def main():
    """Main setup function."""
    print("🚀 Setting up FastAPI Video Backend development environment...\n")
    
    # Create directories
    create_directories()
    print()
    
    # Check .env file
    if not check_env_file():
        sys.exit(1)
    print()
    
    # Validate environment variables
    try:
        if not validate_required_env_vars():
            print("\n⚠️  Setup completed with warnings. Please fix the issues above.")
            sys.exit(1)
    except ImportError:
        print("⚠️  python-dotenv not installed. Skipping environment validation.")
        print("   Install dependencies with: pip install -e .")
    
    print("\n✅ Development environment setup completed!")
    print("\nNext steps:")
    print("1. Install dependencies: pip install -e .")
    print("2. Update .env file with your actual configuration values")
    print("3. Redis has been removed - application now uses database-only storage")
    print("4. Run the application: python -m src.app.main")
    print("5. Visit http://localhost:8000/docs for API documentation")


if __name__ == "__main__":
    main()