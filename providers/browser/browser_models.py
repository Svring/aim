from typing import Optional, Dict
from pydantic import BaseModel, Field
from enum import Enum
from datetime import datetime, timezone

from browser_use import BrowserConfig, Browser
from browser_use.browser.context import BrowserContextConfig, BrowserContext

default_browser_context_config = BrowserContextConfig(
    window_width=1920,
    window_height=1080,
    locale="en-US",
    user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    allowed_domains=[],
    maximum_wait_page_load_time=10,
    highlight_elements=True,
    keep_alive=True,
)


class UserMetadata(BaseModel):
    """
    Metadata for a user.
    """

    website_url: str
    last_active_timestamp: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )

    class Config:
        frozen = True
        arbitrary_types_allowed = True


class BrowserState(BaseModel):
    """
    Manages the state of a single browser instance and multiple user-specific browser contexts.
    """

    browser_instance: Browser
    user_contexts: Dict[str, BrowserContext] = Field(default_factory=dict)
    user_metadata: Dict[str, UserMetadata] = Field(default_factory=dict)

    class Config:
        frozen = True
        arbitrary_types_allowed = (
            True  # Necessary for custom types like Browser and BrowserContext
        )


class BrowserOperation(Enum):
    CREATE_BROWSER = "create_browser"
    CREATE_BROWSER_CONTEXT = "create_browser_context"
    CLOSE_BROWSER_CONTEXT = "close_browser_context"
    ADD_USER_CONTEXT_EXISTS = "add_user_context_exists"
    GET_USER_CONTEXT_NOT_FOUND = "get_user_context_not_found"
    GET_USER_METADATA_NOT_FOUND = "get_user_metadata_not_found"
    REMOVE_USER_CONTEXT_NOT_FOUND = "remove_user_context_not_found"
    UPDATE_USER_METADATA_NOT_FOUND = "update_user_metadata_not_found"
    CLOSE_MAIN_BROWSER = "close_main_browser"
    SHUTDOWN_BROWSER = "shutdown_browser"
    ADD_USER_CONTEXT_FAILED = "add_user_context_failed"
    REMOVE_USER_CONTEXT_FAILED = "remove_user_context_failed"


class BrowserError(BaseModel):
    """Generic error for browser provider operations."""

    message: str
    operation_name: BrowserOperation
    user_id: Optional[str] = None
    details: Optional[str] = None

    class Config:
        frozen = True
        arbitrary_types_allowed = True


if __name__ == "__main__":
    """
    test command: python -m providers.browser.browser_models
    """
    from unittest.mock import MagicMock

    # Example BrowserConfig (remains the same)
    browser_config = BrowserConfig(
        headless=True,
        keep_alive=True,
        browser_class="chromium",
    )

    # Example BrowserContextConfig (remains the same)
    browser_context_config_user1 = BrowserContextConfig(
        window_width=1920,
        window_height=1080,
        locale="en-US",
        user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
        allowed_domains=["google.com", "bing.com", "duckduckgo.com"],
        maximum_wait_page_load_time=10,
        highlight_elements=True,
        keep_alive=True,
        save_recording_path="recordings/user1",
    )

    browser_context_config_user2 = BrowserContextConfig(
        window_width=1280,
        window_height=720,
        locale="de-DE",
        user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
        allowed_domains=["wikipedia.org"],
        maximum_wait_page_load_time=15,
        highlight_elements=False,
        keep_alive=False,
        save_recording_path="recordings/user2",
    )

    # Mock Browser and BrowserContext instances
    mock_browser_instance = MagicMock(spec=Browser)
    mock_browser_instance.config = browser_config

    mock_context_instance_user1 = MagicMock(spec=BrowserContext)
    mock_context_instance_user1.config = browser_context_config_user1

    mock_context_instance_user2 = MagicMock(spec=BrowserContext)
    mock_context_instance_user2.config = browser_context_config_user2

    # Create UserMetadata instances
    user_metadata_user1 = UserMetadata(website_url="https://www.google.com")
    user_metadata_user2 = UserMetadata(website_url="https://www.wikipedia.org")

    # Create BrowserState with mocked instances and user metadata
    browser_state_example = BrowserState(
        browser_instance=mock_browser_instance,
        user_contexts={
            "user123": mock_context_instance_user1,
            "user456": mock_context_instance_user2,
        },
        user_metadata={
            "user123": user_metadata_user1,
            "user456": user_metadata_user2,
        },
    )

    print("--- Example BrowserState ---")
    print(browser_state_example)
    print("\\n--- Browser Instance (Mocked) ---")
    print(f"Type: {type(browser_state_example.browser_instance)}")
    print(f"Associated Config: {browser_state_example.browser_instance.config}")

    print("\\n--- User Contexts (Mocked) ---")
    for user_id, context in browser_state_example.user_contexts.items():
        print(f"  User ID: {user_id}")
        print(
            f"  Context Config: {context.config}"
        )  # Assuming config is attached to mock

    print("\\n--- User Metadata ---")
    for user_id, metadata in browser_state_example.user_metadata.items():
        print(f"  User ID: {user_id}")
        print(f"  Metadata: {metadata}")
