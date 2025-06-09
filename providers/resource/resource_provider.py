import os
import json
import uuid
from dotenv import load_dotenv
from pathlib import Path
from .resource_models import DevboxInfo, SSHCredentials
import urllib.parse

load_dotenv()


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
        token="123",
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


async def parse_kubeconfig(kubeconfig_path: str) -> str:
    """
    Reads a kubeconfig YAML file and returns its contents as a URL-encoded string.

    Args:
        kubeconfig_path: Path to the kubeconfig YAML file.
    Returns:
        str: URL-encoded string of the kubeconfig file contents.
    """
    kubeconfig_file = Path(kubeconfig_path)
    if not kubeconfig_file.exists():
        raise FileNotFoundError(f"Kubeconfig file not found: {kubeconfig_path}")
    with open(kubeconfig_file, "r") as f:
        kubeconfig_str = f.read()
    return urllib.parse.quote(kubeconfig_str)
