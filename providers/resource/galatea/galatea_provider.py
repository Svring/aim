import os
import json
import uuid
import asyncio
from dotenv import load_dotenv
import tempfile
from pathlib import Path
import aiohttp
import asyncssh
from typing import Optional, Dict, Any
from providers.resource.resource_models import DevboxInfo, SSHCredentials
import yaml
import urllib.parse

load_dotenv()


async def activate_galatea_for_devbox(
    devbox_info: DevboxInfo, mcp_enabled: bool = False, update: bool = False
) -> str:
    """
    Activate (or update) Galatea for a devbox. If update=True, cleans up existing Galatea files before activation.
    Cleans ports and launches Galatea if it exists, otherwise uploads and launches it.

    Args:
        devbox_info: DevboxInfo containing SSH credentials and connection details
        mcp_enabled: If True, launch Galatea with '--mcp_enabled' flag
        update: If True, cleanup existing Galatea files before activation

    Returns:
        str: URL in the format {project_public_address}galatea
    """
    try:
        print(
            f"Starting Galatea activation for devbox at {devbox_info.ssh_credentials.host}"
        )

        if update:
            print("Update flag is set. Cleaning up existing Galatea files...")
            await cleanup_galatea_files_on_devbox(devbox_info)
            print("Cleanup complete. Proceeding with activation...")

        # Extract SSH configuration from DevboxInfo
        ssh_config = {
            "host": devbox_info.ssh_credentials.host,
            "port": (
                int(devbox_info.ssh_credentials.port)
                if devbox_info.ssh_credentials.port
                else 22
            ),
            "username": devbox_info.ssh_credentials.username,
            "password": devbox_info.ssh_credentials.password,
        }

        print(
            f"Connecting to devbox via SSH at {ssh_config['host']}:{ssh_config['port']}"
        )
        async with asyncssh.connect(
            host=ssh_config["host"],
            port=ssh_config.get("port", 22),
            username=ssh_config["username"],
            password=ssh_config.get("password"),
            client_keys=(
                [ssh_config["private_key"]] if ssh_config.get("private_key") else None
            ),
            known_hosts=None,
        ) as conn:
            print("SSH connection established, cleaning ports...")
            # Clean ports first
            await conn.run("cd /home/devbox && fuser -k 3051/tcp 3000/tcp", check=False)

            print("Checking if Galatea binary exists...")
            # Check if galatea exists
            check_result = await conn.run(
                "cd /home/devbox && test -f galatea", check=False
            )

            if check_result.exit_status != 0:
                print("Galatea binary not found, uploading...")
                # Galatea does not exist, upload it
                await _upload_galatea_binary(ssh_config)
            else:
                print("Galatea binary found")

            print("Making Galatea executable and launching...")
            # Make executable and launch
            await conn.run("cd /home/devbox && chmod a+x galatea")
            # Launch Galatea in background with proper detachment
            launch_cmd = (
                "cd /home/devbox && (./galatea --mcp-enabled --use-sudo > galatea.log 2>&1 &) && sleep 1"
                if mcp_enabled
                else "cd /home/devbox && (./galatea > galatea.log 2>&1 &) && sleep 1"
            )
            await conn.run(
                launch_cmd,
                check=False,
            )

        galatea_url = f"{devbox_info.project_public_address}galatea"
        print(f"Galatea activation complete. URL: {galatea_url}")
        return galatea_url

    except Exception as e:
        print(f"Error activating Galatea: {str(e)}")
        raise Exception(f"Failed to activate Galatea for devbox: {str(e)}")


async def _upload_galatea_binary(ssh_config: Dict[str, Any]) -> None:
    """
    Helper function to upload Galatea binary to the devbox.

    Args:
        ssh_config: SSH connection configuration
    """
    galatea_release = os.getenv("GALATEA_RELEASE")
    if not galatea_release:
        raise Exception("GALATEA_RELEASE environment variable is not set")

    # Create temporary file
    with tempfile.NamedTemporaryFile(delete=False) as tmp_file:
        tmp_path = tmp_file.name

    try:
        # Download the file locally first
        async with aiohttp.ClientSession() as session:
            async with session.get(galatea_release) as response:
                if not response.ok:
                    raise Exception("Failed to download galatea")

                content = await response.read()
                with open(tmp_path, "wb") as f:
                    f.write(content)

        # Upload to remote using asyncssh
        async with asyncssh.connect(
            host=ssh_config["host"],
            port=ssh_config.get("port", 22),
            username=ssh_config["username"],
            password=ssh_config.get("password"),
            client_keys=(
                [ssh_config["private_key"]] if ssh_config.get("private_key") else None
            ),
            known_hosts=None,
        ) as conn:
            # Upload file
            await asyncssh.scp(tmp_path, (conn, "/home/devbox/galatea"))

    except Exception as e:
        raise Exception(f"Failed to upload Galatea binary: {str(e)}")
    finally:
        # Clean up temporary file
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)


async def cleanup_galatea_files_on_devbox(devbox_info: DevboxInfo) -> bool:
    """
    Cleans up Galatea-related files and folders on the remote devbox.
    Deletes 'galatea_files', 'project' folders and 'galatea', 'galatea_log' files from /home/{user}.

    Args:
        devbox_info: DevboxInfo containing SSH credentials and connection details

    Returns:
        bool: True if cleanup succeeds
    """
    try:
        ssh_user = devbox_info.ssh_credentials.username
        if not ssh_user:
            raise Exception("SSH username is required for cleanup.")
        ssh_config = {
            "host": devbox_info.ssh_credentials.host,
            "port": (
                int(devbox_info.ssh_credentials.port)
                if devbox_info.ssh_credentials.port
                else 22
            ),
            "username": ssh_user,
            "password": devbox_info.ssh_credentials.password,
        }
        cleanup_cmd = (
            f"cd /home/{ssh_user} && "
            "sudo rm -rf galatea_files project galatea galatea.log"
        )
        print(
            f"Connecting to devbox for cleanup at {ssh_config['host']}:{ssh_config['port']}"
        )
        async with asyncssh.connect(
            host=ssh_config["host"],
            port=ssh_config.get("port", 22),
            username=ssh_config["username"],
            password=ssh_config.get("password"),
            client_keys=(
                [ssh_config["private_key"]] if ssh_config.get("private_key") else None
            ),
            known_hosts=None,
        ) as conn:
            print(f"Running cleanup command: {cleanup_cmd}")
            result = await conn.run(cleanup_cmd, check=False)
            if result.exit_status != 0:
                raise Exception(f"Cleanup command failed: {result.stderr}")
        print("Cleanup completed successfully.")
        return True
    except Exception as e:
        print(f"Error during cleanup: {str(e)}")
        raise Exception(f"Failed to cleanup Galatea files on devbox: {str(e)}")
