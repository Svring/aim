# python -m providers.codebase.codebase_provider

import httpx
from typing import Optional, Dict, Any
from datetime import datetime

from returns.result import Result, Success, Failure
from returns.future import FutureResult, future_safe
from returns.pipeline import is_successful

from .codebase_models import (
    CodebaseState,
    UserProject,
    CodebaseError,
    CodebaseOperation,
)


# Factory function for CodebaseError
def _make_codebase_error(
    message: str,
    operation_name: CodebaseOperation,
    user_id: Optional[str] = None,
    project_address: Optional[str] = None,
    details: Optional[str] = None,
) -> CodebaseError:
    """Factory for creating CodebaseError instances with consistent structure."""
    return CodebaseError(
        message=message,
        operation_name=operation_name,
        user_id=user_id,
        project_address=project_address,
        details=details,
    )


# Helper function for health check
@future_safe
async def _check_project_health(project_address: str) -> bool:
    """
    Performs a health check on the project's /galatea/health endpoint.
    Raises httpx.HTTPStatusError for non-2xx responses or httpx.RequestError for network issues.
    """
    health_check_url = f"{project_address}/galatea/health"
    async with httpx.AsyncClient() as client:
        response = await client.get(health_check_url, timeout=5.0)  # 5 second timeout
        response.raise_for_status()  # Raises HTTPStatusError for 4xx/5xx responses
        return response.status_code == 200


# Public API Functions


def create_codebase_state() -> CodebaseState:
    """Initializes an empty CodebaseState."""
    return CodebaseState()


def add_user_project(
    current_state: CodebaseState,
    user_id: str,
    project_address: str,
    metadata: Optional[Dict[str, Any]] = None,
) -> FutureResult[CodebaseState, CodebaseError]:
    """
    Adds or updates a user's project in the codebase state after a health check.
    If user_id exists and project_address/metadata are different, it updates.
    If user_id exists and project_address/metadata are identical, it updates the last_active_timestamp.
    Health check is performed for new projects or when project_address changes.
    """
    now = datetime.utcnow()
    new_project_details_for_comparison = UserProject(
        project_address=project_address,
        metadata=metadata,
        last_active_timestamp=now,  # Use consistent timestamp for comparison if needed
    )
    existing_project = current_state.user_projects.get(user_id)

    if existing_project:
        # Compare only project_address and metadata for substantial changes
        if (
            existing_project.project_address
            == new_project_details_for_comparison.project_address
            and existing_project.metadata == new_project_details_for_comparison.metadata
        ):
            # Details are the same, just update timestamp of the existing project record
            if (
                existing_project.last_active_timestamp == now
            ):  # Avoid redundant update if somehow called rapidly
                return FutureResult.from_result(Success(current_state))

            updated_project_with_new_timestamp = existing_project.model_copy(
                update={"last_active_timestamp": now}
            )
            updated_user_projects = {
                **current_state.user_projects,
                user_id: updated_project_with_new_timestamp,
            }
            return FutureResult.from_result(
                Success(
                    current_state.model_copy(
                        update={"user_projects": updated_user_projects}
                    )
                )
            )
        # If details are different, fall through to health check and full update logic

    # If new project or existing project with different address/metadata, create with fresh timestamp
    project_to_add_or_update = UserProject(
        project_address=project_address,
        metadata=metadata,
        last_active_timestamp=now,  # Ensures new/updated projects get current timestamp
    )

    # Proceed with health check for new project or for existing project with changed details
    return (
        _check_project_health(project_to_add_or_update.project_address)
        .bind_result(
            lambda is_healthy: (
                Success(is_healthy)
                if is_healthy
                else Failure(
                    _make_codebase_error(
                        message=f"Health check failed for project: {project_to_add_or_update.project_address}",
                        operation_name=CodebaseOperation.ADD_USER_PROJECT_HEALTH_CHECK_FAILED,
                        user_id=user_id,
                        project_address=project_to_add_or_update.project_address,
                        details="Health endpoint did not return 200 or was unreachable.",
                    )
                )
            )
        )
        .map(
            lambda _health_check_passed: current_state.model_copy(
                update={
                    "user_projects": {
                        **current_state.user_projects,
                        user_id: project_to_add_or_update,  # Add or update with new details & timestamp
                    }
                }
            )
        )
        .lash(
            lambda error_obj: FutureResult.from_result(
                Failure(
                    error_obj
                    if isinstance(error_obj, CodebaseError)
                    else _make_codebase_error(
                        message=f"HTTP error during health check for project: {project_to_add_or_update.project_address}",
                        operation_name=CodebaseOperation.ADD_USER_PROJECT_HTTP_ERROR,
                        user_id=user_id,
                        project_address=project_to_add_or_update.project_address,
                        details=str(error_obj),
                    )
                )
            )
        )
    )


def get_user_project(
    state: CodebaseState, user_id: str
) -> Result[UserProject, CodebaseError]:
    """Retrieves a user's project from the codebase state."""
    project = state.user_projects.get(user_id)
    if project is None:
        return Failure(
            _make_codebase_error(
                message=f"User project for user_id '{user_id}' not found.",
                operation_name=CodebaseOperation.GET_USER_PROJECT_NOT_FOUND,
                user_id=user_id,
            )
        )
    return Success(project)


def remove_user_project(
    current_state: CodebaseState, user_id: str
) -> Result[CodebaseState, CodebaseError]:
    """Removes a user's project from the codebase state."""
    if user_id not in current_state.user_projects:
        return Failure(
            _make_codebase_error(
                message=f"User project for user_id '{user_id}' not found for removal.",
                operation_name=CodebaseOperation.REMOVE_USER_PROJECT_NOT_FOUND,
                user_id=user_id,
            )
        )

    updated_projects = {
        k: v for k, v in current_state.user_projects.items() if k != user_id
    }
    return Success(current_state.model_copy(update={"user_projects": updated_projects}))


def update_user_project_metadata(
    current_state: CodebaseState,
    user_id: str,
    new_metadata: Optional[Dict[str, Any]],
) -> Result[CodebaseState, CodebaseError]:
    """Updates the metadata for a user's project in the codebase state."""
    project_to_update = current_state.user_projects.get(user_id)

    if project_to_update is None:
        return Failure(
            _make_codebase_error(
                message=f"User project for user_id '{user_id}' not found for metadata update.",
                operation_name=CodebaseOperation.UPDATE_USER_PROJECT_METADATA_NOT_FOUND,
                user_id=user_id,
            )
        )

    updated_project = project_to_update.model_copy(update={"metadata": new_metadata})
    updated_projects = {
        **current_state.user_projects,
        user_id: updated_project,
    }
    return Success(current_state.model_copy(update={"user_projects": updated_projects}))


# --- TEST CODE ---
# The following code is for testing purposes.
# To run these tests, use pytest:
# PYTHONPATH=. pytest aim/providers/codebase/codebase_provider.py

import pytest  # type: ignore

# Mark all tests in this section as asyncio
pytestmark = pytest.mark.asyncio

from unittest.mock import patch, MagicMock, AsyncMock

# CodebaseState, UserProject, CodebaseError, CodebaseOperation are imported from .codebase_models
# create_codebase_state, add_user_project, _make_codebase_error, _check_project_health are in global scope

# httpx, Success, Failure, FutureResult, is_successful are already imported above.


@pytest.fixture
def initial_codebase_state_test() -> CodebaseState:  # Renamed fixture
    """Provides an empty CodebaseState for tests."""
    return create_codebase_state()


def test_create_codebase_state_internal():  # Renamed test
    """Test that create_codebase_state returns an empty CodebaseState."""
    state = create_codebase_state()
    assert isinstance(state, CodebaseState)
    assert state.user_projects == {}


async def test_add_user_project_success_internal(
    initial_codebase_state_test: CodebaseState,
):  # Renamed test
    """Test successfully adding a new user project when health check passes."""
    user_id = "test_user_1"
    project_address = "http://healthy.project.dev"
    metadata = {"description": "A healthy project"}

    # _check_project_health is in global scope here
    with patch(
        "aim.providers.codebase.codebase_provider._check_project_health",  # Path to the function in this module
        return_value=FutureResult.from_result(Success(True)),
    ) as mock_health_check:
        result = await add_user_project(
            initial_codebase_state_test, user_id, project_address, metadata
        )

    assert is_successful(result)
    updated_state = result.unwrap()
    mock_health_check.assert_awaited_once_with(project_address)

    assert user_id in updated_state.user_projects
    project = updated_state.user_projects[user_id]
    assert project.project_address == project_address
    assert project.metadata == metadata
    assert len(updated_state.user_projects) == 1


async def test_add_user_project_existing_user_scenarios_internal(
    initial_codebase_state_test: CodebaseState,
):  # Renamed test
    """Tests scenarios for add_user_project when user_id already exists."""
    user_id = "existing_user"
    original_address = "http://original.dev"
    original_metadata = {"version": 1}
    original_project = UserProject(
        project_address=original_address, metadata=original_metadata
    )

    state_with_existing_project = initial_codebase_state_test.model_copy(
        update={"user_projects": {user_id: original_project}}
    )

    # Scenario 1: user_id exists, identical data provided
    # Expect: success, state remains unchanged (same object ideally, or equal)
    with patch(
        "aim.providers.codebase.codebase_provider._check_project_health"
    ) as mock_health_check_identical:
        result_identical = await add_user_project(
            state_with_existing_project, user_id, original_address, original_metadata
        )

    assert is_successful(result_identical)
    updated_state_identical = result_identical.unwrap()
    assert (
        updated_state_identical == state_with_existing_project
    )  # State should be identical
    assert user_id in updated_state_identical.user_projects
    assert updated_state_identical.user_projects[user_id] == original_project
    mock_health_check_identical.assert_not_awaited()  # Health check should be skipped

    # Scenario 2: user_id exists, different metadata, health check on original address passes
    updated_metadata = {"version": 2}
    expected_updated_project_meta_only = UserProject(
        project_address=original_address, metadata=updated_metadata
    )
    with patch(
        "aim.providers.codebase.codebase_provider._check_project_health",
        return_value=FutureResult.from_result(Success(True)),
    ) as mock_health_check_meta_update:
        result_meta_update = await add_user_project(
            state_with_existing_project,
            user_id,
            original_address,
            updated_metadata,  # new metadata
        )

    assert is_successful(result_meta_update)
    updated_state_meta = result_meta_update.unwrap()
    mock_health_check_meta_update.assert_awaited_once_with(original_address)
    assert user_id in updated_state_meta.user_projects
    assert (
        updated_state_meta.user_projects[user_id] == expected_updated_project_meta_only
    )
    assert updated_state_meta.user_projects[user_id].metadata == updated_metadata

    # Scenario 3: user_id exists, different project_address, health check on NEW address passes
    new_address = "http://newaddress.dev"
    expected_updated_project_new_address = UserProject(
        project_address=new_address, metadata=original_metadata
    )
    with patch(
        "aim.providers.codebase.codebase_provider._check_project_health",
        return_value=FutureResult.from_result(Success(True)),
    ) as mock_health_check_addr_update:
        result_addr_update = await add_user_project(
            state_with_existing_project,
            user_id,
            new_address,
            original_metadata,  # new address
        )

    assert is_successful(result_addr_update)
    updated_state_addr = result_addr_update.unwrap()
    # Health check should be on the new_address
    mock_health_check_addr_update.assert_awaited_once_with(new_address)
    assert user_id in updated_state_addr.user_projects
    assert (
        updated_state_addr.user_projects[user_id]
        == expected_updated_project_new_address
    )
    assert updated_state_addr.user_projects[user_id].project_address == new_address

    # Scenario 4: user_id exists, different project_address, health check on NEW address FAILS
    failing_new_address = "http://failingnew.dev"
    health_fail_error = _make_codebase_error(
        message=f"Health check failed for project: {failing_new_address}",
        operation_name=CodebaseOperation.ADD_USER_PROJECT_HEALTH_CHECK_FAILED,
        user_id=user_id,
        project_address=failing_new_address,
        details="Health endpoint did not return 200 or was unreachable.",
    )
    with patch(
        "aim.providers.codebase.codebase_provider._check_project_health",
        # Simulate health check failing specifically for the new address
        return_value=FutureResult.from_result(Success(False)),
    ) as mock_health_check_addr_fail:
        result_addr_fail = await add_user_project(
            state_with_existing_project, user_id, failing_new_address, original_metadata
        )

    assert not is_successful(result_addr_fail)
    error_addr_fail = result_addr_fail.failure()
    mock_health_check_addr_fail.assert_awaited_once_with(failing_new_address)
    assert isinstance(error_addr_fail, CodebaseError)
    # We need to compare the generated error with what we expect
    # The _make_codebase_error inside bind_result creates this
    assert (
        error_addr_fail.operation_name
        == CodebaseOperation.ADD_USER_PROJECT_HEALTH_CHECK_FAILED
    )
    assert error_addr_fail.project_address == failing_new_address
    assert error_addr_fail.user_id == user_id


async def test_add_user_project_health_check_fails_internal(  # Renamed test
    initial_codebase_state_test: CodebaseState,
):
    """Test adding a project when the health check returns a Failure from bind_result."""
    user_id = "test_user_unhealthy"
    project_address = "http://unhealthy.project.dev"

    # This error is constructed inside add_user_project when _check_project_health's result leads to Failure
    expected_constructed_error = _make_codebase_error(
        message=f"Health check failed for project: {project_address}",
        operation_name=CodebaseOperation.ADD_USER_PROJECT_HEALTH_CHECK_FAILED,
        user_id=user_id,
        project_address=project_address,
        details="Health endpoint did not return 200 or was unreachable.",
    )

    with patch(
        "aim.providers.codebase.codebase_provider._check_project_health",
        # Simulate _check_project_health returning Success(False) which then causes
        # add_user_project's bind_result to create the CodebaseError
        return_value=FutureResult.from_result(Success(False)),
    ) as mock_health_check:
        result = await add_user_project(
            initial_codebase_state_test, user_id, project_address
        )

    mock_health_check.assert_awaited_once_with(project_address)
    assert not is_successful(result)
    error = result.failure()
    assert isinstance(error, CodebaseError)
    assert error == expected_constructed_error  # Compare the actual error object


async def test_add_user_project_health_check_http_error_internal(  # Renamed test
    initial_codebase_state_test: CodebaseState,
):
    """Test adding a project when the health check itself raises an HTTP exception."""
    user_id = "test_user_http_error"
    project_address = "http://error.project.dev"
    http_exception = httpx.RequestError("Network trouble", request=MagicMock())

    with patch(
        "aim.providers.codebase.codebase_provider._check_project_health",
        return_value=FutureResult.from_failure(http_exception),
    ) as mock_health_check:
        result = await add_user_project(
            initial_codebase_state_test, user_id, project_address
        )

    mock_health_check.assert_awaited_once_with(project_address)
    assert not is_successful(result)
    error = result.failure()

    assert isinstance(error, CodebaseError)
    assert error.operation_name == CodebaseOperation.ADD_USER_PROJECT_HTTP_ERROR
    assert error.user_id == user_id
    assert error.project_address == project_address
    assert "HTTP error during health check" in error.message
    assert str(http_exception) in error.details


@patch("httpx.AsyncClient")
async def test_check_project_health_success_internal(MockAsyncClient):  # Renamed test
    """Test _check_project_health success path."""
    mock_response = MagicMock()
    mock_response.status_code = 200
    # mock_response.raise_for_status = MagicMock() # Not strictly needed if status_code is 200

    mock_client_instance = MockAsyncClient.return_value.__aenter__.return_value
    mock_client_instance.get = AsyncMock(return_value=mock_response)

    project_address = "http://working.example.com"

    # _check_project_health is in global scope
    result_fr = _check_project_health(project_address)
    result_io = await result_fr.awaitable()

    assert is_successful(result_io)
    assert result_io.unwrap() is True
    mock_client_instance.get.assert_awaited_once_with(
        f"{project_address}/galatea/health", timeout=5.0
    )
    mock_response.raise_for_status.assert_called_once()


@patch("httpx.AsyncClient")
async def test_check_project_health_failure_status_internal(
    MockAsyncClient,
):  # Renamed test
    """Test _check_project_health with non-200 status."""
    mock_response = MagicMock()
    mock_response.status_code = 404
    mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
        "Not Found", request=MagicMock(), response=mock_response
    )

    mock_client_instance = MockAsyncClient.return_value.__aenter__.return_value
    mock_client_instance.get = AsyncMock(return_value=mock_response)

    project_address = "http://notfound.example.com"

    result_fr = _check_project_health(
        project_address
    )  # _check_project_health is in global scope
    result_io = await result_fr.awaitable()

    assert not is_successful(result_io)
    assert isinstance(result_io.failure(), httpx.HTTPStatusError)


@patch("httpx.AsyncClient")
async def test_check_project_health_request_error_internal(
    MockAsyncClient,
):  # Renamed test
    """Test _check_project_health with httpx.RequestError."""
    request_error = httpx.RequestError("Connection failed", request=MagicMock())

    mock_client_instance = MockAsyncClient.return_value.__aenter__.return_value
    mock_client_instance.get = AsyncMock(side_effect=request_error)

    project_address = "http://unreachable.example.com"

    result_fr = _check_project_health(
        project_address
    )  # _check_project_health is in global scope
    result_io = await result_fr.awaitable()

    assert not is_successful(result_io)
    assert result_io.failure() is request_error


# Tests for get_user_project
def test_get_user_project_success_internal(initial_codebase_state_test: CodebaseState):
    user_id = "user_to_get"
    project_data = UserProject(
        project_address="http://gettable.dev", metadata={"info": "some data"}
    )
    state_with_project = initial_codebase_state_test.model_copy(
        update={"user_projects": {user_id: project_data}}
    )
    result = get_user_project(state_with_project, user_id)
    assert is_successful(result)
    assert result.unwrap() == project_data


def test_get_user_project_not_found_internal(
    initial_codebase_state_test: CodebaseState,
):
    user_id = "user_not_exists"
    result = get_user_project(initial_codebase_state_test, user_id)
    assert not is_successful(result)
    error = result.failure()
    assert isinstance(error, CodebaseError)
    assert error.operation_name == CodebaseOperation.GET_USER_PROJECT_NOT_FOUND
    assert error.user_id == user_id


# Tests for remove_user_project
def test_remove_user_project_success_internal(
    initial_codebase_state_test: CodebaseState,
):
    user_id_to_remove = "user_to_remove"
    user_id_to_keep = "user_to_keep"
    project_to_remove = UserProject(project_address="http://removable.dev")
    project_to_keep = UserProject(project_address="http://keepable.dev")

    state_with_projects = initial_codebase_state_test.model_copy(
        update={
            "user_projects": {
                user_id_to_remove: project_to_remove,
                user_id_to_keep: project_to_keep,
            }
        }
    )
    result = remove_user_project(state_with_projects, user_id_to_remove)
    assert is_successful(result)
    updated_state = result.unwrap()
    assert user_id_to_remove not in updated_state.user_projects
    assert user_id_to_keep in updated_state.user_projects
    assert len(updated_state.user_projects) == 1


def test_remove_user_project_not_found_internal(
    initial_codebase_state_test: CodebaseState,
):
    user_id = "user_not_exists_for_removal"
    result = remove_user_project(initial_codebase_state_test, user_id)
    assert not is_successful(result)
    error = result.failure()
    assert isinstance(error, CodebaseError)
    assert error.operation_name == CodebaseOperation.REMOVE_USER_PROJECT_NOT_FOUND
    assert error.user_id == user_id


# Tests for update_user_project_metadata
def test_update_user_project_metadata_success_internal(
    initial_codebase_state_test: CodebaseState,
):
    user_id = "user_to_update"
    original_metadata = {"version": 1, "status": "active"}
    new_metadata = {"version": 2, "status": "archived", "notes": "updated"}
    project_to_update = UserProject(
        project_address="http://updatable.dev", metadata=original_metadata
    )

    state_with_project = initial_codebase_state_test.model_copy(
        update={"user_projects": {user_id: project_to_update}}
    )

    result = update_user_project_metadata(state_with_project, user_id, new_metadata)
    assert is_successful(result)
    updated_state = result.unwrap()
    assert updated_state.user_projects[user_id].metadata == new_metadata
    assert (
        updated_state.user_projects[user_id].project_address == "http://updatable.dev"
    )


def test_update_user_project_metadata_clear_internal(
    initial_codebase_state_test: CodebaseState,
):
    user_id = "user_clear_meta"
    original_metadata = {"data": "some_data"}
    project_to_update = UserProject(
        project_address="http://clearable.dev", metadata=original_metadata
    )
    state_with_project = initial_codebase_state_test.model_copy(
        update={"user_projects": {user_id: project_to_update}}
    )
    result = update_user_project_metadata(
        state_with_project, user_id, None
    )  # Clear metadata
    assert is_successful(result)
    updated_state = result.unwrap()
    assert updated_state.user_projects[user_id].metadata is None


def test_update_user_project_metadata_not_found_internal(
    initial_codebase_state_test: CodebaseState,
):
    user_id = "user_not_exists_for_update"
    new_metadata = {"error": "this should not be applied"}
    result = update_user_project_metadata(
        initial_codebase_state_test, user_id, new_metadata
    )
    assert not is_successful(result)
    error = result.failure()
    assert isinstance(error, CodebaseError)
    assert (
        error.operation_name == CodebaseOperation.UPDATE_USER_PROJECT_METADATA_NOT_FOUND
    )
    assert error.user_id == user_id


if __name__ == "__main__":
    # This allows running the tests in this file directly:
    # python -m aim.providers.codebase.codebase_provider
    # or from the project root, ensure PYTHONPATH is set:
    # PYTHONPATH=. python aim/providers/codebase/codebase_provider.py

    # pytest is already imported within the TEST CODE section with type: ignore
    # However, to be clean for a __main__ block, let's ensure it's available.
    try:
        import pytest  # type: ignore
    except ImportError:
        print(
            "pytest is not installed. Please install it to run the tests: pip install pytest pytest-asyncio"
        )
        exit(1)

    # The tests are marked with pytestmark = pytest.mark.asyncio implicitly via pytest-asyncio
    # when run with the pytest command.
    # When running pytest.main() programmatically, pytest-asyncio should still pick them up.

    # Get the path to the current file
    import os

    current_file_path = os.path.abspath(__file__)

    # Run pytest on the current file
    # The exit code of pytest.main will be the exit code of the script
    exit_code = pytest.main([current_file_path, "-v"])
    exit(exit_code)
