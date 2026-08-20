# Copyright (c) 2026, Camptocamp SA
from unittest.mock import AsyncMock, MagicMock

import pytest

from shared_config_manager.security import User


@pytest.mark.asyncio
async def test_user_has_write_access_admin():
    """Test that admin users always have write access."""
    user = User(
        auth_type="github_oauth",
        login="testuser",
        name="Test User",
        url="https://github.com/testuser",
        is_auth=True,
        token="test_token",
    )

    user.is_admin = AsyncMock(return_value=True)

    source_config = {"auth": {"github_repository": "org/repo"}}
    assert await user.has_write_access(source_config) is True


@pytest.mark.asyncio
async def test_user_has_write_access_with_push_permission():
    """Test that users with push permission have write access."""
    user = User(
        auth_type="github_oauth",
        login="testuser",
        name="Test User",
        url="https://github.com/testuser",
        is_auth=True,
        token="test_token",
    )

    user.is_admin = AsyncMock(return_value=False)

    mock_auth_info = MagicMock()
    user.auth_info = mock_auth_info

    import c2casgiutils.auth

    original_check = c2casgiutils.auth.check_access

    async def mock_check_access(auth_info, auth_config):
        # Return True when checking write access
        return True

    c2casgiutils.auth.check_access = mock_check_access

    try:
        source_config = {"auth": {"github_repository": "org/repo"}}
        assert await user.has_write_access(source_config) is True
    finally:
        c2casgiutils.auth.check_access = original_check


@pytest.mark.asyncio
async def test_user_has_write_access_without_push_permission():
    """Test that users without push permission don't have write access."""
    user = User(
        auth_type="github_oauth",
        login="testuser",
        name="Test User",
        url="https://github.com/testuser",
        is_auth=True,
        token="test_token",
    )

    user.is_admin = AsyncMock(return_value=False)

    mock_auth_info = MagicMock()
    user.auth_info = mock_auth_info

    import c2casgiutils.auth

    original_check = c2casgiutils.auth.check_access

    async def mock_check_access(auth_info, auth_config):
        # Return False when checking write access
        return False

    c2casgiutils.auth.check_access = mock_check_access

    try:
        source_config = {"auth": {"github_repository": "org/repo"}}
        assert await user.has_write_access(source_config) is False
    finally:
        c2casgiutils.auth.check_access = original_check


@pytest.mark.asyncio
async def test_user_has_write_access_no_repo_config():
    """Test that users without repo config don't have write access."""
    user = User(
        auth_type="github_oauth",
        login="testuser",
        name="Test User",
        url="https://github.com/testuser",
        is_auth=True,
        token="test_token",
    )

    user.is_admin = AsyncMock(return_value=False)

    source_config = {}
    assert await user.has_write_access(source_config) is False
