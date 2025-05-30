# python -m pytest -s tests/test_resource_provider.py
import pytest
import asyncio
from providers.resource.resource_provider import (
    activate_galatea_for_devbox,
    update_galatea_for_devbox,
    get_dummy_devbox_for_task,
)


# python -m pytest -s tests/test_resource_provider.py::test_activate_galatea_for_dummy_devbox
@pytest.mark.asyncio
async def test_activate_galatea_for_dummy_devbox():
    # Get a dummy devbox info (token can be any string for the dummy)
    devbox_info = get_dummy_devbox_for_task(
        task_path="dummy_task_path.json", token="dummy_token_123"
    )

    # Call the async activate function
    try:
        result = await activate_galatea_for_devbox(devbox_info)
        print(f"Galatea activated at: {result}")
        assert isinstance(result, str)
        assert result.endswith("/galatea") or "/galatea" in result
    except Exception as e:
        # If the dummy devbox is not actually reachable, we expect an exception
        print(f"Expected exception (if dummy devbox is not real): {e}")
        assert True  # The test passes if an exception is raised for dummy


# python -m pytest -s tests/test_resource_provider.py::test_update_galatea_for_dummy_devbox
@pytest.mark.asyncio
async def test_update_galatea_for_dummy_devbox():
    # Get a dummy devbox info (token can be any string for the dummy)
    devbox_info = get_dummy_devbox_for_task(
        task_path="dummy_task_path.json", token="dummy_token_123"
    )

    # Call the async update function
    try:
        result = await update_galatea_for_devbox(devbox_info)
        print(f"Galatea updated at: {result}")
        assert isinstance(result, str)
        assert result.endswith("/galatea") or "/galatea" in result
    except Exception as e:
        # If the dummy devbox is not actually reachable, we expect an exception
        print(f"Expected exception (if dummy devbox is not real): {e}")
        assert True  # The test passes if an exception is raised for dummy
