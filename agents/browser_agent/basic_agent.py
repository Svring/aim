import asyncio
from browser_use import Agent

from providers.backbone.backbone_provider import get_sealos_model


async def run_basic_agent():
    agent = Agent(
        task="Compare the price of gpt-4o and DeepSeek-V3",
        llm=get_sealos_model("gpt-4o"),
    )

    await agent.run()


if __name__ == "__main__":
    asyncio.run(run_basic_agent())
