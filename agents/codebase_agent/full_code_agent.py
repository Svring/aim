# python -m agents.codebase_agent.full_code_agent

import json
import asyncio
from typing import Dict, List, Optional, Any
from langchain_core.messages import (
    HumanMessage,
    SystemMessage,
    AIMessage,
    ToolMessage,
)

from providers.backbone.backbone_provider import (
    get_sealos_model,
    build_codebase_agent_prompt,
)
from providers.tool.function.codebase_tools import (
    codebase_find_files,
    codebase_editor_command,
    codebase_npm_script,
    task_completion,
    _execute_codebase_find_files,
    _execute_codebase_editor_command,
    _execute_codebase_npm_script,
    _execute_task_completion,
    FindFilesParams,
    EditorCommandParams,
    NpmScriptParams,
    TaskCompletionParams,
)


async def _execute_tools(
    tool_calls: List[Dict], galatea_url: str, token: str, tools: Dict
) -> List[ToolMessage]:
    """Execute the tools requested by the AI with token injection."""
    tool_results = []

    for tool_call in tool_calls:
        tool_name = tool_call["name"]
        tool_args = tool_call["args"]

        # Unwrap 'params' if present
        if "params" in tool_args:
            tool_args = tool_args["params"]

        print(f"🔧 Executing tool: {tool_name}")
        print(f"   Args: {json.dumps(tool_args, indent=2)}")

        try:
            # Execute the tool with token and URL injection
            if tool_name == "codebase_find_files":
                params = FindFilesParams(**tool_args)
                result = _execute_codebase_find_files(params, token, galatea_url)
            elif tool_name == "codebase_editor_command":
                params = EditorCommandParams(**tool_args)
                result = _execute_codebase_editor_command(params, token, galatea_url)
            elif tool_name == "codebase_npm_script":
                params = NpmScriptParams(**tool_args)
                result = _execute_codebase_npm_script(params, token, galatea_url)
            elif tool_name == "task_completion":
                params = TaskCompletionParams(**tool_args)
                result = _execute_task_completion(params, token, galatea_url)
            else:
                error_msg = f"Unknown tool: {tool_name}"
                print(f"   Error: {error_msg}")
                result = {"success": False, "error": error_msg}

            print(f"   Result: {json.dumps(result, indent=2)}")

            tool_message = ToolMessage(
                content=json.dumps(result), tool_call_id=tool_call["id"]
            )
            tool_results.append(tool_message)

        except Exception as e:
            error_msg = f"Error executing tool {tool_name}: {str(e)}"
            print(f"   Error: {error_msg}")
            tool_message = ToolMessage(
                content=json.dumps({"success": False, "error": error_msg}),
                tool_call_id=tool_call["id"],
            )
            tool_results.append(tool_message)

    return tool_results


async def _check_task_completion(
    galatea_url: str, token: str, task_plan: Dict[str, Any]
) -> bool:
    """Check if the implementation is complete by running tests and linting."""
    try:
        # Run linting to check for errors
        lint_params = NpmScriptParams(script="lint")
        lint_result = _execute_codebase_npm_script(lint_params, token, galatea_url)

        if lint_result.get("success", False):
            print("✅ Linting passed")

            # Additional checks based on task requirements
            functionalities = task_plan.get("functionalities", [])
            if functionalities:
                # Check if key files exist for the functionalities
                find_params = FindFilesParams(
                    dir=".",
                    suffixes=["tsx", "ts", "jsx", "js"],
                    exclude_dirs=["node_modules", "dist", ".next"],
                )
                find_result = _execute_codebase_find_files(
                    find_params, token, galatea_url
                )

                if find_result.get("success", False) and find_result.get("files"):
                    print(f"✅ Found {len(find_result['files'])} implementation files")
                    return True
            else:
                return True
        else:
            print(
                f"⚠️ Linting issues found: {lint_result.get('error', 'Unknown error')}"
            )
            return False

    except Exception as e:
        print(f"Error checking completion: {str(e)}")
        return False


async def run_full_code_agent(
    galatea_url: str, token: str, task_plan: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Run the full codebase agent autonomously to implement the given task plan.

    Args:
        galatea_url: The URL of the Galatea development environment
        token: Authentication token for API requests
        task_plan: The task plan dictionary containing implementation details

    Returns:
        Dict containing the result of the implementation
    """
    print(
        f"🚀 Starting Full Codebase Agent for task: {task_plan.get('task_name', 'Unknown')}"
    )
    print(f"🔗 Using Galatea URL: {galatea_url}")
    print(f"🎯 Task functionalities: {task_plan.get('functionalities', [])}")

    # Initialize components
    llm = get_sealos_model("gpt-4o-mini")
    tools = {
        "codebase_find_files": codebase_find_files,
        "codebase_editor_command": codebase_editor_command,
        "codebase_npm_script": codebase_npm_script,
        "task_completion": task_completion,
    }
    llm_with_tools = llm.bind_tools(list(tools.values()))
    max_iterations = 10
    current_iteration = 0

    # Initialize conversation with enhanced system prompt
    system_prompt = build_codebase_agent_prompt(galatea_url, task_plan)
    enhanced_prompt = f"""{system_prompt}

IMPORTANT INSTRUCTIONS:
- You are working autonomously to implement the task plan completely
- Use the provided tools to explore, understand, and modify the codebase
- The galatea_url and token will be automatically handled for all tool calls
- Focus on implementing ALL functionalities listed in the task plan
- Test your implementation by running lint checks
- When you believe the task is complete, use the 'task_completion' tool to indicate completion
- Be thorough and ensure all requirements are met before declaring completion
"""

    messages = [
        SystemMessage(content=enhanced_prompt),
        HumanMessage(
            content=f"""Please implement the following task plan completely and autonomously:

Task Name: {task_plan.get('task_name', 'Unknown')}
User Prompt: {task_plan.get('user_prompt', '')}
Template: {task_plan.get('template', 'Unknown')}
Design Principles: {task_plan.get('design_principles', [])}
Functionalities: {task_plan.get('functionalities', [])}
Additional Notes: {task_plan.get('additional_notes', '')}

Start by exploring the current codebase structure, then implement all required functionalities step by step. 
When you have completed all functionalities and verified they work correctly, use the task_completion tool to indicate completion."""
        ),
    ]

    try:
        while current_iteration < max_iterations:
            current_iteration += 1
            print(f"\n--- Iteration {current_iteration} ---")

            # Get AI response
            try:
                response = await llm_with_tools.ainvoke(messages)
                print(f"🤖 AI Response: {response.content}")
            except Exception as e:
                print(f"❌ Error getting AI response: {str(e)}")
                break

            if not response:
                print("❌ Failed to get AI response")
                break

            messages.append(response)

            # Check if AI wants to use tools
            if response.tool_calls:
                print(f"🔧 Tool Calls: {response.tool_calls}")
                tool_results = await _execute_tools(
                    response.tool_calls, galatea_url, token, tools
                )

                # Add tool results to conversation
                for tool_result in tool_results:
                    messages.append(tool_result)

                # Check if task completion was indicated
                for tool_call in response.tool_calls:
                    if tool_call["name"] == "task_completion":
                        # Find the corresponding result
                        for tool_result in tool_results:
                            if tool_result.tool_call_id == tool_call["id"]:
                                result_data = json.loads(tool_result.content)
                                if result_data.get("task_completed", False):
                                    # Verify completion with actual checks
                                    if await _check_task_completion(
                                        galatea_url, token, task_plan
                                    ):
                                        print("\n🎉 Task completion confirmed!")
                                        return {
                                            "status": "completed",
                                            "message": "Task implementation completed successfully",
                                            "iterations": current_iteration,
                                            "galatea_url": galatea_url,
                                            "task_name": task_plan.get(
                                                "task_name", "Unknown"
                                            ),
                                            "completion_summary": result_data.get(
                                                "summary", ""
                                            ),
                                            "functionalities_completed": result_data.get(
                                                "functionalities_completed", []
                                            ),
                                            "files_modified": result_data.get(
                                                "files_modified", []
                                            ),
                                        }
                                    else:
                                        # Completion claimed but verification failed
                                        messages.append(
                                            HumanMessage(
                                                content="Task completion was indicated but verification failed. Please continue working on the task and ensure all functionalities are properly implemented and tested."
                                            )
                                        )
                                        break
            else:
                # AI provided a response without tool calls
                print(f"🤖 AI Response: {response.content}")

        # Max iterations reached
        print(f"\n⚠️ Maximum iterations ({max_iterations}) reached")
        return {
            "status": "max_iterations_reached",
            "message": f"Implementation stopped after {max_iterations} iterations",
            "iterations": current_iteration,
            "galatea_url": galatea_url,
            "task_name": task_plan.get("task_name", "Unknown"),
        }

    except Exception as e:
        print(f"\n❌ Error during implementation: {str(e)}")
        return {
            "status": "error",
            "message": f"Implementation failed: {str(e)}",
            "iterations": current_iteration,
            "galatea_url": galatea_url,
            "task_name": task_plan.get("task_name", "Unknown"),
        }


async def test_run_full_code_agent():
    """
    Test function for run_full_code_agent using dummy devbox and company news website task plan.

    This test:
    1. Loads the company news website task plan from JSON file
    2. Gets dummy devbox info for token and galatea_url
    3. Runs the full code agent with the task plan
    4. Prints the results
    """
    print("🧪 Starting Full Code Agent Test")
    print("=" * 50)

    try:
        # Import here to avoid circular imports
        from providers.resource.resource_provider import get_dummy_devbox_for_task

        # Load task plan from JSON file
        task_plan_path = "task_plans/company_news_website_with_categories_and_tags.json"
        print(f"📋 Loading task plan from: {task_plan_path}")

        with open(task_plan_path, "r") as f:
            task_plan = json.load(f)

        print(f"✅ Task plan loaded: {task_plan.get('task_name', 'Unknown')}")
        print(f"📝 Functionalities count: {len(task_plan.get('functionalities', []))}")

        # Get dummy devbox info
        print("\n🔧 Getting dummy devbox info...")
        devbox_info = get_dummy_devbox_for_task(
            task_path=task_plan_path, token="test_token_123"
        )

        # Extract galatea_url and token
        galatea_url = devbox_info.project_public_address + "galatea"
        token = devbox_info.token or "test_token_123"

        print(f"🔗 Galatea URL: {galatea_url}")
        print(f"🔑 Token: {token[:10]}..." if len(token) > 10 else f"🔑 Token: {token}")

        # Run the full code agent
        print("\n🚀 Starting Full Code Agent execution...")
        print("=" * 50)

        result = await run_full_code_agent(
            galatea_url=galatea_url, token=token, task_plan=task_plan
        )

        # Print results
        print("\n" + "=" * 50)
        print("🎯 TEST RESULTS")
        print("=" * 50)
        print(f"Status: {result.get('status', 'Unknown')}")
        print(f"Message: {result.get('message', 'No message')}")
        print(f"Iterations: {result.get('iterations', 0)}")
        print(f"Task Name: {result.get('task_name', 'Unknown')}")

        if result.get("status") == "completed":
            print(
                f"✅ Completion Summary: {result.get('completion_summary', 'No summary')}"
            )
            print(
                f"✅ Functionalities Completed: {len(result.get('functionalities_completed', []))}"
            )
            print(f"✅ Files Modified: {len(result.get('files_modified', []))}")

            # Print detailed completion info
            if result.get("functionalities_completed"):
                print("\n📋 Completed Functionalities:")
                for i, func in enumerate(
                    result.get("functionalities_completed", []), 1
                ):
                    print(f"  {i}. {func}")

            if result.get("files_modified"):
                print("\n📁 Modified Files:")
                for i, file in enumerate(result.get("files_modified", []), 1):
                    print(f"  {i}. {file}")

        print("\n🧪 Test completed!")
        return result

    except FileNotFoundError as e:
        print(f"❌ Task plan file not found: {e}")
        return {"status": "error", "message": f"Task plan file not found: {e}"}
    except Exception as e:
        print(f"❌ Test failed with error: {str(e)}")
        return {"status": "error", "message": f"Test failed: {str(e)}"}


# For testing purposes
if __name__ == "__main__":
    asyncio.run(test_run_full_code_agent())
