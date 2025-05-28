# python -m workflows.manus_workflow.basic_manus_workflow

import asyncio
import json

from agents.enquiry_agent.basic_enquiry_agent import run_basic_enquiry_agent
from agents.codebase_agent.full_code_agent import run_full_code_agent
from providers.resource.resource_provider import (
    get_dummy_devbox_for_task,
    add_devbox_info_to_task_plan,
)


async def run_manus_workflow(initial_prompt: str, token: str = None):
    """
    Runs the complete Manus workflow:
    1. Generates a task plan using the enquiry agent.
    2. Allocates devbox resources and adds them to the task plan.
    3. Runs the full code agent to implement the task autonomously.

    Args:
        initial_prompt: The user's initial request
        token: Authentication token for API requests (optional, will use dummy if not provided)

    Returns:
        Dict containing the final result of the workflow
    """
    print("🚀 Starting Manus Workflow...")
    print(f"📝 Received initial prompt: {initial_prompt}")

    # Part 1: Enquiry Agent - Generate Task Plan
    print("\n--- Step 1: Running Enquiry Agent ---")
    task_plan_path = await run_basic_enquiry_agent(initial_prompt)

    if not task_plan_path:
        print("❌ Enquiry agent failed to generate a task plan. Exiting workflow.")
        return {
            "status": "failed",
            "step": "enquiry_agent",
            "message": "Failed to generate task plan",
        }

    print(f"✅ Task plan generated at: {task_plan_path}")

    # Part 2: Resource Allocation
    print("\n--- Step 2: Allocating Devbox Resources ---")
    # Use provided token or fallback to dummy
    auth_token = token or "dummy_token_123"
    devbox_info = get_dummy_devbox_for_task(task_path=task_plan_path, token=auth_token)

    print(f"✅ Retrieved devbox info: {devbox_info}")

    # Add devbox info to the task plan
    updated_task_plan = await add_devbox_info_to_task_plan(task_plan_path, devbox_info)

    if not updated_task_plan:
        print("❌ Failed to update task plan with devbox info.")
        return {
            "status": "failed",
            "step": "resource_allocation",
            "message": "Failed to update task plan with devbox info",
        }

    print(f"✅ Task plan updated with devbox info")

    # Part 3: Full Code Agent Implementation
    print("\n--- Step 3: Running Full Code Agent ---")
    galatea_url = devbox_info.get("galatea_url", "http://localhost:3000")

    try:
        implementation_result = await run_full_code_agent(
            galatea_url=galatea_url, token=auth_token, task_plan=updated_task_plan
        )

        print(
            f"🎉 Full Code Agent completed with status: {implementation_result.get('status')}"
        )

        # Combine all results
        final_result = {
            "status": "completed",
            "workflow_steps": {
                "enquiry_agent": {
                    "status": "completed",
                    "task_plan_path": task_plan_path,
                },
                "resource_allocation": {
                    "status": "completed",
                    "devbox_info": devbox_info,
                },
                "code_implementation": implementation_result,
            },
            "task_plan": updated_task_plan,
            "galatea_url": galatea_url,
            "final_message": implementation_result.get("message", "Workflow completed"),
        }

        print("\n🎉 Manus Workflow completed successfully!")
        return final_result

    except Exception as e:
        print(f"❌ Error during code implementation: {str(e)}")
        return {
            "status": "failed",
            "step": "code_implementation",
            "message": f"Code implementation failed: {str(e)}",
            "task_plan": updated_task_plan,
            "galatea_url": galatea_url,
        }


async def run_manus_workflow_with_existing_devbox(
    initial_prompt: str, galatea_url: str, token: str
):
    """
    Runs the Manus workflow with an existing devbox (skips resource allocation).

    Args:
        initial_prompt: The user's initial request
        galatea_url: The URL of the existing Galatea devbox
        token: Authentication token for API requests

    Returns:
        Dict containing the final result of the workflow
    """
    print("🚀 Starting Manus Workflow with existing devbox...")
    print(f"📝 Received initial prompt: {initial_prompt}")
    print(f"🔗 Using existing Galatea URL: {galatea_url}")

    # Part 1: Enquiry Agent - Generate Task Plan
    print("\n--- Step 1: Running Enquiry Agent ---")
    task_plan_path = await run_basic_enquiry_agent(initial_prompt)

    if not task_plan_path:
        print("❌ Enquiry agent failed to generate a task plan. Exiting workflow.")
        return {
            "status": "failed",
            "step": "enquiry_agent",
            "message": "Failed to generate task plan",
        }

    print(f"✅ Task plan generated at: {task_plan_path}")

    # Load the task plan
    try:
        with open(task_plan_path, "r") as f:
            task_plan = json.load(f)
    except Exception as e:
        print(f"❌ Failed to load task plan: {str(e)}")
        return {
            "status": "failed",
            "step": "task_plan_loading",
            "message": f"Failed to load task plan: {str(e)}",
        }

    # Part 2: Full Code Agent Implementation
    print("\n--- Step 2: Running Full Code Agent ---")

    try:
        implementation_result = await run_full_code_agent(
            galatea_url=galatea_url, token=token, task_plan=task_plan
        )

        print(
            f"🎉 Full Code Agent completed with status: {implementation_result.get('status')}"
        )

        # Combine all results
        final_result = {
            "status": "completed",
            "workflow_steps": {
                "enquiry_agent": {
                    "status": "completed",
                    "task_plan_path": task_plan_path,
                },
                "code_implementation": implementation_result,
            },
            "task_plan": task_plan,
            "galatea_url": galatea_url,
            "final_message": implementation_result.get("message", "Workflow completed"),
        }

        print("\n🎉 Manus Workflow completed successfully!")
        return final_result

    except Exception as e:
        print(f"❌ Error during code implementation: {str(e)}")
        return {
            "status": "failed",
            "step": "code_implementation",
            "message": f"Code implementation failed: {str(e)}",
            "task_plan": task_plan,
            "galatea_url": galatea_url,
        }
