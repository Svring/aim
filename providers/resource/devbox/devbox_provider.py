import os
import json
import random
import uuid
import asyncio
import asyncssh
import base64
from typing import Optional, Dict
import requests


def generate_networks_for_devbox(
    devbox_name: str, template_config: str, ingress_domain: Optional[str] = None
) -> list:
    """
    Generate network configuration for a devbox, replicating frontend logic.

    Args:
        devbox_name (str): Name of the devbox.
        template_config (str): JSON string of the template config.
        ingress_domain (str, optional): Ingress domain to use. Defaults to env INGRESS_DOMAIN or 'sealosusw.site'.

    Returns:
        list: List of network configuration dicts.
    """

    def nanoid(length=12):
        alphabet = "abcdefghijklmnopqrstuvwxyz"
        return "".join(random.choices(alphabet, k=length))

    if ingress_domain is None:
        ingress_domain = os.getenv("INGRESS_DOMAIN", "sealosusw.site")

    try:
        config = json.loads(template_config)
        app_ports = config.get("appPorts", [])
    except Exception as e:
        raise ValueError(f"Invalid template_config JSON: {e}")

    networks = []
    for port_config in app_ports:
        port = port_config.get("port")
        if port is None:
            continue
        network = {
            "networkName": f"{devbox_name}-{nanoid()}",
            "portName": nanoid(),
            "port": port,
            "protocol": "HTTP",
            "openPublicDomain": True,
            "publicDomain": f"{nanoid()}.{ingress_domain}",
            "customDomain": "",
            "id": str(uuid.uuid4()),
        }
        networks.append(network)
    return networks


def get_ssh_connection_info(
    region_url: str, devbox_name: str, kubeconfig: str, devbox_token: str
) -> Dict:
    """
    Fetch SSH connection info for a given devbox.

    Args:
        region_url (str): The region's base URL (without protocol).
        devbox_name (str): The name of the devbox.
        kubeconfig (str): Kubeconfig token string.
        devbox_token (str): Devbox token string.

    Returns:
        dict: SSH connection info data as returned by the API (the 'data' field).
    """
    url = f"https://{region_url}/api/getSSHConnectionInfo?devboxName={devbox_name}"
    headers = {
        "Authorization": kubeconfig,
        "Authorization-Bearer": devbox_token,
        "Content-Type": "application/json",
    }
    response = requests.get(url, headers=headers)
    response.raise_for_status()
    result = response.json()
    # Return only the 'data' field if present, else the whole result
    return result.get("data", result)


def get_devbox_list(region_url: str, kubeconfig: str, devbox_token: str) -> dict:
    """
    Fetch the list of devboxes for the given region.

    Args:
        region_url (str): The region's base URL (without protocol).
        kubeconfig (str): Kubeconfig token string (parsed).
        devbox_token (str): Devbox token string.

    Returns:
        dict: Devbox list data as returned by the API (the 'data' field).
    """
    url = f"https://{region_url}/api/getDevboxList"
    headers = {
        "Authorization": kubeconfig,
        "Authorization-Bearer": devbox_token,
        "Content-Type": "application/json",
    }
    response = requests.get(url, headers=headers)
    response.raise_for_status()
    result = response.json()
    return result.get("data", result)


def get_devbox_by_name(
    region_url: str, devbox_name: str, mock: bool, kubeconfig: str, devbox_token: str
) -> dict:
    """
    Fetch a devbox by name for the given region.

    Args:
        region_url (str): The region's base URL (without protocol).
        devbox_name (str): The name of the devbox to fetch.
        mock (bool): Whether to use mock mode (passed as 'true' or 'false' in the query).
        kubeconfig (str): Kubeconfig token string (parsed).
        devbox_token (str): Devbox token string.

    Returns:
        dict: Devbox data as returned by the API (the 'data' field).
    """
    url = f"https://{region_url}/api/getDevboxByName?devboxName={devbox_name}&mock={str(mock).lower()}"
    headers = {
        "Authorization": kubeconfig,
        "Authorization-Bearer": devbox_token,
        "Content-Type": "application/json",
    }
    response = requests.get(url, headers=headers)
    response.raise_for_status()
    result = response.json()
    return result.get("data", result)


def get_ssh_connection_params(ssh_info: dict):
    """
    Extract SSH connection parameters from the info dict returned by fetch_ssh_connection_info.
    """
    private_key_str = base64.b64decode(ssh_info["base64PrivateKey"]).decode("utf-8")
    username = ssh_info["userName"]
    return private_key_str, username


async def connect_to_devbox_terminal(ssh_info: dict, hostname: str, port: int = 22):
    """
    Connect to the devbox terminal using asyncssh and the SSH info dict.

    Args:
        ssh_info (dict): The SSH connection info as returned by fetch_ssh_connection_info.
        hostname (str): The SSH server hostname.
        port (int): The SSH server port (default 22).

    Returns:
        asyncssh.SSHClientConnection: The SSH connection object.
    """
    private_key_str, username = get_ssh_connection_params(ssh_info)
    try:
        private_key = asyncssh.import_private_key(private_key_str)
        conn = await asyncssh.connect(
            host=hostname,
            port=port,
            username=username,
            client_keys=[private_key],
            known_hosts=None,  # Disable host key checking (use cautiously)
        )
        print(f"Successfully connected to {username}@{hostname}:{port}")
        # Optionally, run a test command here if you want
        return conn
    except asyncssh.DisconnectError as e:
        print(f"SSH error: {e}")
    except asyncssh.PermissionDenied as e:
        print(f"Authentication failed: {e}")
    except Exception as e:
        print(f"Connection error: {e}")
    return None
