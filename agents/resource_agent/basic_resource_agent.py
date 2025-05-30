# python -m agents.resource_agent.basic_resource_agent
from langchain_mcp_adapters.client import MultiServerMCPClient
from langgraph.prebuilt import create_react_agent
from langchain_core.messages import HumanMessage

from providers.backbone.backbone_provider import get_sealos_model


async def main():
    client = MultiServerMCPClient(
        {
            "algebra": {
                "command": "python",
                "args": ["/Users/linkling/Code/aim/providers/tool/mcp/algebra_mcp.py"],
                "transport": "stdio",
            }
        }
    )

    tools = await client.get_tools()

    agent = create_react_agent(
        model=get_sealos_model("gpt-4o-mini"),
        tools=tools,
    )

    async for chunk in agent.astream(
        {
            "messages": [
                HumanMessage("what's (3 + 5) x 12? Please use the tools provided.")
            ]
        },
        stream_mode="updates",
    ):
        print(chunk)


if __name__ == "__main__":
    import asyncio

    asyncio.run(main())
