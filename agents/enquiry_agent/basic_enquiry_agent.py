# python -m agents.enquiry_agent.basic_enquiry_agent

from langchain_core.messages import (
    HumanMessage,
    SystemMessage,
)

from providers.backbone.backbone_provider import get_sealos_model
from providers.backbone.backbone_provider import build_enquiry_agent_prompt
from providers.tool.function.enquiry_tools import (
    ask_follow_up_question,
    generate_task_plan,
)


async def run_basic_enquiry_agent(prompt: str):
    llm = get_sealos_model("claude-sonnet-4-20250514")
    tools = {
        "ask_follow_up_question": ask_follow_up_question,
        "generate_task_plan": generate_task_plan,
    }
    llm_with_tools = llm.bind_tools(list(tools.values()))

    messages = [
        SystemMessage(content=build_enquiry_agent_prompt("")),
        HumanMessage(content=prompt),
    ]

    while True:
        response = llm_with_tools.invoke(messages)
        messages.append(response)

        print(response.content)

        tool_call = response.tool_calls[0]
        tool_msg = tools[tool_call["name"]].invoke(tool_call)
        messages.append(tool_msg)

        if tool_call["name"] == "generate_task_plan":
            print(tool_msg)
            # tool_msg.content is a JSON string
            import json

            content = getattr(tool_msg, "content", None)
            if content:
                try:
                    result = json.loads(content)
                    if result.get("status") == "success":
                        return result.get("file_path")
                    else:
                        print(f"Error: {result.get('error')}")
                        return None
                except Exception as e:
                    print(f"Error parsing tool_msg content: {e}")
                    return None
            else:
                return None


if __name__ == "__main__":
    import asyncio

    async def test_run_basic_enquiry_agent():
        prompt = (
            "AI Prompt Library, do not ask me questions, just generate the task plan"
        )
        result = await run_basic_enquiry_agent(prompt)
        print(result)

    asyncio.run(test_run_basic_enquiry_agent())

# tool_calls_chunks = []
# for chunk in llm_with_tools.stream(messages):
#     if chunk.additional_kwargs.get("tool_calls"):
#         tool_calls_chunks.append(chunk.additional_kwargs.get("tool_calls"))
#     else:
#         print(chunk.content, end="", flush=True)

# print(accumulate_tool_call_chunks(tool_calls_chunks))

# def accumulate_tool_call_chunks(chunks):
#     """
#     Given a list of tool call chunks (as printed from chunk.additional_kwargs.get("tool_calls")),
#     accumulate the arguments and return the final tool call dict.
#     """
#     tool_call = None
#     args_buffer = ""
#     for chunk in chunks:
#         if not chunk or not isinstance(chunk, list) or not chunk[0]:
#             continue
#         call = chunk[0]
#         # If this is the first chunk, initialize the tool_call dict
#         if tool_call is None:
#             tool_call = {k: v for k, v in call.items() if k != "function"}
#             tool_call["function"] = {
#                 k: v for k, v in call["function"].items() if k != "arguments"
#             }
#             args_buffer = ""
#         # Accumulate arguments, safely handling None
#         args_buffer += call["function"].get("arguments") or ""
#     if tool_call is not None:
#         tool_call["function"]["arguments"] = args_buffer
#     return tool_call
