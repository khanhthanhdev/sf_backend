"""
Dependency injection container module.
"""

from .dependency_container import (
    IDependencyContainer,
    DependencyContainer,
    ServiceLifetime,
    ServiceRegistration,
    get_container,
    set_container,
    initialize_container,
    cleanup_container
)

from .service_registration import (
    setup_service_container,
    create_test_container,
    get_video_generation_use_case,
    get_job_management_use_case,
    get_file_management_use_case,
    get_user_management_use_case
)

__all__ = [
    # Container classes
    'IDependencyContainer',
    'DependencyContainer',
    'ServiceLifetime',
    'ServiceRegistration',
    
    # Container management
    'get_container',
    'set_container',
    'initialize_container',
    'cleanup_container',
    
    # Service registration
    'setup_service_container',
    'create_test_container',
    
    # Service accessors
    'get_video_generation_use_case',
    'get_job_management_use_case',
    'get_file_management_use_case',
    'get_user_management_use_case'
]
