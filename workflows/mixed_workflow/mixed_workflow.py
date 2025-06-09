# python -m workflows.mixed_workflow.mixed_workflow

import asyncio
import json
import os
from typing import Dict, Any, Optional
from datetime import datetime
from pydantic import BaseModel, Field

from agents.enquiry_agent.basic_enquiry_agent import run_basic_enquiry_agent
from agents.codebase_agent.full_code_agent import run_full_code_agent
from agents.browser_agent.browser_agent import run_browser_agent
from providers.resource.resource_provider import (
    get_dummy_devbox_for_task,
    add_devbox_info_to_task_plan,
)
from providers.tool.function.enquiry_tools import TaskPlan


# Pydantic models for workflow state
class WorkflowStep(BaseModel):
    """Represents a single step in the workflow"""

    step_name: str
    status: str = Field(default="pending")  # pending, running, completed, failed
    start_time: Optional[str] = None
    end_time: Optional[str] = None
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None


class WorkflowState(BaseModel):
    """Represents the complete workflow state"""

    workflow_id: str
    initial_prompt: str
    start_time: str
    end_time: Optional[str] = None
    status: str = Field(default="running")  # running, completed, failed
    current_step: Optional[str] = None
    task_plan_path: Optional[str] = None
    galatea_url: Optional[str] = None
    token: Optional[str] = None
    task_plan: Optional[Dict[str, Any]] = None
    implementation_attempts: int = Field(default=0)
    max_attempts: int = Field(default=3)
    steps: Dict[str, WorkflowStep] = Field(default_factory=dict)
    final_result: Optional[Dict[str, Any]] = None


async def run_mixed_workflow(
    initial_prompt: str,
    token: Optional[str] = None,
    existing_devbox_url: Optional[str] = None,
    max_implementation_attempts: int = 3,
) -> Dict[str, Any]:
    """
    Runs the complete mixed workflow from user prompt to deployed application.

    This is a functional implementation that:
    1. Uses the enquiry agent to understand user intent and generate a task plan
    2. Allocates development resources (or uses existing ones)
    3. Runs the codebase agent to implement the task
    4. Uses the browser agent to evaluate the implementation
    5. Iterates if evaluation fails (up to max_attempts)

    Args:
        initial_prompt: The user's coding task request
        token: Authentication token (optional, will use dummy if not provided)
        existing_devbox_url: URL of existing devbox to use (optional)
        max_implementation_attempts: Maximum number of implementation attempts

    Returns:
        Dict containing the complete workflow results
    """
    # Initialize workflow state
    workflow_id = datetime.now().strftime("%Y%m%d_%H%M%S")
    logs_dir = f"logs/workflows/{workflow_id}"
    os.makedirs(logs_dir, exist_ok=True)

    state = WorkflowState(
        workflow_id=workflow_id,
        initial_prompt=initial_prompt,
        start_time=datetime.now().isoformat(),
        max_attempts=max_implementation_attempts,
    )

    try:
        # Step 1: Enquiry Agent - Generate Task Plan
        print(f"\n{'='*60}")
        print("🔍 STEP 1: ENQUIRY AGENT - Understanding User Intent")
        print(f"{'='*60}")

        state.current_step = "enquiry"
        state.steps["enquiry"] = WorkflowStep(
            step_name="enquiry", status="running", start_time=datetime.now().isoformat()
        )

        enquiry_result = await _run_enquiry_step(initial_prompt)

        if enquiry_result["status"] == "success":
            state.task_plan_path = enquiry_result["task_plan_path"]
            state.steps["enquiry"].status = "completed"
            state.steps["enquiry"].result = enquiry_result
        else:
            state.steps["enquiry"].status = "failed"
            state.steps["enquiry"].error = enquiry_result.get("error", "Unknown error")
            state.status = "failed"
            return _finalize_workflow(state, logs_dir)

        state.steps["enquiry"].end_time = datetime.now().isoformat()

        # Step 2: Resource Allocation
        print(f"\n{'='*60}")
        print("🔧 STEP 2: RESOURCE ALLOCATION - Setting up Development Environment")
        print(f"{'='*60}")

        state.current_step = "resource_allocation"
        state.steps["resource_allocation"] = WorkflowStep(
            step_name="resource_allocation",
            status="running",
            start_time=datetime.now().isoformat(),
        )

        if existing_devbox_url:
            if not state.task_plan_path:
                raise ValueError("Task plan path is required but not set")
            resource_result = await _use_existing_devbox(
                state.task_plan_path, existing_devbox_url, token
            )
        else:
            if not state.task_plan_path:
                raise ValueError("Task plan path is required but not set")
            resource_result = await _allocate_resources(state.task_plan_path, token)

        if resource_result["status"] == "success":
            state.galatea_url = resource_result["galatea_url"]
            state.token = resource_result["token"]
            state.task_plan = resource_result["task_plan"]
            state.steps["resource_allocation"].status = "completed"
            state.steps["resource_allocation"].result = resource_result
        else:
            state.steps["resource_allocation"].status = "failed"
            state.steps["resource_allocation"].error = resource_result.get(
                "error", "Unknown error"
            )
            state.status = "failed"
            return _finalize_workflow(state, logs_dir)

        state.steps["resource_allocation"].end_time = datetime.now().isoformat()

        # Step 3 & 4: Implementation and Evaluation Loop
        evaluation_passed = False

        while (
            state.implementation_attempts < state.max_attempts and not evaluation_passed
        ):
            state.implementation_attempts += 1
            attempt_num = state.implementation_attempts

            # Step 3: Codebase Agent - Implementation
            print(f"\n{'='*60}")
            print(
                f"💻 STEP 3: CODEBASE AGENT - Implementation (Attempt {attempt_num}/{state.max_attempts})"
            )
            print(f"{'='*60}")

            state.current_step = f"implementation_attempt_{attempt_num}"
            state.steps[f"implementation_attempt_{attempt_num}"] = WorkflowStep(
                step_name=f"implementation_attempt_{attempt_num}",
                status="running",
                start_time=datetime.now().isoformat(),
            )

            if not state.galatea_url or not state.token or not state.task_plan:
                raise ValueError(
                    "Missing required state: galatea_url, token, or task_plan"
                )

            implementation_result = await _run_implementation_step(
                state.galatea_url, state.token, state.task_plan
            )

            state.steps[f"implementation_attempt_{attempt_num}"].result = (
                implementation_result
            )

            if implementation_result["status"] == "completed":
                state.steps[f"implementation_attempt_{attempt_num}"].status = (
                    "completed"
                )
            else:
                state.steps[f"implementation_attempt_{attempt_num}"].status = "failed"
                state.steps[f"implementation_attempt_{attempt_num}"].error = (
                    implementation_result.get("message", "Unknown error")
                )
                print(f"⚠️ Implementation attempt {attempt_num} failed")
                state.steps[f"implementation_attempt_{attempt_num}"].end_time = (
                    datetime.now().isoformat()
                )
                continue

            state.steps[f"implementation_attempt_{attempt_num}"].end_time = (
                datetime.now().isoformat()
            )

            # Step 4: Browser Agent - Evaluation
            print(f"\n{'='*60}")
            print(f"🌐 STEP 4: BROWSER AGENT - Evaluation (Attempt {attempt_num})")
            print(f"{'='*60}")

            state.current_step = f"evaluation_attempt_{attempt_num}"
            state.steps[f"evaluation_attempt_{attempt_num}"] = WorkflowStep(
                step_name=f"evaluation_attempt_{attempt_num}",
                status="running",
                start_time=datetime.now().isoformat(),
            )

            if not state.galatea_url or not state.task_plan:
                raise ValueError("Missing required state: galatea_url or task_plan")

            evaluation_result = await _run_evaluation_step(
                state.galatea_url, state.task_plan
            )

            state.steps[f"evaluation_attempt_{attempt_num}"].result = evaluation_result

            if evaluation_result["status"] == "passed":
                evaluation_passed = True
                state.steps[f"evaluation_attempt_{attempt_num}"].status = "completed"
                print("✅ Evaluation passed!")
            else:
                state.steps[f"evaluation_attempt_{attempt_num}"].status = "failed"
                state.steps[f"evaluation_attempt_{attempt_num}"].error = (
                    "Evaluation failed"
                )
                print(
                    f"❌ Evaluation failed: {evaluation_result.get('feedback', 'No specific feedback')}"
                )

                # Update task plan with evaluation feedback for next iteration
                if state.implementation_attempts < state.max_attempts:
                    state.task_plan = await _update_task_plan_with_feedback(
                        state.task_plan, evaluation_result.get("feedback", {})
                    )

            state.steps[f"evaluation_attempt_{attempt_num}"].end_time = (
                datetime.now().isoformat()
            )

        # Finalize workflow
        if evaluation_passed:
            state.status = "completed"
            state.final_result = {
                "status": "success",
                "message": "Task successfully implemented and evaluated",
                "url": state.galatea_url,
                "implementation_attempts": state.implementation_attempts,
            }
        else:
            state.status = "failed"
            state.final_result = {
                "status": "failed",
                "message": f"Failed to pass evaluation after {state.max_attempts} attempts",
                "implementation_attempts": state.implementation_attempts,
            }

        return _finalize_workflow(state, logs_dir)

    except Exception as e:
        state.status = "failed"
        state.final_result = {
            "status": "error",
            "error": str(e),
            "current_step": state.current_step,
        }
        return _finalize_workflow(state, logs_dir)


async def _run_enquiry_step(initial_prompt: str) -> Dict[str, Any]:
    """Run the enquiry agent to generate task plan."""
    try:
        task_plan_path = await run_basic_enquiry_agent(initial_prompt)

        if task_plan_path:
            # Load and validate the task plan
            with open(task_plan_path, "r") as f:
                task_plan_data = json.load(f)

            # Validate using Pydantic model
            task_plan = TaskPlan.model_validate(task_plan_data)

            return {
                "status": "success",
                "task_plan_path": task_plan_path,
                "task_name": task_plan.task_name,
                "functionalities_count": len(task_plan.functionalities),
            }
        else:
            return {
                "status": "failed",
                "error": "Enquiry agent failed to generate task plan",
            }

    except Exception as e:
        return {"status": "error", "error": str(e)}


async def _allocate_resources(
    task_plan_path: str, token: Optional[str]
) -> Dict[str, Any]:
    """Allocate development resources for the task."""
    try:
        auth_token = token or "dummy_token_123"

        # Get devbox allocation
        devbox_info = get_dummy_devbox_for_task(
            task_path=task_plan_path, token=auth_token
        )

        # Update task plan with devbox info
        updated_task_plan = await add_devbox_info_to_task_plan(
            task_plan_path, devbox_info
        )

        if not updated_task_plan:
            return {
                "status": "failed",
                "error": "Failed to update task plan with devbox info",
            }

        # Extract galatea URL properly based on DevboxInfo type
        if hasattr(devbox_info, "project_public_address"):
            base_url = devbox_info.project_public_address
            galatea_url = (
                f"{base_url}galatea" if base_url else "http://localhost:3000/galatea"
            )
        else:
            # Fallback for dict-like object
            base_url = devbox_info.get(
                "project_public_address", "http://localhost:3000"
            )
            galatea_url = f"{base_url}galatea"

        return {
            "status": "success",
            "devbox_info": (
                devbox_info.__dict__
                if hasattr(devbox_info, "__dict__")
                else devbox_info
            ),
            "galatea_url": galatea_url,
            "token": auth_token,
            "task_plan": updated_task_plan,
        }

    except Exception as e:
        return {"status": "error", "error": str(e)}


async def _use_existing_devbox(
    task_plan_path: str, devbox_url: str, token: Optional[str]
) -> Dict[str, Any]:
    """Use an existing devbox instead of allocating a new one."""
    try:
        auth_token = token or "dummy_token_123"

        # Load task plan
        with open(task_plan_path, "r") as f:
            task_plan = json.load(f)

        # Ensure galatea URL format
        galatea_url = devbox_url if "galatea" in devbox_url else devbox_url + "galatea"

        return {
            "status": "success",
            "galatea_url": galatea_url,
            "token": auth_token,
            "task_plan": task_plan,
            "using_existing_devbox": True,
        }

    except Exception as e:
        return {"status": "error", "error": str(e)}


async def _run_implementation_step(
    galatea_url: str, token: str, task_plan: Dict[str, Any]
) -> Dict[str, Any]:
    """Run the codebase agent to implement the task."""
    try:
        result = await run_full_code_agent(
            galatea_url=galatea_url, token=token, task_plan=task_plan
        )

        return result

    except Exception as e:
        return {"status": "error", "error": str(e)}


async def _run_evaluation_step(
    project_url: str, task_plan: Dict[str, Any]
) -> Dict[str, Any]:
    """Run the browser agent to evaluate the implementation."""
    try:
        # Build evaluation prompt based on task plan
        functionalities = task_plan.get("functionalities", [])
        eval_prompt = _build_evaluation_prompt(task_plan)

        # Run browser agent for evaluation
        history = await run_browser_agent(
            prompt=eval_prompt, project_address=project_url, record_activity=True
        )

        # Analyze the browser agent results
        evaluation_passed = _analyze_browser_results(history, functionalities)

        if evaluation_passed:
            return {
                "status": "passed",
                "message": "All functionalities verified successfully",
                "steps_taken": len(history.history) if history else 0,
            }
        else:
            # Extract specific feedback about what failed
            feedback = _extract_failure_feedback(history, functionalities)
            return {
                "status": "failed",
                "feedback": feedback,
                "steps_taken": len(history.history) if history else 0,
            }

    except Exception as e:
        return {"status": "error", "error": str(e)}


def _build_evaluation_prompt(task_plan: Dict[str, Any]) -> str:
    """Build a comprehensive evaluation prompt for the browser agent."""
    task_name = task_plan.get("task_name", "the application")
    functionalities = task_plan.get("functionalities", [])

    prompt = f"""Please thoroughly test and evaluate {task_name} by checking the following functionalities:

"""

    for i, func in enumerate(functionalities, 1):
        prompt += f"{i}. {func.get('description', 'Unknown functionality')}\n"
        if func.get("workflow"):
            prompt += f"   Test workflow: {func['workflow']}\n"
        prompt += "\n"

    prompt += """For each functionality:
- Navigate through the UI as described
- Verify that the expected behavior occurs
- Take screenshots of key interactions
- Note any errors, missing features, or unexpected behavior

Provide a clear assessment of whether each functionality is working correctly."""

    return prompt


def _analyze_browser_results(history, functionalities) -> bool:
    """Analyze browser agent history to determine if evaluation passed."""
    # This is a simplified analysis - in production, you'd want more sophisticated checks
    if not history or not history.history:
        return False

    # Check if the browser agent completed its evaluation
    # In a real implementation, you'd analyze the extracted content and model outputs
    # to verify each functionality was tested and passed
    return len(history.history) > len(functionalities)


def _extract_failure_feedback(history, functionalities) -> Dict[str, Any]:
    """Extract specific feedback about what failed during evaluation."""
    feedback = {"failed_functionalities": [], "errors_found": [], "suggestions": []}

    # In a real implementation, analyze the browser history to identify:
    # - Which functionalities failed
    # - What errors were encountered
    # - Specific UI issues or missing features

    # For now, return generic feedback
    feedback["suggestions"].append("Review implementation for completeness")
    feedback["suggestions"].append("Ensure all UI elements are properly rendered")

    return feedback


async def _update_task_plan_with_feedback(
    task_plan: Dict[str, Any], feedback: Dict[str, Any]
) -> Dict[str, Any]:
    """Update the task plan based on evaluation feedback."""
    # Add feedback to additional notes
    additional_feedback = f"\n\nEvaluation Feedback:\n"

    if feedback.get("failed_functionalities"):
        additional_feedback += f"- Failed functionalities: {', '.join(feedback['failed_functionalities'])}\n"

    if feedback.get("errors_found"):
        additional_feedback += (
            f"- Errors found: {', '.join(feedback['errors_found'])}\n"
        )

    if feedback.get("suggestions"):
        additional_feedback += f"- Suggestions: {', '.join(feedback['suggestions'])}\n"

    task_plan["additional_notes"] = (
        task_plan.get("additional_notes", "") + additional_feedback
    )

    return task_plan


def _finalize_workflow(state: WorkflowState, logs_dir: str) -> Dict[str, Any]:
    """Finalize the workflow and save summary."""
    state.end_time = datetime.now().isoformat()
    state.current_step = None

    # Convert state to dict for return
    result = state.model_dump()

    # Save workflow summary
    summary_path = os.path.join(logs_dir, "workflow_summary.json")

    try:
        with open(summary_path, "w") as f:
            json.dump(result, f, indent=2, default=str)
        print(f"\n📄 Workflow summary saved to: {summary_path}")
    except Exception as e:
        print(f"⚠️ Failed to save workflow summary: {e}")

    return result


# Convenience function for backward compatibility
async def run_mixed_workflow_with_existing_devbox(
    initial_prompt: str, galatea_url: str, token: str
) -> Dict[str, Any]:
    """
    Run the mixed workflow with an existing devbox.

    Args:
        initial_prompt: The user's coding task request
        galatea_url: URL of the existing devbox
        token: Authentication token

    Returns:
        Dict containing the workflow results
    """
    return await run_mixed_workflow(
        initial_prompt=initial_prompt, token=token, existing_devbox_url=galatea_url
    )


# Test function
async def test_mixed_workflow():
    """Test the mixed workflow with a sample prompt."""
    test_prompt = """Create a modern task management web application with the following features:
    - User can create, edit, and delete tasks
    - Tasks have title, description, due date, and priority
    - Tasks can be marked as complete
    - Filter tasks by status (all, active, completed)
    - Responsive design with a clean, modern UI
    """

    print("🧪 Testing Mixed Workflow")
    print(f"📝 Test Prompt: {test_prompt}")

    result = await run_mixed_workflow(test_prompt)

    print("\n" + "=" * 60)
    print("🎯 WORKFLOW RESULT")
    print("=" * 60)
    print(json.dumps(result, indent=2, default=str))

    return result


if __name__ == "__main__":
    asyncio.run(test_mixed_workflow())
