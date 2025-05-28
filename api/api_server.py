# python -m api.api_server

from fastapi import FastAPI, Request
import uvicorn
import asyncio
from datetime import datetime, timedelta, timezone
from contextlib import asynccontextmanager
import json

from returns.pipeline import is_successful
from returns.unsafe import unsafe_perform_io

from browser_use import BrowserConfig
from browser_use.browser.context import BrowserContext

from .api_models import (
    BrowserContextFlowRequest,
    BrowserContextFlowResponse,
    CodebaseBasicFlowRequest,
    MixedFlowRequest,
    BrowserFullFlowRequest,
    BrowserFullFlowResponse,
    CodebaseFullFlowRequest,
    CodebaseFullFlowResponse,
)
from workflows.browser_workflows.context_browser_flow import run_context_browser_flow
from workflows.codebase_workflows.basic_code_flow import run_basic_code_flow
from workflows.browser_workflows.full_browser_flow import run_full_browser_flow
from workflows.codebase_workflows.full_code_flow import run_full_code_flow

from providers.browser.browser_models import default_browser_context_config
from providers.browser.browser_provider import (
    create_browser_state,
    add_user_context_and_metadata,
    get_user_context,
    remove_user_context,
    update_user_metadata,
)

from providers.codebase.codebase_provider import (
    create_codebase_state,
    add_user_project,
    get_user_project,
    remove_user_project,
    update_user_project_metadata,
)

# Configuration for user activity recycling
INACTIVITY_THRESHOLD_SECONDS = 3600  # 1 hour
RECYCLING_INTERVAL_SECONDS = 300  # 5 minutes

browser_state = create_browser_state(
    BrowserConfig(
        # headless=True,
        keep_alive=True,
        browser_class="chromium",
    )
)

codebase_state = create_codebase_state()


# Lifespan context manager
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage startup and shutdown events, including background tasks."""
    print("Starting up application and background tasks...")
    recycling_task = asyncio.create_task(recycle_inactive_users())
    print("User inactivity recycling task started via lifespan.")
    try:
        yield
    finally:
        print("Shutting down application...")
        # Optionally, you can try to cancel the task on shutdown, though it might not always be necessary
        # for a continuously running daemon-like task. If it has cleanup, it should handle cancellation.
        if not recycling_task.done():
            recycling_task.cancel()
            try:
                await recycling_task
            except asyncio.CancelledError:
                print("User inactivity recycling task was cancelled.")
        print("Application shutdown complete.")


app = FastAPI(lifespan=lifespan)  # Use the lifespan manager


# Helper to process removal and update global state for browser
async def _handle_browser_user_removal(user_id_to_remove: str) -> None:
    global browser_state
    print(
        f"[{datetime.now(timezone.utc)}] Attempting to remove inactive browser context for user: {user_id_to_remove}"
    )

    # remove_user_context returns FutureResult[BrowserState, BrowserError]
    await (
        remove_user_context(browser_state, user_id_to_remove)
        .map(
            lambda new_state: globals().update(browser_state=new_state)
            or print(
                f"[{datetime.now(timezone.utc)}] Successfully removed browser context for user: {user_id_to_remove}"
            )
        )
        .lash(
            lambda error: print(
                f"[{datetime.now(timezone.utc)}] Error removing browser context for user {user_id_to_remove}: {error}"
            )
        )
    ).awaitable()  # Ensure the FutureResult is awaited


# Helper to process removal and update global state for codebase
def _handle_codebase_user_removal(user_id_to_remove: str) -> None:
    global codebase_state
    print(
        f"[{datetime.now(timezone.utc)}] Attempting to remove inactive codebase project for user: {user_id_to_remove}"
    )

    # remove_user_project returns Result[CodebaseState, CodebaseError]
    # We need to handle the Success/Failure from the Result.
    result = remove_user_project(codebase_state, user_id_to_remove)
    if is_successful(result):
        codebase_state = unsafe_perform_io(result.unwrap())  # Update global state
        print(
            f"[{datetime.now(timezone.utc)}] Successfully removed codebase project for user: {user_id_to_remove}"
        )
    else:
        print(
            f"[{datetime.now(timezone.utc)}] Error removing codebase project for user {user_id_to_remove}: {result.failure()}"
        )


async def recycle_inactive_users():
    """Periodically checks for and removes inactive user states."""
    # Global state is modified by helper functions now
    while True:
        await asyncio.sleep(RECYCLING_INTERVAL_SECONDS)
        print(f"[{datetime.now(timezone.utc)}] Running inactivity check...")
        now = datetime.now(timezone.utc)
        threshold_time = now - timedelta(seconds=INACTIVITY_THRESHOLD_SECONDS)

        # Identify inactive browser users
        # browser_state.user_metadata.items() can change size during iteration if modified elsewhere, copy for safety
        inactive_browser_users_to_process = [
            user_id
            for user_id, metadata in list(browser_state.user_metadata.items())
            if metadata.last_active_timestamp < threshold_time
        ]
        if inactive_browser_users_to_process:
            print(
                f"[{datetime.now(timezone.utc)}] Found inactive browser users: {inactive_browser_users_to_process}"
            )
            for user_id in inactive_browser_users_to_process:
                await _handle_browser_user_removal(user_id)

        # Identify inactive codebase users
        # codebase_state.user_projects.items() can change size during iteration, copy for safety
        inactive_codebase_users_to_process = [
            user_id
            for user_id, project in list(codebase_state.user_projects.items())
            if project.last_active_timestamp < threshold_time
        ]
        if inactive_codebase_users_to_process:
            print(
                f"[{datetime.now(timezone.utc)}] Found inactive codebase users: {inactive_codebase_users_to_process}"
            )
            for user_id in inactive_codebase_users_to_process:
                _handle_codebase_user_removal(user_id)  # This is synchronous

        if (
            not inactive_browser_users_to_process
            and not inactive_codebase_users_to_process
        ):
            print(
                f"[{datetime.now(timezone.utc)}] No inactive users found in this cycle."
            )


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.post("/browser/context_flow")
async def browser_context_flow(request: Request):
    global browser_state
    data = await request.json()
    validated_data = BrowserContextFlowRequest(**data)

    if not validated_data.user_id in browser_state.user_contexts.keys():
        result = await add_user_context_and_metadata(
            browser_state,
            validated_data.user_id,
            validated_data.context_config,
            validated_data.metadata,
        )

        if is_successful(result):
            browser_state = unsafe_perform_io(result.unwrap())
        else:
            return {"error": f"Failed to create context: {result.failure().message}"}

    context_result = get_user_context(browser_state, validated_data.user_id)
    if not is_successful(context_result):
        return {"error": f"Failed to get context: {context_result.failure().message}"}

    context = context_result.unwrap()

    history = await run_context_browser_flow(
        context,
        validated_data.metadata,
        validated_data.prompt,
    )

    return BrowserContextFlowResponse(
        final_result=history.final_result()
    ).model_dump_json()


@app.post("/codebase/basic_flow")
async def codebase_basic_flow(request: Request):
    global codebase_state
    data = await request.json()
    validated_data = CodebaseBasicFlowRequest(**data)

    # Add/Update user project information in the state
    add_project_result_fr = add_user_project(
        current_state=codebase_state,
        user_id=validated_data.user_id,
        project_address=validated_data.project.project_address,
        metadata=validated_data.project.metadata,
    )
    add_project_result = (
        await add_project_result_fr.awaitable()
    )  # Get the Result[CodebaseState, CodebaseError]

    if not is_successful(add_project_result):
        error_details = unsafe_perform_io(add_project_result.failure())
        return {
            "error": f"Failed to add or update user project: {error_details.message}",
            "details": error_details.details,
            "operation": error_details.operation_name.value,
        }, 500  # Internal Server Error or appropriate status

    codebase_state = unsafe_perform_io(
        add_project_result.unwrap()
    )  # Update global state

    # Proceed with the basic code flow
    await run_basic_code_flow(
        validated_data.project.project_address, validated_data.prompt
    )

    # Return a simple success string instead of a CodebaseBasicFlowResponse
    return "Task completed successfully"


@app.post("/browser/full_flow")
async def browser_full_flow(request: Request):
    global browser_state
    data = await request.json()
    validated_data = BrowserFullFlowRequest(**data)

    if validated_data.url is None:
        return {"error": "URL is required"}

    browser_flow_result = await run_full_browser_flow(
        BrowserContext(
            browser=browser_state.browser_instance,
            config=default_browser_context_config,
        ),
        validated_data.url,
        validated_data.prompt,
    )

    return BrowserFullFlowResponse(
        final_result=browser_flow_result.final_result,
        urls=browser_flow_result.urls,
        screenshot_urls=browser_flow_result.screenshot_urls,
        model_actions=browser_flow_result.model_actions,
    ).model_dump_json()


@app.post("/codebase/full_flow")
async def codebase_full_flow(request: Request):
    global codebase_state
    data = await request.json()
    validated_data = CodebaseFullFlowRequest(**data)

    if validated_data.url is None:
        return {"error": "URL is required"}

    code_flow_result = await run_full_code_flow(
        validated_data.url, validated_data.prompt
    )

    result = CodebaseFullFlowResponse(
        final_result=code_flow_result.final_result,
        modified_files=code_flow_result.modified_files,
    ).model_dump_json()

    return json.dumps("Codebase full flow completed")


if __name__ == "__main__":
    print("Starting Context Flow API on http://0.0.0.0:3050")
    uvicorn.run("api.api_server:app", host="0.0.0.0", port=3050, reload=True)
