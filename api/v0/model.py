from pydantic import BaseModel
from typing import Optional, Dict, List, Any, Union


class ChatAgentRequest(BaseModel):
    user_id: str
    prompt: str


class ChatAgentResponse(BaseModel):
    response: str


# Account endpoint models
class AccountAmountRequest(BaseModel):
    region_url: str


class AuthInfoRequest(BaseModel):
    region_url: str


class AccountResponse(BaseModel):
    data: Dict


# Devbox endpoint models
class DevboxListRequest(BaseModel):
    region_url: str


class DevboxByNameRequest(BaseModel):
    region_url: str
    devbox_name: str
    mock: bool


class SSHConnectionInfoRequest(BaseModel):
    region_url: str
    devbox_name: str


class GenerateNetworksRequest(BaseModel):
    devbox_name: str
    template_config: str
    ingress_domain: Optional[str] = None


class DevboxResponse(BaseModel):
    data: Dict


class DevboxListResponse(BaseModel):
    data: Any  # Can be either a list or dict depending on API response


class NetworksResponse(BaseModel):
    networks: List[Dict]
