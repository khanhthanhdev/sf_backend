"""
Refactored service layer following SOLID principles.

This module provides a clean, testable, and maintainable service layer
with proper separation of concerns, dependency injection, and interfaces.

The service layer is organized into three tiers:
1. Domain Services: Pure business logic
2. Application Services: Use case orchestration  
3. Infrastructure Services: External system integration

Usage:
    # Setup dependency injection container
    from .core.container import setup_service_container, initialize_container
    
    container = setup_service_container()
    await initialize_container()
    
    # Use services through dependency injection
    from .core.container import get_video_generation_use_case
    
    video_use_case = get_video_generation_use_case()
    result = await video_use_case.generate_video(request, user)
"""

# Import service interfaces
from .interfaces import *

# Import domain services
from .domain import *

# Import application services
from .application import *

# Import infrastructure services  
from .infrastructure import *

# Import dependency injection container
from ..core.container import (
    setup_service_container,
    get_container,
    initialize_container,
    cleanup_container,
    get_video_generation_use_case,
    get_job_management_use_case,
    get_file_management_use_case,
    get_user_management_use_case
)

__all__ = [
    # Container setup
    'setup_service_container',
    'get_container', 
    'initialize_container',
    'cleanup_container',
    
    # Service accessors
    'get_video_generation_use_case',
    'get_job_management_use_case', 
    'get_file_management_use_case',
    'get_user_management_use_case'
]