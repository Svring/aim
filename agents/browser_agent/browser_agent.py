import asyncio
from returns.future import future_safe

from browser_use import Agent, AgentHistoryList
from browser_use.browser.context import BrowserContext

from providers.backbone.backbone_provider import get_sealos_model
from providers.browser.browser_models import default_browser_context_config


@future_safe
async def run_browser_agent(prompt: str) -> AgentHistoryList:
    browser_context = BrowserContext(config=default_browser_context_config)

    agent = Agent(
        task=prompt,
        llm=get_sealos_model("claude-sonnet-4-20250514"),
        browser_context=browser_context,
    )

    history = await agent.run()

    return history


# if __name__ == "__main__":
#     asyncio.run(run_context_agent())
