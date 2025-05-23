from pydantic import BaseModel
from browser_use import AgentHistoryList
from browser_use.browser.context import BrowserContextConfig

from providers.browser.browser_models import UserMetadata
from providers.codebase.codebase_models import UserProject

from typing import Optional, List, Any


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


class BrowserFullFlowRequest(BaseModel):
    user_id: str
    prompt: str
    url: str | None = None


class BrowserFullFlowResponse(BaseModel):
    final_result: str | None
    urls: List[str | None]
    screenshot_urls: List[str | None]
    model_actions: List[Any]


class CodebaseFullFlowRequest(BaseModel):
    user_id: str
    prompt: str
    url: str | None = None


class CodebaseFullFlowResponse(BaseModel):
    final_result: str | None
    modified_files: List[str | None]
