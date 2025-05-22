from returns.unsafe import unsafe_perform_io

from agents.codebase_agent.basic_code_agent import run_basic_code_agent

from pydantic import BaseModel
from typing import List


class FullCodeFlowResponse(BaseModel):
    final_result: str
    modified_files: List[str]


async def run_full_code_flow(public_address: str, prompt: str):
    """Run the full code flow."""
    code_result = await run_basic_code_agent(public_address, prompt)
    code = unsafe_perform_io(code_result.unwrap())
    # this return value is of no use
    return FullCodeFlowResponse(
        final_result=code,
        modified_files=["file1.py", "file2.py"],
    )
