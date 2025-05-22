from returns.unsafe import unsafe_perform_io
from browser_use.browser.context import BrowserContext

from providers.browser.browser_models import UserMetadata
from agents.browser_agent.full_browser_agent import run_full_browser_agent

from pydantic import BaseModel
from typing import List


class FullBrowserFlowResponse(BaseModel):
    final_result: str
    urls: List[str]
    screenshot_urls: List[str]
    model_actions: List[str]


async def run_full_browser_flow(
    context: BrowserContext,
    metadata: UserMetadata,
    prompt: str,
):
    print("[full_browser_flow] running full browser flow")
    history_result = await run_full_browser_agent(context, metadata.website_url, prompt)
    history = unsafe_perform_io(history_result.unwrap())
    print("[full_browser_flow] resulted history", history)

    final_result = history.final_result()
    urls = history.urls()
    screenshot_urls = history.screenshots()
    model_actions = history.model_actions()

    return FullBrowserFlowResponse(
        final_result=final_result,
        urls=urls,
        screenshot_urls=screenshot_urls,
        model_actions=model_actions,
    )
