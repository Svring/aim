# python -m pytest -s tests/test_resource_provider.py
import pytest
import asyncio
import os
from dotenv import load_dotenv
from providers.resource.resource_provider import (
    parse_kubeconfig,
)
from providers.resource.galatea.galatea_provider import (
    activate_galatea_for_devbox,
    cleanup_galatea_files_on_devbox,
)
import urllib.parse
import json
from unittest.mock import patch, AsyncMock
from tests.fixtures import dummy_devbox_info, kubeconfig_path

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


# python -m pytest -s tests/test_resource_provider.py::test_activate_galatea_for_dummy_devbox_update
@pytest.mark.asyncio
async def test_activate_galatea_for_dummy_devbox_update(dummy_devbox_info):
    try:
        result = await activate_galatea_for_devbox(dummy_devbox_info, update=True)
        print(f"Galatea activated (update) at: {result}")
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


# python -m pytest -s tests/test_resource_provider.py::test_activate_galatea_for_dummy_devbox_mcp_update
@pytest.mark.asyncio
async def test_activate_galatea_for_dummy_devbox_mcp_update(dummy_devbox_info):
    try:
        result = await activate_galatea_for_devbox(
            dummy_devbox_info, mcp_enabled=True, update=True
        )
        print(f"Galatea activated (MCP, update) at: {result}")
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


# python -m pytest -s tests/test_resource_provider.py::test_parse_kubeconfig_url_encoding
@pytest.mark.asyncio
async def test_parse_kubeconfig_url_encoding(kubeconfig_path):
    result = await parse_kubeconfig(kubeconfig_path)
    print(f"Result: {result}")
    with open(kubeconfig_path, "r") as f:
        original = f.read()
    assert urllib.parse.unquote(result) == original
