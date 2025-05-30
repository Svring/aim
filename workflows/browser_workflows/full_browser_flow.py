from returns.unsafe import unsafe_perform_io
from browser_use.browser.context import BrowserContext

from providers.browser.browser_models import UserMetadata
from agents.browser_agent.full_browser_agent import run_full_browser_agent

from pydantic import BaseModel
from typing import List, Any


class FullBrowserFlowResponse(BaseModel):
    final_result: str
    urls: List[str]
    screenshot_urls: List[str | None]
    model_actions: List[Any]


def _serialize_action(action):
    # Recursively convert any Pydantic models to dicts
    if hasattr(action, "model_dump"):
        return action.model_dump()
    elif isinstance(action, dict):
        return {k: _serialize_action(v) for k, v in action.items()}
    elif isinstance(action, list):
        return [_serialize_action(i) for i in action]
    else:
        return action


async def run_full_browser_flow(
    context: BrowserContext,
    url: str,
    prompt: str,
):
    print("[full_browser_flow] running full browser flow")
    history_result = await run_full_browser_agent(context, url, prompt)
    history = unsafe_perform_io(history_result.unwrap())
    print("[full_browser_flow] resulted history", history)

    final_result = history.final_result()
    urls = history.urls()
    screenshot_urls = history.screenshots()
    model_actions = [_serialize_action(a) for a in history.model_actions()]

    return FullBrowserFlowResponse(
        final_result=final_result,
        urls=urls,
        screenshot_urls=[None],
        model_actions=model_actions,
    )
