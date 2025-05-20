import asyncio
from typing import Optional
from datetime import datetime

from returns.result import Result, Success, Failure
from returns.maybe import Maybe
from returns.pipeline import is_successful
from returns.converters import maybe_to_result
from returns.future import FutureResult, future_safe
from returns.unsafe import unsafe_perform_io

# Assuming these are the correct import paths for the browser_use library components
from browser_use import Browser, BrowserConfig
from browser_use.browser.context import BrowserContext, BrowserContextConfig

from .browser_models import BrowserState, UserMetadata, BrowserError, BrowserOperation


# Factory function for BrowserError
def _make_browser_error(
    message: str,
    operation_name: BrowserOperation,
    user_id: Optional[str] = None,
    details: Optional[str] = None,
) -> BrowserError:
    """Factory for creating BrowserError instances with consistent structure."""
    return BrowserError(
        message=message,
        operation_name=operation_name,
        user_id=user_id,
        details=details,
    )


# Provider functions


@future_safe
async def _create_browser_context(
    browser_instance: Browser, config: BrowserContextConfig
) -> BrowserContext:
    return await browser_instance.new_context(config=config)


@future_safe
async def _close_browser_context(context: BrowserContext) -> None:
    await context.close()


@future_safe
async def _close_browser(browser_instance: Browser) -> str:
    await browser_instance.close()
    return "Browser closed successfully"


# Public API Functions


def create_browser_state(
    browser_config: BrowserConfig,
) -> BrowserState:
    browser_instance = Browser(browser_config)
    return BrowserState(browser_instance=browser_instance)


def add_user_context_and_metadata(
    current_state: BrowserState,
    user_id: str,
    context_config: BrowserContextConfig,
    user_meta: UserMetadata,
) -> FutureResult[BrowserState, BrowserError]:
    now = datetime.utcnow()

    if user_id in current_state.user_contexts:
        # User context exists. We will only update the timestamp of their metadata.
        # The existing BrowserContext and its config are preserved.
        # The new user_meta.website_url will replace old if different, and timestamp updated.

        existing_meta = current_state.user_metadata.get(user_id)
        # Create new metadata with potentially updated URL from request, and fresh timestamp
        # Note: user_meta from input is a complete UserMetadata object, which already has a factory-generated timestamp.
        # We want to ensure the one we store has *this* invocation's timestamp.
        updated_user_meta_for_existing_user = UserMetadata(
            website_url=user_meta.website_url,  # Use URL from the request
            last_active_timestamp=now,
        )

        if existing_meta and existing_meta == updated_user_meta_for_existing_user:
            # If all details including timestamp are somehow identical, no need to update state.
            # This is unlikely given timestamp precision but a safe check.
            return FutureResult.from_result(Success(current_state))

        updated_metadata_dict = {
            **current_state.user_metadata,
            user_id: updated_user_meta_for_existing_user,
        }
        new_state_only_meta_update = current_state.model_copy(
            update={"user_metadata": updated_metadata_dict}
        )
        return FutureResult.from_result(Success(new_state_only_meta_update))

    # User context does not exist, create new context and new metadata
    # Ensure the user_meta to be stored has the correct `now` timestamp
    user_meta_with_current_timestamp = user_meta.model_copy(
        update={"last_active_timestamp": now}
    )

    return (
        _create_browser_context(current_state.browser_instance, context_config)
        .map(
            lambda new_context: current_state.model_copy(
                update={
                    "user_contexts": {
                        **current_state.user_contexts,
                        user_id: new_context,
                    },
                    "user_metadata": {
                        **current_state.user_metadata,
                        user_id: user_meta_with_current_timestamp,  # Use the one with correct timestamp
                    },
                }
            )
        )
        .lash(
            lambda err: Failure(
                _make_browser_error(
                    message=f"Failed to add user context for '{user_id}'.",
                    user_id=user_id,
                    operation_name=BrowserOperation.ADD_USER_CONTEXT_FAILED,
                    details=str(err),
                )
            )
        )
    )


# These functions do not perform async I/O, they operate on state. They return Result.
def get_user_context(
    state: BrowserState, user_id: str
) -> Result[BrowserContext, BrowserError]:
    maybe_context = Maybe.from_optional(state.user_contexts.get(user_id))
    return maybe_to_result(
        maybe_context,
        _make_browser_error(
            message=f"User context for '{user_id}' not found.",
            user_id=user_id,
            operation_name=BrowserOperation.GET_USER_CONTEXT_NOT_FOUND,
        ),
    )


def get_user_metadata(
    state: BrowserState, user_id: str
) -> Result[UserMetadata, BrowserError]:
    maybe_metadata = Maybe.from_optional(state.user_metadata.get(user_id))
    return maybe_to_result(
        maybe_metadata,
        _make_browser_error(
            message=f"User metadata for '{user_id}' not found.",
            user_id=user_id,
            operation_name=BrowserOperation.GET_USER_METADATA_NOT_FOUND,
        ),
    )


def remove_user_context(
    current_state: BrowserState, user_id: str
) -> FutureResult[BrowserState, BrowserError]:
    # Get the context and handle errors in one step
    context_result = get_user_context(current_state, user_id)

    # If context not found, return early with appropriate error
    if not is_successful(context_result):
        return FutureResult.from_result(
            Failure(
                context_result.failure().model_copy(
                    update={
                        "operation_name": BrowserOperation.REMOVE_USER_CONTEXT_NOT_FOUND
                    }
                )
            )
        )

    context_to_remove = context_result.unwrap()

    return (
        _close_browser_context(context_to_remove)
        .map(
            lambda _unused_none_after_io: current_state.model_copy(
                update={
                    "user_contexts": {
                        k: v
                        for k, v in current_state.user_contexts.items()
                        if k != user_id
                    },
                    "user_metadata": {
                        k: v
                        for k, v in current_state.user_metadata.items()
                        if k != user_id
                    },
                }
            )
        )
        .lash(
            lambda err: Failure(
                _make_browser_error(
                    message=f"Failed to remove user context for '{user_id}'.",
                    user_id=user_id,
                    operation_name=BrowserOperation.REMOVE_USER_CONTEXT_FAILED,
                    details=str(err),
                )
            )
        )
    )


# Synchronous state update, returns Result
def update_user_metadata(
    current_state: BrowserState,
    user_id: str,
    new_meta: UserMetadata,
) -> Result[BrowserState, BrowserError]:
    if user_id not in current_state.user_metadata:
        return Failure(
            _make_browser_error(
                message=f"User '{user_id}' not found for metadata update.",
                user_id=user_id,
                operation_name=BrowserOperation.UPDATE_USER_METADATA_NOT_FOUND,
            )
        )
    updated_metadata = {**current_state.user_metadata, user_id: new_meta}
    return Success(current_state.model_copy(update={"user_metadata": updated_metadata}))


def shutdown_browser(
    state: BrowserState,
) -> FutureResult[str, BrowserError]:
    return _close_browser(state.browser_instance).lash(
        lambda err: Failure(
            _make_browser_error(
                message=f"Failed to close browser.",
                operation_name=BrowserOperation.SHUTDOWN_BROWSER,
                details=str(err),
            )
        )
    )


# python -m providers.browser.browser_provider
async def main_example():
    from unittest.mock import MagicMock

    print(
        "--- Browser Provider Example (Live Operations with FutureResult and IO handling) ---"
    )

    mock_browser_config = MagicMock(spec=BrowserConfig)
    mock_browser_config.headless = True
    mock_browser_config.browser_class = "chromium"
    mock_browser_config.keep_alive = False

    mock_context_config_user1 = MagicMock(spec=BrowserContextConfig)
    mock_context_config_user1.user_agent = "TestAgent/1.0"
    mock_context_config_user1.allowed_domains = ["example.com"]

    mock_user_meta_user1 = UserMetadata(website_url="https://example.com")

    print("\nStep 1: Initialize browser state")
    # Provider functions now return FutureResult, so we await them.
    initial_state: BrowserState = create_browser_state(mock_browser_config)

    if isinstance(initial_state, BrowserState):
        print("\nStep 2: Add user context and metadata")
        state_after_add_result = await add_user_context_and_metadata(
            initial_state, "user123", mock_context_config_user1, mock_user_meta_user1
        )
        if is_successful(state_after_add_result):
            print(f"Add User Context Success: {state_after_add_result.unwrap()}")
            state_after_add = state_after_add_result.unwrap()
        else:
            print(f"Add User Context Failure: {state_after_add_result.failure()}")
            state_after_add = state_after_add_result

        state_after_add = unsafe_perform_io(state_after_add)

        if isinstance(state_after_add, BrowserState):
            print(
                f"State after adding user123: {len(state_after_add.user_contexts)} context(s)"
            )
            print("\nStep 3: Get user context (sync)")
            context_result = get_user_context(state_after_add, "user123")
            if is_successful(context_result):
                print(f"Get User Context Success: {context_result.unwrap()}")
            else:
                print(f"Get User Context Failure: {context_result.failure()}")

            print("\nStep 4: Remove user context")
            state_after_remove_result = await remove_user_context(
                state_after_add, "user123"
            )
            state_after_remove_result = state_after_remove_result.unwrap()
            state_after_remove = unsafe_perform_io(state_after_remove_result)
            if isinstance(state_after_remove, BrowserState):
                print(f"Remove User Context Success: {state_after_remove}")
                print(
                    f"State after removing user123: {len(state_after_remove.user_contexts)} context(s)"
                )
            else:
                print(f"Remove User Context Failure")

            state_for_shutdown = state_after_add
            if isinstance(state_after_remove, BrowserState):
                state_for_shutdown = state_after_remove
        else:
            state_for_shutdown = initial_state
            print(f"Skipping some steps due to failure in adding user context.")

        print("\nStep 5: Shutdown browser")
        if isinstance(state_for_shutdown, BrowserState):
            shutdown_result = await shutdown_browser(state_for_shutdown)
            if is_successful(shutdown_result):
                print(f"Shutdown Success: {shutdown_result.unwrap()}")
            else:
                print(f"Shutdown Failure: {shutdown_result.failure()}")
        else:
            print("Skipping shutdown as no valid browser state available.")

    print("\n--- Example End ---")


if __name__ == "__main__":
    asyncio.run(main_example())
