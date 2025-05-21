import asyncio
from returns.future import future_safe

from browser_use import Agent, AgentHistoryList
from browser_use.browser.context import BrowserContext

from providers.backbone.backbone_provider import get_sealos_model


@future_safe
async def run_full_agent(
    context: BrowserContext, website_url: str, prompt: str
) -> AgentHistoryList:
    agent = Agent(
        task=prompt,
        llm=get_sealos_model("gpt-4o"),
        browser_context=context,
        initial_actions=[{"open_tab": {"url": website_url}}],
    )

    history = await agent.run()

    return history


# if __name__ == "__main__":
#     asyncio.run(run_context_agent())
