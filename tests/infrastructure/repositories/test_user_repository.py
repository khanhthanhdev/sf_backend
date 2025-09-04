"""
Unit tests for user repository implementation.

Tests cover CRUD operations, business logic, error handling,
and edge cases for the UserRepository.
"""

import pytest
from uuid import uuid4
from datetime import datetime

from src.domain.value_objects import UserId, EmailAddress
from src.infrastructure.repositories import UserRepository, PaginationParams
from .conftest import UserFactory, create_test_user


class TestUserRepository:
    """Test suite for UserRepository."""
    
    async def test_create_user_success(self, user_repository: UserRepository):
        """Test successful user creation."""
        user = UserFactory.create_user()
        
        result = await user_repository.create(user)
        
        assert result.success
        assert result.value.user_id == user.user_id
        assert result.value.clerk_user_id == user.clerk_user_id
        assert result.value.primary_email == user.primary_email
    
    async def test_create_user_duplicate_clerk_id_fails(self, user_repository: UserRepository):
        """Test that creating user with duplicate Clerk ID fails."""
        clerk_id = f"clerk_{uuid4().hex[:8]}"
        
        # Create first user
        user1 = UserFactory.create_user(clerk_user_id=clerk_id)
        result1 = await user_repository.create(user1)
        assert result1.success
        
        # Try to create second user with same Clerk ID
        user2 = UserFactory.create_user(clerk_user_id=clerk_id)
        result2 = await user_repository.create(user2)
        assert not result2.success
    
    async def test_get_by_id_existing_user(self, user_repository: UserRepository):
        """Test getting existing user by ID."""
        user = await create_test_user(user_repository)
        
        result = await user_repository.get_by_id(uuid4(user.user_id.value))
        
        assert result.success
        assert result.value is not None
        assert result.value.user_id == user.user_id
    
    async def test_get_by_id_non_existing_user(self, user_repository: UserRepository):
        """Test getting non-existing user by ID."""
        non_existing_id = uuid4()
        
        result = await user_repository.get_by_id(non_existing_id)
        
        assert result.success
        assert result.value is None
    
    async def test_get_by_clerk_id_existing_user(self, user_repository: UserRepository):
        """Test getting existing user by Clerk ID."""
        user = await create_test_user(user_repository)
        
        result = await user_repository.get_by_clerk_id(user.clerk_user_id)
        
        assert result.success
        assert result.value is not None
        assert result.value.clerk_user_id == user.clerk_user_id
    
    async def test_get_by_clerk_id_non_existing_user(self, user_repository: UserRepository):
        """Test getting non-existing user by Clerk ID."""
        non_existing_clerk_id = f"clerk_{uuid4().hex}"
        
        result = await user_repository.get_by_clerk_id(non_existing_clerk_id)
        
        assert result.success
        assert result.value is None
    
    async def test_get_by_email_existing_user(self, user_repository: UserRepository):
        """Test getting existing user by email."""
        user = await create_test_user(user_repository)
        
        result = await user_repository.get_by_email(user.primary_email.value)
        
        assert result.success
        assert result.value is not None
        assert result.value.primary_email == user.primary_email
    
    async def test_get_by_email_non_existing_user(self, user_repository: UserRepository):
        """Test getting non-existing user by email."""
        non_existing_email = f"nonexisting_{uuid4().hex}@example.com"
        
        result = await user_repository.get_by_email(non_existing_email)
        
        assert result.success
        assert result.value is None
    
    async def test_update_user_success(self, user_repository: UserRepository):
        """Test successful user update."""
        user = await create_test_user(user_repository)
        
        # Update user properties
        user._first_name = "Updated"
        user._last_name = "Name"
        user._updated_at = datetime.utcnow()
        
        result = await user_repository.update(user)
        
        assert result.success
        assert result.value.first_name == "Updated"
        assert result.value.last_name == "Name"
    
    async def test_update_non_existing_user(self, user_repository: UserRepository):
        """Test updating non-existing user."""
        user = UserFactory.create_user()  # Not saved to database
        
        result = await user_repository.update(user)
        
        # Should still succeed but won't update anything
        assert result.success
        assert result.value is None  # No user found to update
    
    async def test_delete_user_success(self, user_repository: UserRepository):
        """Test successful user deletion (soft delete)."""
        user = await create_test_user(user_repository)
        
        result = await user_repository.delete(uuid4(user.user_id.value))
        
        assert result.success
        assert result.value is True
        
        # Verify user is soft deleted
        get_result = await user_repository.get_by_id(uuid4(user.user_id.value))
        assert get_result.success
        assert get_result.value is None  # Should not find deleted user
    
    async def test_delete_non_existing_user(self, user_repository: UserRepository):
        """Test deleting non-existing user."""
        non_existing_id = uuid4()
        
        result = await user_repository.delete(non_existing_id)
        
        assert result.success
        assert result.value is False  # No user was deleted
    
    async def test_list_users_no_filters(self, user_repository: UserRepository):
        """Test listing users without filters."""
        # Create test users
        users = []
        for i in range(3):
            user = await create_test_user(user_repository, 
                                        email=f"user{i}@example.com")
            users.append(user)
        
        result = await user_repository.list()
        
        assert result.success
        assert len(result.value.items) >= 3  # At least our test users
        assert result.value.total_count >= 3
    
    async def test_list_users_with_pagination(self, user_repository: UserRepository):
        """Test listing users with pagination."""
        # Create test users
        for i in range(5):
            await create_test_user(user_repository, 
                                 email=f"paging_user{i}@example.com")
        
        pagination = PaginationParams(page=1, size=2)
        result = await user_repository.list(pagination=pagination)
        
        assert result.success
        assert len(result.value.items) <= 2
        assert result.value.page == 1
        assert result.value.size == 2
    
    async def test_list_users_with_role_filter(self, user_repository: UserRepository):
        """Test listing users filtered by role."""
        # Create users with different roles
        await create_test_user(user_repository, role="admin", 
                             email="admin@example.com")
        await create_test_user(user_repository, role="user", 
                             email="user@example.com")
        
        result = await user_repository.list(filters={"role": "admin"})
        
        assert result.success
        assert all(user.role == "admin" for user in result.value.items)
    
    async def test_list_users_with_status_filter(self, user_repository: UserRepository):
        """Test listing users filtered by status."""
        # Create users with different statuses
        await create_test_user(user_repository, status="active", 
                             email="active@example.com")
        await create_test_user(user_repository, status="inactive", 
                             email="inactive@example.com")
        
        result = await user_repository.list(filters={"status": "active"})
        
        assert result.success
        assert all(user.status == "active" for user in result.value.items)
    
    async def test_exists_existing_user(self, user_repository: UserRepository):
        """Test checking existence of existing user."""
        user = await create_test_user(user_repository)
        
        result = await user_repository.exists(uuid4(user.user_id.value))
        
        assert result.success
        assert result.value is True
    
    async def test_exists_non_existing_user(self, user_repository: UserRepository):
        """Test checking existence of non-existing user."""
        non_existing_id = uuid4()
        
        result = await user_repository.exists(non_existing_id)
        
        assert result.success
        assert result.value is False
    
    async def test_count_users_no_filters(self, user_repository: UserRepository):
        """Test counting users without filters."""
        # Create test users
        initial_count_result = await user_repository.count()
        initial_count = initial_count_result.value if initial_count_result.success else 0
        
        for i in range(3):
            await create_test_user(user_repository, 
                                 email=f"count_user{i}@example.com")
        
        result = await user_repository.count()
        
        assert result.success
        assert result.value == initial_count + 3
    
    async def test_count_users_with_filters(self, user_repository: UserRepository):
        """Test counting users with filters."""
        # Create users with specific role
        for i in range(2):
            await create_test_user(user_repository, role="test_role",
                                 email=f"test_role_user{i}@example.com")
        
        result = await user_repository.count(filters={"role": "test_role"})
        
        assert result.success
        assert result.value >= 2
    
    async def test_get_active_users(self, user_repository: UserRepository):
        """Test getting active users."""
        # Create active and inactive users
        await create_test_user(user_repository, status="active",
                             email="active1@example.com")
        await create_test_user(user_repository, status="inactive",
                             email="inactive1@example.com")
        
        result = await user_repository.get_active_users()
        
        assert result.success
        assert all(user.status == "active" for user in result.value.items)
    
    async def test_get_users_by_role(self, user_repository: UserRepository):
        """Test getting users by role."""
        # Create users with specific role
        await create_test_user(user_repository, role="manager",
                             email="manager1@example.com")
        await create_test_user(user_repository, role="employee",
                             email="employee1@example.com")
        
        result = await user_repository.get_users_by_role("manager")
        
        assert result.success
        assert all(user.role == "manager" for user in result.value.items)
    
    async def test_list_users_sorting(self, user_repository: UserRepository):
        """Test listing users with sorting."""
        # Create users with different creation times
        user1 = await create_test_user(user_repository, 
                                     email="sort1@example.com")
        user2 = await create_test_user(user_repository, 
                                     email="sort2@example.com")
        
        # Test ascending sort by created_at
        pagination = PaginationParams(sort_by="created_at", sort_order="asc")
        result = await user_repository.list(pagination=pagination)
        
        assert result.success
        assert len(result.value.items) >= 2
        
        # Find our test users in the results
        test_users = [u for u in result.value.items 
                     if u.primary_email.value in ["sort1@example.com", "sort2@example.com"]]
        assert len(test_users) == 2
    
    async def test_pagination_edge_cases(self, user_repository: UserRepository):
        """Test pagination edge cases."""
        # Test invalid page number
        pagination = PaginationParams(page=0, size=10)
        with pytest.raises(ValueError, match="Page must be >= 1"):
            await user_repository.list(pagination=pagination)
        
        # Test invalid page size
        pagination = PaginationParams(page=1, size=0)
        with pytest.raises(ValueError, match="Size must be between 1 and 100"):
            await user_repository.list(pagination=pagination)
        
        # Test large page size
        pagination = PaginationParams(page=1, size=101)
        with pytest.raises(ValueError, match="Size must be between 1 and 100"):
            await user_repository.list(pagination=pagination)
    
    async def test_repository_error_handling(self, user_repository: UserRepository):
        """Test repository error handling."""
        # Test with invalid data that should cause database error
        user = UserFactory.create_user()
        user._clerk_user_id = None  # This should cause an error
        
        result = await user_repository.create(user)
        
        assert not result.success
        assert "Failed to create user" in result.error
