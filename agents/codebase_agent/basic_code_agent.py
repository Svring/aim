import asyncio  # Added for asyncio.sleep
from pydantic import BaseModel, Field
from langchain_core.tools import tool

from typing import Optional, Dict, Any
from returns.future import future_safe
import httpx

# --- Constants for Polling ---
POLLING_INTERVAL_SECONDS = 2  # Interval between status checks
MAX_POLLING_ATTEMPTS = (
    150  # Max attempts (150 * 2s = 300s = 5 minutes total polling time)
)

# --- Pydantic Models for API Interaction ---
# These models align with the Rust backend API structure and adhere to style guidelines.


class SubmitResponsePayload(BaseModel):
    task_id: str

    class Config:
        frozen = True


class CodexResponseDetails(BaseModel):
    raw_codex_output: Optional[str] = None
    assistant_message: Optional[str] = None
    function_result: Optional[str] = None

    class Config:
        frozen = True


class TaskStatusDetailsPayload(BaseModel):
    query_text: str
    response: Optional[CodexResponseDetails] = None
    error: Optional[str] = None

    class Config:
        frozen = True


class TaskStatusPayload(BaseModel):
    status: str
    details: TaskStatusDetailsPayload

    class Config:
        frozen = True


class StatusResponsePayload(BaseModel):
    task_id: str
    task_status: TaskStatusPayload

    class Config:
        frozen = True


@future_safe
async def run_basic_code_agent(project_address: str, prompt: str) -> str:
    """
    Run the code agent by submitting a task and polling for its completion.

    This function submits a prompt to the '/galatea/api/codex/submit' endpoint,
    retrieves a task_id, and then polls the '/galatea/api/codex/status/{task_id}'
    endpoint until the task is completed or fails. The raw_codex_output from the
    completed task is returned.

    Relies on @future_safe to wrap exceptions (e.g., HTTP errors, task failures,
    timeouts) in a returns.result.Failure.
    """
    submit_url = f"{project_address}/galatea/api/codex/submit"
    payload = {"query_text": prompt}

    async with httpx.AsyncClient() as client:
        # 1. Submit the task
        try:
            submit_response_http = await client.post(
                submit_url, json=payload, timeout=30.0
            )
            submit_response_http.raise_for_status()
            submit_payload = SubmitResponsePayload(**submit_response_http.json())
            task_id = submit_payload.task_id
        except (httpx.HTTPStatusError, httpx.RequestError) as e:
            raise Exception(f"Failed to submit task to {submit_url}: {e}") from e
        except (
            Exception
        ) as e:  # Catches Pydantic validation errors or other unexpected issues
            raise Exception(
                f"Error processing submission response from {submit_url}: {e}"
            ) from e

        # 2. Poll for task status
        status_url = f"{project_address}/galatea/api/codex/status/{task_id}"

        for attempt in range(MAX_POLLING_ATTEMPTS):
            await asyncio.sleep(POLLING_INTERVAL_SECONDS)

            try:
                status_response_http = await client.get(status_url, timeout=30.0)
                status_response_http.raise_for_status()
                status_data = StatusResponsePayload(**status_response_http.json())
            except httpx.HTTPStatusError as e:
                # If specific non-fatal HTTP errors should allow retries, handle them here.
                # For now, any HTTP error during polling is considered a failure for that attempt.
                print(
                    f"Polling attempt {attempt + 1}/{MAX_POLLING_ATTEMPTS} for task {task_id} failed with HTTP error: {e}. Retrying..."
                )
                if attempt == MAX_POLLING_ATTEMPTS - 1:
                    raise Exception(
                        f"Failed to get task status from {status_url} after {MAX_POLLING_ATTEMPTS} attempts due to HTTP error: {e}"
                    ) from e
                continue
            except httpx.RequestError as e:  # Network errors
                print(
                    f"Polling attempt {attempt + 1}/{MAX_POLLING_ATTEMPTS} for task {task_id} failed with network error: {e}. Retrying..."
                )
                if attempt == MAX_POLLING_ATTEMPTS - 1:
                    raise Exception(
                        f"Failed to get task status from {status_url} after {MAX_POLLING_ATTEMPTS} attempts due to network error: {e}"
                    ) from e
                continue
            except (
                Exception
            ) as e:  # Catches Pydantic validation errors or other unexpected issues
                raise Exception(
                    f"Error processing status response from {status_url} for task {task_id}: {e}"
                ) from e

            task_main_status = status_data.task_status.status
            task_details = status_data.task_status.details

            if task_main_status == "Completed":
                if (
                    task_details.response
                    and task_details.response.raw_codex_output is not None
                ):
                    return task_details.response.raw_codex_output
                else:
                    raise Exception(
                        f"Task {task_id} completed but 'raw_codex_output' was missing or null in the response."
                    )
            elif task_main_status == "Failed":
                error_message = task_details.error or "Unknown error"
                raise Exception(f"Task {task_id} failed: {error_message}")
            elif task_main_status in ["Pending", "Processing"]:
                print(
                    f"Task {task_id} is {task_main_status}. Polling attempt {attempt + 1}/{MAX_POLLING_ATTEMPTS}..."
                )
                # Continue to the next polling attempt
            else:
                raise Exception(
                    f"Task {task_id} returned an unknown status: '{task_main_status}'"
                )

        # If the loop completes, it means MAX_POLLING_ATTEMPTS was reached without completion
        raise Exception(
            f"Timeout: Task {task_id} did not complete within the allocated {MAX_POLLING_ATTEMPTS * POLLING_INTERVAL_SECONDS} seconds."
        )
