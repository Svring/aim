from langchain_core.tools import tool
from pydantic import BaseModel, Field
import os
import re
from typing import Literal, List


# Define a Pydantic model for structured follow-up questions
class FollowUpQuestion(BaseModel):
    question: str = Field(description="The follow-up question to clarify user intent")
    context: str = Field(
        description="Context or reason for asking the follow-up question"
    )


@tool
def ask_follow_up_question(params: FollowUpQuestion) -> str:
    """
    Ask a follow-up question to gather more details about the user's coding task requirements.

    Args:
        params: A FollowUpQuestion object containing the question and its context.

    Returns:
        A string containing the follow-up question to be presented to the user.
    """
    question = params.question
    user_input = input(f"AI asks: {question}\nYour answer: ")
    return f"User answered: {user_input}"


# Define a Pydantic model for the task plan
class SSHCredentials(BaseModel):
    host: str = Field(description="SSH host address")
    port: str = Field(description="SSH port number")
    username: str = Field(description="SSH username")
    password: str = Field(description="SSH password")


class DevboxInfo(BaseModel):
    user_id: str = Field(description="User identifier for the devbox")
    project_public_address: str = Field(description="Public URL of the project")
    ssh_credentials: SSHCredentials = Field(
        description="SSH credentials for accessing the devbox"
    )
    template: Literal["nextjs", "uv"] = Field(
        description="Template used for the devbox"
    )


class Functionality(BaseModel):
    description: str = Field(description="Description of the functionality")
    workflow: str = Field(
        description="Details on how to use the functionality in the UI and expected result"
    )
    completed: bool = Field(
        description="Indicates whether the functionality is completed", default=False
    )


class TaskPlan(BaseModel):
    task_id: str = Field(description="Unique identifier for the task")
    task_name: str = Field(description="The name of the task")
    user_prompt: str = Field(description="The original user prompt")
    template: Literal["nextjs", "uv"] = Field(
        description="Template to be used: 'nextjs' or 'uv'"
    )
    design_principles: List[str] = Field(description="Design principles to follow")
    functionalities: List[Functionality] = Field(
        description="Expected functionalities of the task"
    )
    additional_notes: str = Field(
        description="Any additional notes or considerations", default=""
    )
    devbox_info: DevboxInfo = Field(description="Development environment information")


@tool
def generate_task_plan(plan: TaskPlan) -> dict:
    """
    Generate and save a detailed task plan as a JSON file based on the user's requirements.

    Args:
        plan: A TaskPlan object containing the details of the task plan.

    Returns:
        A dict containing status, task_name, and file_path (or error message).
    """
    # Convert the plan to JSON
    plan_json = plan.model_dump_json(indent=2)

    # Convert task_name to snake_case for the filename
    def to_snake_case(name):
        name = name.strip().lower()
        name = re.sub(r"[^a-z0-9]+", "_", name)
        name = re.sub(r"_+", "_", name)
        return name.strip("_")

    base_dir = "task_plans"
    base_name = to_snake_case(plan.task_name)
    file_path = os.path.join(base_dir, f"{base_name}.json")
    # Collision avoidance
    if not os.path.exists(base_dir):
        os.makedirs(base_dir, exist_ok=True)
    suffix = 1
    while os.path.exists(file_path):
        file_path = os.path.join(base_dir, f"{base_name}_{suffix}.json")
        suffix += 1
    try:
        with open(file_path, "w") as f:
            f.write(plan_json)
        return {
            "status": "success",
            "task_name": plan.task_name,
            "file_path": file_path,
        }
    except Exception as e:
        return {"status": "error", "task_name": plan.task_name, "error": str(e)}


class CompleteFunctionalityParams(BaseModel):
    plan: TaskPlan = Field(description="The task plan to update")
    description: str = Field(
        description="The description of the functionality to mark as completed"
    )


@tool
def complete_functionality(params: CompleteFunctionalityParams) -> TaskPlan:
    """
    Mark a functionality as completed in the given TaskPlan by matching its description.
    Returns the updated TaskPlan.
    """
    updated = False
    for func in params.plan.functionalities:
        if func.description == params.description:
            func.completed = True
            updated = True
    if not updated:
        raise ValueError(
            f"No functionality found with description: {params.description}"
        )
    return params.plan
