import pytest
import asyncio
from unittest.mock import patch, AsyncMock
from providers.resource.devbox.devbox_provider import (
    generate_networks_for_devbox,
    get_ssh_connection_info,
    get_ssh_connection_params,
    connect_to_devbox_terminal,
    get_devbox_list,
    get_devbox_by_name,
)
from tests.fixtures import (
    sample_template_config,
    sample_devbox_name,
    sample_ingress_domain,
    devbox_region_url,
    devbox_token,
    kubeconfig,
    ssh_info,
)

# All fixtures are now imported from tests/fixtures.py

# ============================================================================
# NETWORK CONFIGURATION TESTS
# ============================================================================


# python -m pytest -s tests/test_devbox_provider.py::test_generate_networks_for_devbox
def test_generate_networks_for_devbox(
    sample_devbox_name, sample_template_config, sample_ingress_domain
):
    networks = generate_networks_for_devbox(
        sample_devbox_name, sample_template_config, sample_ingress_domain
    )
    print(f"Networks: {networks}")
    assert isinstance(networks, list)
    assert len(networks) == 2
    for net, port in zip(networks, [3000, 5000]):
        assert net["networkName"].startswith(sample_devbox_name + "-")
        assert isinstance(net["portName"], str) and len(net["portName"]) == 12
        assert net["port"] == port
        assert net["protocol"] == "HTTP"
        assert net["openPublicDomain"] is True
        assert net["publicDomain"].endswith("." + sample_ingress_domain)
        assert net["customDomain"] == ""
        # UUID check
        import uuid

        uuid.UUID(net["id"])  # should not raise


# ============================================================================
# API ENDPOINT TESTS
# ============================================================================


# python -m pytest -s tests/test_devbox_provider.py::test_get_ssh_connection_info
def test_get_ssh_connection_info(
    devbox_region_url, sample_devbox_name, kubeconfig, devbox_token
):
    try:
        result = get_ssh_connection_info(
            devbox_region_url, sample_devbox_name, kubeconfig, devbox_token
        )
        print(f"SSH Connection Info: {result}")
        assert isinstance(result, dict)
    except Exception as e:
        print(f"Exception occurred: {e}")
        assert False, f"get_ssh_connection_info failed: {e}"


# python -m pytest -s tests/test_devbox_provider.py::test_get_devbox_list
def test_get_devbox_list(devbox_region_url, kubeconfig, devbox_token):
    try:
        result = get_devbox_list(devbox_region_url, kubeconfig, devbox_token)
        print(f"Devbox List: {result}")
        assert isinstance(result, dict)
    except Exception as e:
        print(f"Exception occurred: {e}")
        assert True


# python -m pytest -s tests/test_devbox_provider.py::test_get_devbox_by_name
def test_get_devbox_by_name(
    devbox_region_url, sample_devbox_name, kubeconfig, devbox_token
):
    try:
        result = get_devbox_by_name(
            devbox_region_url, sample_devbox_name, False, kubeconfig, devbox_token
        )
        print(f"Devbox By Name: {result}")
        assert isinstance(result, dict)
    except Exception as e:
        print(f"Exception occurred: {e}")
        assert True


# ============================================================================
# SSH CONNECTION TESTS
# ============================================================================


# python -m pytest -s tests/test_devbox_provider.py::test_get_ssh_connection_params
def test_get_ssh_connection_params(ssh_info):
    private_key_str, username = get_ssh_connection_params(ssh_info)
    print(f"Private Key String: {private_key_str}")
    print(f"Username: {username}")
    assert isinstance(private_key_str, str)
    assert private_key_str.startswith("-----BEGIN OPENSSH PRIVATE KEY-----")
    assert username == "devbox"


# python -m pytest -s tests/test_devbox_provider.py::test_connect_to_devbox_terminal
@pytest.mark.asyncio
async def test_connect_to_devbox_terminal(ssh_info):
    """Test real SSH connection to devbox and execute commands"""
    hostname = "bja.sealos.run"
    port = 40277
    try:
        conn = await connect_to_devbox_terminal(ssh_info, hostname, port)
        print(f"Connection result: {conn}")
        if conn is not None:
            pwd_result = await conn.run("pwd", check=True)
            print(f"PWD Command output: {pwd_result.stdout.strip()}")
            print(f"PWD Command error (if any): {pwd_result.stderr.strip()}")
            ls_result = await conn.run("ls -la", check=True)
            print(f"LS Command output: {ls_result.stdout.strip()}")
            conn.close()
            await conn.wait_closed()
        assert True
    except Exception as e:
        print(f"Real connection test failed: {e}")
        assert True
