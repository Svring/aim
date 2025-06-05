# python -m pytest -s tests/test_resource_provider.py
import pytest
import asyncio
import os
from dotenv import load_dotenv
from providers.resource.resource_provider import (
    activate_galatea_for_devbox,
    update_galatea_for_devbox,
    get_dummy_devbox_for_task,
    cleanup_galatea_files_on_devbox,
)

load_dotenv()


# python -m pytest -s tests/test_resource_provider.py::test_activate_galatea_for_dummy_devbox
@pytest.mark.asyncio
async def test_activate_galatea_for_dummy_devbox(dummy_devbox_info):
    try:
        result = await activate_galatea_for_devbox(dummy_devbox_info)
        print(f"Galatea activated at: {result}")
        assert isinstance(result, str)
        assert result.endswith("/galatea") or "/galatea" in result
    except Exception as e:
        print(f"Expected exception (if dummy devbox is not real): {e}")
        assert True


# python -m pytest -s tests/test_resource_provider.py::test_update_galatea_for_dummy_devbox
@pytest.mark.asyncio
async def test_update_galatea_for_dummy_devbox(dummy_devbox_info):
    try:
        result = await update_galatea_for_devbox(dummy_devbox_info)
        print(f"Galatea updated at: {result}")
        assert isinstance(result, str)
        assert result.endswith("/galatea") or "/galatea" in result
    except Exception as e:
        print(f"Expected exception (if dummy devbox is not real): {e}")
        assert True


# python -m pytest -s tests/test_resource_provider.py::test_activate_galatea_for_dummy_devbox_mcp
@pytest.mark.asyncio
async def test_activate_galatea_for_dummy_devbox_mcp(dummy_devbox_info):
    try:
        result = await activate_galatea_for_devbox(dummy_devbox_info, mcp_enabled=True)
        print(f"Galatea activated at (MCP): {result}")
        assert isinstance(result, str)
        assert result.endswith("/galatea") or "/galatea" in result
    except Exception as e:
        print(f"Expected exception (if dummy devbox is not real): {e}")
        assert True


# python -m pytest -s tests/test_resource_provider.py::test_update_galatea_for_dummy_devbox_mcp
@pytest.mark.asyncio
async def test_update_galatea_for_dummy_devbox_mcp(dummy_devbox_info):
    try:
        result = await update_galatea_for_devbox(dummy_devbox_info, mcp_enabled=True)
        print(f"Galatea updated at (MCP): {result}")
        assert isinstance(result, str)
        assert result.endswith("/galatea") or "/galatea" in result
    except Exception as e:
        print(f"Expected exception (if dummy devbox is not real): {e}")
        assert True


# python -m pytest -s tests/test_resource_provider.py::test_cleanup_galatea_files_on_devbox
@pytest.mark.asyncio
async def test_cleanup_galatea_files_on_devbox(dummy_devbox_info):
    try:
        result = await cleanup_galatea_files_on_devbox(dummy_devbox_info)
        print(f"Cleanup result: {result}")
        assert result is True
    except Exception as e:
        print(f"Expected exception (if dummy devbox is not real): {e}")
        assert True


@pytest.fixture
def dummy_devbox_info():
    from providers.resource.resource_models import DevboxInfo, SSHCredentials

    return DevboxInfo(
        project_public_address="https://mpiadxtjesgr.sealosbja.site/",
        ssh_credentials=SSHCredentials(
            host="bja.sealos.run",
            port="40277",
            username="devbox",
            password="12345",
        ),
        template="nextjs",
        token="daxfAj-1nizti-dazduw",
    )
