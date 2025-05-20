from returns.unsafe import unsafe_perform_io

from agents.code_agent.basic_code_agent import run_basic_code_agent


async def run_basic_code_flow(project_address: str, prompt: str):
    """Run the basic code flow."""
    code_result = await run_basic_code_agent(project_address, prompt)
    code = unsafe_perform_io(code_result.unwrap())
    return code
