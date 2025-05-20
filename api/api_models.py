from pydantic import BaseModel
from browser_use import AgentHistoryList
from browser_use.browser.context import BrowserContextConfig

from providers.browser.browser_models import UserMetadata
from providers.codebase.codebase_models import UserProject


class BrowserContextFlowRequest(BaseModel):
    user_id: str
    context_config: BrowserContextConfig
    metadata: UserMetadata
    prompt: str


class BrowserContextFlowResponse(BaseModel):
    history: AgentHistoryList


class CodebaseBasicFlowRequest(BaseModel):
    user_id: str
    project: UserProject
    prompt: str


class CodebaseBasicFlowResponse(BaseModel):
    code: str
