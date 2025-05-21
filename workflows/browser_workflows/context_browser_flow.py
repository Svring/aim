from returns.unsafe import unsafe_perform_io
from browser_use.browser.context import BrowserContext

from providers.browser.browser_models import UserMetadata
from agents.browser_agent.context_browser_agent import run_context_agent


async def run_context_flow(
    context: BrowserContext,
    metadata: UserMetadata,
    prompt: str,
):
    print("[context_flow] running context flow")
    history_result = await run_context_agent(context, metadata.website_url, prompt)
    history = unsafe_perform_io(history_result.unwrap())
    print("[context_flow] resulted history", history)
    return history
