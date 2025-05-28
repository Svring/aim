import asyncio
import aiohttp
from langchain_core.tools import tool
from pydantic import BaseModel, Field
from typing import List, Optional, Union, Literal
import json


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
    last_error = None

    for attempt in range(max_retries):
        try:
            timeout = aiohttp.ClientTimeout(total=timeout_seconds)
            headers = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {token}",
            }

            async with session.request(
                method=method,
                url=url,
                json=json_data,
                headers=headers,
                timeout=timeout,
            ) as response:
                try:
                    data = await response.json()
                except aiohttp.ContentTypeError:
                    # If not JSON, try to get plain text
                    text = await response.text()
                    return {"success": False, "error": f"Non-JSON response: {text}"}

                if not response.ok:
                    return {
                        "success": False,
                        "error": data.get("message", "Request failed"),
                    }

                return data

        except asyncio.TimeoutError as e:
            last_error = e
            if attempt < max_retries - 1:
                continue  # Retry on timeout
            else:
                break
        except Exception as e:
            # Don't retry on non-timeout errors
            return {"success": False, "error": f"Request failed: {str(e)}"}

    return {
        "success": False,
        "error": f"Request timed out after {max_retries} attempts: {str(last_error)}",
    }


def _execute_codebase_find_files(params: FindFilesParams, token: str, url: str) -> dict:
    """Internal function to execute find files with token."""

    async def _find_files():
        async with aiohttp.ClientSession() as session:
            request_data = {
                "dir": params.dir,
                "suffixes": params.suffixes,
            }
            if params.exclude_dirs:
                request_data["exclude_dirs"] = params.exclude_dirs

            result = await fetch_with_timeout_and_retry(
                session=session,
                url=f"{url}/api/project/find-files",
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

    # Run the async function
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        return loop.run_until_complete(_find_files())
    finally:
        loop.close()


def _execute_codebase_editor_command(
    params: EditorCommandParams, token: str, url: str
) -> dict:
    """Internal function to execute editor command with token."""
    # Validation logic similar to TypeScript superRefine
    if params.command == "view":
        if not params.path and (not params.paths or len(params.paths) == 0):
            return {
                "success": False,
                "error": "For 'view' command, either 'path' (for single file) or a non-empty 'paths' array (for multiple files) must be provided.",
            }
        if params.path and params.paths and len(params.paths) > 0:
            return {
                "success": False,
                "error": "For 'view' command, provide either 'path' or 'paths', not both.",
            }
    else:
        # For non-"view" commands
        if not params.path:
            return {
                "success": False,
                "error": f"'path' is required for command '{params.command}'.",
            }
        if params.paths and len(params.paths) > 0:
            return {
                "success": False,
                "error": f"'paths' should not be provided for command '{params.command}'.",
            }

    async def _editor_command():
        async with aiohttp.ClientSession() as session:
            body = {"command": params.command}

            if params.view_range:
                body["view_range"] = params.view_range

            if params.command == "view":
                if params.paths and len(params.paths) > 0:
                    body["paths"] = params.paths
                else:
                    body["path"] = params.path
            else:
                body["path"] = params.path

            # Add optional parameters
            if params.file_text is not None:
                body["file_text"] = params.file_text
            if params.insert_line is not None:
                body["insert_line"] = params.insert_line
            if params.new_str is not None:
                body["new_str"] = params.new_str
            if params.old_str is not None:
                body["old_str"] = params.old_str

            result = await fetch_with_timeout_and_retry(
                session=session,
                url=f"{url}/api/editor/command",
                token=token,
                method="POST",
                json_data=body,
            )

            return result

    # Run the async function
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        return loop.run_until_complete(_editor_command())
    finally:
        loop.close()


def _execute_codebase_npm_script(params: NpmScriptParams, token: str, url: str) -> dict:
    """Internal function to execute npm script with token."""

    async def _npm_script():
        async with aiohttp.ClientSession() as session:
            result = await fetch_with_timeout_and_retry(
                session=session,
                url=f"{url}/api/project/{params.script}",
                token=token,
                method="POST",
            )

            return result

    # Run the async function
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        return loop.run_until_complete(_npm_script())
    finally:
        loop.close()


def _execute_task_completion(
    params: TaskCompletionParams, token: str, url: str
) -> dict:
    """Internal function to handle task completion indication."""
    # This is a local tool that doesn't make network requests
    # It simply returns the completion information
    return {
        "success": True,
        "task_completed": True,
        "summary": params.summary,
        "functionalities_completed": params.functionalities_completed,
        "files_modified": params.files_modified or [],
        "message": "Task completion indicated by agent",
    }


@tool
def codebase_find_files(params: FindFilesParams) -> dict:
    """Find files in the project matching specific suffixes and excluding directories."""
    # This will be called by the agent without token, token will be injected during execution
    return {"tool_name": "codebase_find_files", "params": params.dict()}


@tool
def codebase_editor_command(params: EditorCommandParams) -> dict:
    """Send an editor command (view, create, str_replace, insert, undo_edit) to the backend for file operations."""
    # This will be called by the agent without token, token will be injected during execution
    return {"tool_name": "codebase_editor_command", "params": params.dict()}


@tool
def codebase_npm_script(params: NpmScriptParams) -> dict:
    """Run npm scripts (lint or format) in the project root and return their output."""
    # This will be called by the agent without token, token will be injected during execution
    return {"tool_name": "codebase_npm_script", "params": params.dict()}


@tool
def task_completion(params: TaskCompletionParams) -> dict:
    """Indicate that the task implementation is complete. Use this tool when all functionalities have been implemented and tested."""
    # This will be called by the agent without token, token will be injected during execution
    return {"tool_name": "task_completion", "params": params.dict()}
