# python -m api.api_server

from fastapi import FastAPI, Request
import uvicorn
import asyncio
from datetime import datetime, timedelta

from returns.pipeline import is_successful
from returns.unsafe import unsafe_perform_io

from browser_use import BrowserConfig

from .api_models import (
    BrowserContextFlowRequest,
    BrowserContextFlowResponse,
    CodebaseBasicFlowRequest,
    CodebaseBasicFlowResponse,
)
from workflows.context_flow import run_context_flow
from workflows.code_workflows.basic_code_flow import run_basic_code_flow
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

app = FastAPI()

# Configuration for user activity recycling
INACTIVITY_THRESHOLD_SECONDS = 3600  # 1 hour
RECYCLING_INTERVAL_SECONDS = 300  # 5 minutes

browser_state = create_browser_state(
    BrowserConfig(
        headless=True,
        keep_alive=True,
        browser_class="chromium",
    )
)

codebase_state = create_codebase_state()


async def recycle_inactive_users():
    """Periodically checks for and removes inactive user states."""
    global browser_state, codebase_state
    while True:
        await asyncio.sleep(RECYCLING_INTERVAL_SECONDS)
        print(f"[{datetime.utcnow()}] Running inactivity check...")
        now = datetime.utcnow()
        threshold_time = now - timedelta(seconds=INACTIVITY_THRESHOLD_SECONDS)

        # Recycle browser states
        inactive_browser_users = []
        for user_id, metadata in browser_state.user_metadata.items():
            if metadata.last_active_timestamp < threshold_time:
                inactive_browser_users.append(user_id)

        if inactive_browser_users:
            print(
                f"[{datetime.utcnow()}] Found inactive browser users: {inactive_browser_users}"
            )
        for user_id in inactive_browser_users:
            print(
                f"[{datetime.utcnow()}] Removing inactive browser context for user: {user_id}"
            )
            remove_result_fr = remove_user_context(browser_state, user_id)
            # remove_user_context is a FutureResult, so we need to await it
            remove_result = await remove_result_fr.awaitable()
            if is_successful(remove_result):
                browser_state = unsafe_perform_io(
                    remove_result.unwrap()
                )  # Update global state
                print(
                    f"[{datetime.utcnow()}] Successfully removed browser context for user: {user_id}"
                )
            else:
                # Log error, but continue trying to recycle others
                print(
                    f"[{datetime.utcnow()}] Error removing browser context for user {user_id}: {remove_result.failure()}"
                )

        # Recycle codebase states
        inactive_codebase_users = []
        for user_id, project in codebase_state.user_projects.items():
            if project.last_active_timestamp < threshold_time:
                inactive_codebase_users.append(user_id)

        if inactive_codebase_users:
            print(
                f"[{datetime.utcnow()}] Found inactive codebase users: {inactive_codebase_users}"
            )
        for user_id in inactive_codebase_users:
            print(
                f"[{datetime.utcnow()}] Removing inactive codebase project for user: {user_id}"
            )
            remove_result = remove_user_project(codebase_state, user_id)
            if is_successful(remove_result):
                codebase_state = unsafe_perform_io(
                    remove_result.unwrap()
                )  # Update global state
                print(
                    f"[{datetime.utcnow()}] Successfully removed codebase project for user: {user_id}"
                )
            else:
                print(
                    f"[{datetime.utcnow()}] Error removing codebase project for user {user_id}: {remove_result.failure()}"
                )

        if not inactive_browser_users and not inactive_codebase_users:
            print(f"[{datetime.utcnow()}] No inactive users found in this cycle.")


@app.on_event("startup")
async def on_startup():
    """Create background task for recycling inactive users."""
    asyncio.create_task(recycle_inactive_users())
    print("User inactivity recycling task started.")


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

    history = await run_context_flow(
        context,
        validated_data.metadata,
        validated_data.prompt,
    )

    return BrowserContextFlowResponse(history=history).model_dump_json()


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
        error_details = add_project_result.failure()
        return {
            "error": f"Failed to add or update user project: {error_details.message}",
            "details": error_details.details,
            "operation": error_details.operation_name.value,
        }, 500  # Internal Server Error or appropriate status

    codebase_state = unsafe_perform_io(
        add_project_result.unwrap()
    )  # Update global state

    # Proceed with the basic code flow
    code = await run_basic_code_flow(
        validated_data.project.project_address, validated_data.prompt
    )
    return CodebaseBasicFlowResponse(code=code).model_dump_json()


if __name__ == "__main__":
    print("Starting Context Flow API on http://0.0.0.0:3050")
    uvicorn.run("api.api_server:app", host="0.0.0.0", port=3050, reload=True)
