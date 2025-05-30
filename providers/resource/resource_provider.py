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
from .resource_models import DevboxInfo, SSHCredentials

load_dotenv()


async def activate_galatea_for_devbox(devbox_info: DevboxInfo) -> str:
    """
    Activate Galatea for a devbox. Cleans ports and launches Galatea if it exists,
    otherwise uploads and launches it.

    Args:
        devbox_info: DevboxInfo containing SSH credentials and connection details

    Returns:
        str: URL in the format {project_public_address}/galatea
    """
    try:
        print(
            f"Starting Galatea activation for devbox at {devbox_info.ssh_credentials.host}"
        )

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
            await conn.run(
                "cd /home/devbox && (./galatea > galatea.log 2>&1 &) && sleep 1",
                check=False,
            )

        galatea_url = f"{devbox_info.project_public_address}/galatea"
        print(f"Galatea activation complete. URL: {galatea_url}")
        return galatea_url

    except Exception as e:
        print(f"Error activating Galatea: {str(e)}")
        raise Exception(f"Failed to activate Galatea for devbox: {str(e)}")


async def update_galatea_for_devbox(devbox_info: DevboxInfo) -> str:
    """
    Update Galatea for a devbox by removing current version and activating with newest release.

    Args:
        devbox_info: DevboxInfo containing SSH credentials and connection details

    Returns:
        str: URL in the format {project_public_address}/galatea
    """
    try:
        print("🔄 Starting Galatea update process...")

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

        print(f"🔌 Connecting to devbox at {ssh_config['host']}:{ssh_config['port']}")
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
            print("🧹 Cleaning up existing Galatea processes and files...")
            # Clean ports and remove existing galatea
            await conn.run("cd /home/devbox && fuser -k 3051/tcp 3000/tcp", check=False)
            await conn.run("cd /home/devbox && rm -f galatea galatea.log", check=False)
            print("✅ Cleanup complete")

        print("🚀 Activating new Galatea version...")
        # Call activate function to fetch newest galatea and launch
        result = await activate_galatea_for_devbox(devbox_info)
        print("✅ Galatea update completed successfully")
        return result

    except Exception as e:
        print(f"❌ Error updating Galatea: {str(e)}")
        raise Exception(f"Failed to update Galatea for devbox: {str(e)}")


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


def get_devbox_for_task(task_path: str, token: str) -> DevboxInfo:
    """Returns the devbox info for a given task.

    This function should create a devbox according to the task content for the user holding the token.

    Args:
        task_path: The path to the task
        token: The token for the task

    Returns:
        DevboxInfo: The devbox info structure
    """
    return DevboxInfo(
        project_public_address=get_available_devbox_address(),
        ssh_credentials=SSHCredentials(
            host=None,
            port=None,
            username=None,
            password=None,
        ),
        template="nextjs",
    )


def get_dummy_devbox_for_task(task_path: str, token: str) -> DevboxInfo:
    print("received token: " + token)
    return DevboxInfo(
        project_public_address=os.getenv("DUMMY_ADDRESS"),
        ssh_credentials=SSHCredentials(
            host=os.getenv("DUMMY_HOST"),
            port=os.getenv("DUMMY_PORT"),
            username=os.getenv("DUMMY_USERNAME"),
            password=os.getenv("DUMMY_PASSWORD"),
        ),
        template="nextjs",
        token=os.getenv("DUMMY_TOKEN"),
    )


def get_available_devbox_address():
    """Returns the IP address of an available devbox instance.

    Returns:
        str: The IP address of the devbox instance (currently hardcoded to 192.168.1.100)
    """
    return "192.168.1.100"


async def add_devbox_info_to_task_plan(
    task_plan_path: str, devbox_info: DevboxInfo
) -> dict:
    """
    Adds devbox information and status to the task plan JSON file.

    Args:
        task_plan_path: Path to the task plan JSON file.
        devbox_info: DevboxInfo object to add.

    Returns:
        The updated task plan as a dictionary.
    """
    task_plan_file = Path(task_plan_path)
    if not task_plan_file.exists():
        raise FileNotFoundError(f"Task plan file not found: {task_plan_path}")

    with open(task_plan_file, "r") as f:
        task_plan_data = json.load(f)

    task_plan_data["devbox_info"] = (
        devbox_info.model_dump()
    )  # Convert Pydantic model to dict
    task_plan_data["task_id"] = str(uuid.uuid4())  # Add a unique ID to the task
    task_plan_data["status"] = "initiated"  # Add status field

    with open(task_plan_file, "w") as f:
        json.dump(task_plan_data, f, indent=2)

    print(f"Devbox info, task ID, and status added to task plan: {task_plan_path}")
    return task_plan_data
