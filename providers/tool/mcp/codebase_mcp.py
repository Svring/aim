from langchain_mcp_adapters.client import MultiServerMCPClient


async def get_codebase_editor_tools(url: str):
    codebase_client = MultiServerMCPClient(
        {
            "codebase_editor": {
                "url": url + "galatea/api/editor/mcp",
                "transport": "streamable_http",
            }
        }
    )

    return await codebase_client.get_tools()


async def get_codebase_project_tools(url: str):
    codebase_client = MultiServerMCPClient(
        {
            "codebase_project": {
                "url": url + "galatea/api/project/mcp",
                "transport": "streamable_http",
            }
        }
    )

    return await codebase_client.get_tools()
