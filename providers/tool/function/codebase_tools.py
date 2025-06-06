import asyncio
import aiohttp
from langchain_core.tools import tool
from pydantic import BaseModel, Field
from typing import List, Optional, Union, Literal, Annotated
from langgraph.prebuilt import InjectedState
from langgraph.prebuilt.chat_agent_executor import AgentState
from langchain_core.runnables import RunnableConfig


class FindFilesParams(BaseModel):
    dir: str = Field(
        description="Directory path to search from (relative to project root, e.g., 'project/src/')."
    )
    suffixes: List[str] = Field(
        description="File extensions to search for (e.g., ['ts', 'tsx', 'js'])."
    )
    exclude_dirs: Optional[List[str]] = Field(
        default=None,
        description="Directories to exclude (e.g., ['node_modules', 'dist']).",
    )


class EditorCommandParams(BaseModel):
    command: Literal["view", "create", "str_replace", "insert", "undo_edit"] = Field(
        description="The editor command to execute."
    )
    path: Optional[str] = Field(
        default=None,
        description="The file path to operate on (relative to project root). Required for non-view commands and single-file view.",
    )
    paths: Optional[List[str]] = Field(
        default=None,
        description="An array of file paths to view (for multi-file view operations only).",
    )
    file_text: Optional[str] = Field(
        default=None, description="The file content for create or replace operations."
    )
    insert_line: Optional[int] = Field(
        default=None, description="The line number for insert operations (1-based)."
    )
    new_str: Optional[str] = Field(
        default=None, description="The new string for insert or str_replace operations."
    )
    old_str: Optional[str] = Field(
        default=None,
        description="The old string to be replaced in str_replace operations.",
    )
    view_range: Optional[List[int]] = Field(
        default=None,
        description="The line range to view (e.g., [1, 10] or [5, -1] for all lines from 5). Applied to all files in a multi-file view.",
    )


class NpmScriptParams(BaseModel):
    script: Literal["lint", "format"] = Field(
        description="The npm script to run: 'lint' or 'format'."
    )


class UpdateProjectStructureParams(BaseModel):
    project_structure: dict = Field(
        description="The project structure to update. The project structure is a dictionary with the following structure: {project_name: [file_name, file_name, ...], project_name: [file_name, file_name, ...], ...}"
    )


class TaskCompletionParams(BaseModel):
    summary: str = Field(
        description="A brief summary of what was implemented and completed."
    )
    functionalities_completed: List[str] = Field(
        description="List of functionalities that were successfully implemented."
    )
    files_modified: Optional[List[str]] = Field(
        default=None,
        description="List of files that were created or modified during implementation.",
    )


async def fetch_with_timeout_and_retry(
    session: aiohttp.ClientSession,
    url: str,
    token: str,
    method: str = "GET",
    json_data: Optional[dict] = None,
    timeout_seconds: int = 20,
    max_retries: int = 3,
) -> dict:
    """Helper function for HTTP requests with timeout and retry logic."""
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {token}",
    }
    timeout = aiohttp.ClientTimeout(total=timeout_seconds)

    for attempt in range(max_retries):
        print(f"🔄 Attempt {attempt + 1}/{max_retries} for {method} request to {url}")
        print(f"📤 Sending {method} request with timeout {timeout_seconds}s")

        response = await session.request(
            method=method,
            url=url,
            json=json_data,
            headers=headers,
            timeout=timeout,
        )

        print(f"📥 Received response with status {response.status}")

        if not response.ok:
            error_msg = (await response.json()).get("message", "Request failed")
            print(f"❌ Request failed: {error_msg}")
            return {"success": False, "error": error_msg}

        try:
            data = await response.json()
            print("✅ Request successful")
            return data
        except aiohttp.ContentTypeError:
            text = await response.text()
            print(f"⚠️ Non-JSON response received: {text[:100]}...")
            return {"success": False, "error": f"Non-JSON response: {text}"}

    print(f"❌ All {max_retries} attempts failed for {method} request to {url}")
    return {"success": False, "error": f"Request failed after {max_retries} attempts"}


@tool("codebase_find_files", args_schema=FindFilesParams)
async def codebase_find_files(
    dir: str,
    suffixes: List[str],
    exclude_dirs: Optional[List[str]] = None,
    state: Annotated[AgentState, InjectedState] = None,
    config: RunnableConfig = None,
) -> dict:
    """Find files in the project matching specific suffixes and excluding directories."""
    token = config["configurable"]["token"]
    url = config["configurable"]["project_address"]
    async with aiohttp.ClientSession() as session:
        request_data = {
            "dir": dir,
            "suffixes": suffixes,
        }
        if exclude_dirs:
            request_data["exclude_dirs"] = exclude_dirs

        result = await fetch_with_timeout_and_retry(
            session=session,
            url=f"{url}/galatea/api/editor/find-files",
            token=token,
            method="POST",
            json_data=request_data,
        )

        if result.get("success", True) and "files" in result:
            return {
                "success": True,
                "files": result.get("files", []),
                "message": f"Found {len(result.get('files', []))} files matching criteria",
            }

        return result


@tool("codebase_editor_command", args_schema=EditorCommandParams)
async def codebase_editor_command(
    command: Literal["view", "create", "str_replace", "insert", "undo_edit"],
    path: Optional[str] = None,
    paths: Optional[List[str]] = None,
    file_text: Optional[str] = None,
    insert_line: Optional[int] = None,
    new_str: Optional[str] = None,
    old_str: Optional[str] = None,
    view_range: Optional[List[int]] = None,
    state: Annotated[AgentState, InjectedState] = None,
    config: RunnableConfig = None,
) -> dict:
    """Send an editor command (view, create, str_replace, insert, undo_edit) to the backend for file operations."""
    token = config["configurable"]["token"]
    url = config["configurable"]["project_address"]
    # Validation logic similar to TypeScript superRefine
    if command == "view":
        if not path and (not paths or len(paths) == 0):
            return {
                "success": False,
                "error": "For 'view' command, either 'path' (for single file) or a non-empty 'paths' array (for multiple files) must be provided.",
            }
        if path and paths and len(paths) > 0:
            return {
                "success": False,
                "error": "For 'view' command, provide either 'path' or 'paths', not both.",
            }
    else:
        # For non-"view" commands
        if not path:
            return {
                "success": False,
                "error": f"'path' is required for command '{command}'.",
            }
        if paths and len(paths) > 0:
            return {
                "success": False,
                "error": f"'paths' should not be provided for command '{command}'.",
            }

    async with aiohttp.ClientSession() as session:
        body = {"command": command}

        if view_range:
            body["view_range"] = view_range

        if command == "view":
            if paths and len(paths) > 0:
                body["paths"] = paths
            else:
                body["path"] = path
        else:
            body["path"] = path

        # Add optional parameters
        if file_text is not None:
            body["file_text"] = file_text
        if insert_line is not None:
            body["insert_line"] = insert_line
        if new_str is not None:
            body["new_str"] = new_str
        if old_str is not None:
            body["old_str"] = old_str

        result = await fetch_with_timeout_and_retry(
            session=session,
            url=f"{url}/galatea/api/editor/command",
            token=token,
            method="POST",
            json_data=body,
        )

        return result


@tool("codebase_npm_script", args_schema=NpmScriptParams)
async def codebase_npm_script(
    script: Literal["lint", "format"],
    state: Annotated[AgentState, InjectedState] = None,
    config: RunnableConfig = None,
) -> dict:
    """Run npm scripts (lint or format) in the project root and return their output."""
    token = config["configurable"]["token"]
    url = config["configurable"]["project_address"]
    async with aiohttp.ClientSession() as session:
        result = await fetch_with_timeout_and_retry(
            session=session,
            url=f"{url}/galatea/api/editor/{script}",
            token=token,
            method="POST",
        )
        return result


@tool("codebase_update_project_structure", args_schema=UpdateProjectStructureParams)
async def codebase_update_project_structure(
    project_structure: dict,
    state: Annotated[AgentState, InjectedState] = None,
    config: RunnableConfig = None,
) -> dict:
    """Update the project structure with the given project structure."""
    return {
        "success": True,
        "project_structure": project_structure,
        "message": "Project structure updated",
    }


@tool("task_completion", args_schema=TaskCompletionParams)
def task_completion(
    summary: str,
    functionalities_completed: List[str],
    files_modified: Optional[List[str]] = None,
    state: Annotated[AgentState, InjectedState] = None,
    config: RunnableConfig = None,
) -> dict:
    """Indicate that the task implementation is complete. Use this tool when all functionalities have been implemented and tested."""
    return {
        "success": True,
        "task_completed": True,
        "summary": summary,
        "functionalities_completed": functionalities_completed,
        "files_modified": files_modified or [],
        "message": "Task completion indicated by agent",
    }
