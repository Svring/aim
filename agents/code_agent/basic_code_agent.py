from pydantic import BaseModel, Field
from langchain_core.tools import tool

from typing import Optional, Dict, Any
from returns.future import future_safe
import httpx


@future_safe
async def run_basic_code_agent(project_address: str, prompt: str) -> str:
    """Run the code agent by sending a prompt to the invoke-codex endpoint.

    This function relies on the @future_safe decorator to handle exceptions
    (like httpx.HTTPStatusError or httpx.RequestError) and wrap them in a Failure.
    """
    invoke_url = f"{project_address}/galatea/invoke-codex"
    payload = {"prompt": prompt}

    async with httpx.AsyncClient() as client:
        response = await client.post(
            invoke_url, json=payload, timeout=60.0
        )  # 60-second timeout
        response.raise_for_status()  # Let httpx raise for bad status, future_safe will catch it
        # Assuming the endpoint returns a JSON response with a string field,
        # or just a plain text response. For now, let's assume plain text.
        # If it's JSON like {"response": "..."}, you might do: return response.json()["response"]
        return response.content
