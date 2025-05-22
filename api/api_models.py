from pydantic import BaseModel
from browser_use import AgentHistoryList
from browser_use.browser.context import BrowserContextConfig

from providers.browser.browser_models import UserMetadata
from providers.codebase.codebase_models import UserProject

from typing import Optional


class BrowserContextFlowRequest(BaseModel):
    user_id: str
    context_config: BrowserContextConfig
    metadata: UserMetadata
    prompt: str


class BrowserContextFlowResponse(BaseModel):
    final_result: str


class CodebaseBasicFlowRequest(BaseModel):
    user_id: str
    project: UserProject
    prompt: str


class CodebaseBasicFlowResponse(BaseModel):
    code: str


class MixedFlowRequest(BaseModel):
    user_id: str
    prompt: str
    project: UserProject
    browser_metadata: UserMetadata
    context_config: Optional[BrowserContextConfig] = None
