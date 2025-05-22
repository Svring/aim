from workflows.codebase_workflows.full_code_flow import (
    run_full_code_flow,
    FullCodeFlowResponse,
)
from workflows.browser_workflows.full_browser_flow import (
    run_full_browser_flow,
    FullBrowserFlowResponse,
)
from providers.backbone.backbone_provider import get_sealos_model
from providers.browser.browser_models import UserMetadata
from providers.codebase.codebase_models import UserProject
from browser_use.browser.context import BrowserContext


async def run_mixed_flow(
    prompt: str,
    context: BrowserContext,
    metadata: UserMetadata,
    project: UserProject,
):
    print("[mixed_flow] running mixed flow")

    llm = get_sealos_model("gpt-4o")

    code_flow_result: FullCodeFlowResponse = await run_full_code_flow(
        project.project_address, prompt
    )

    browser_flow_result: FullBrowserFlowResponse = await run_full_browser_flow(
        context, metadata, prompt
    )

    return code_flow_result, browser_flow_result
