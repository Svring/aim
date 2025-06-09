# python -m api.v0.server
from fastapi import FastAPI, HTTPException, Header
from typing import Optional
from agents.chat_agent.basic_chat_agent import chat_turn
from providers.resource.account.account_provider import (
    get_account_amount,
    get_auth_info,
)
from providers.resource.devbox.devbox_provider import (
    get_devbox_list,
    get_devbox_by_name,
    get_ssh_connection_info,
    generate_networks_for_devbox,
)
from .model import (
    ChatAgentRequest,
    ChatAgentResponse,
    AccountAmountRequest,
    AuthInfoRequest,
    AccountResponse,
    DevboxListRequest,
    DevboxByNameRequest,
    SSHConnectionInfoRequest,
    GenerateNetworksRequest,
    DevboxResponse,
    DevboxListResponse,
    NetworksResponse,
)

app = FastAPI()


@app.post("/v0/agent/chat", response_model=ChatAgentResponse)
def chat_agent_endpoint(request: ChatAgentRequest):
    response = chat_turn(request.prompt, request.user_id)
    return ChatAgentResponse(response=response)


# Account namespace endpoints
@app.post("/v0/account/amount", response_model=AccountResponse)
def get_account_amount_endpoint(
    request: AccountAmountRequest,
    authorization: str = Header(..., description="Region token"),
):
    try:
        data = get_account_amount(request.region_url, authorization)
        return AccountResponse(data=data)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/v0/account/auth-info", response_model=AccountResponse)
def get_auth_info_endpoint(
    request: AuthInfoRequest,
    authorization: str = Header(..., description="Region token"),
):
    try:
        data = get_auth_info(request.region_url, authorization)
        return AccountResponse(data=data)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# Devbox namespace endpoints
@app.post("/v0/devbox/list", response_model=DevboxListResponse)
def get_devbox_list_endpoint(
    request: DevboxListRequest,
    authorization: str = Header(..., description="Kubeconfig token"),
    authorization_bearer: str = Header(
        ..., alias="Authorization-Bearer", description="Devbox token"
    ),
):
    try:
        data = get_devbox_list(request.region_url, authorization, authorization_bearer)
        return DevboxListResponse(data=data)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/v0/devbox/by-name", response_model=DevboxResponse)
def get_devbox_by_name_endpoint(
    request: DevboxByNameRequest,
    authorization: str = Header(..., description="Kubeconfig token"),
    authorization_bearer: str = Header(
        ..., alias="Authorization-Bearer", description="Devbox token"
    ),
):
    try:
        data = get_devbox_by_name(
            request.region_url,
            request.devbox_name,
            request.mock,
            authorization,
            authorization_bearer,
        )
        return DevboxResponse(data=data)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/v0/devbox/ssh-connection-info", response_model=DevboxResponse)
def get_ssh_connection_info_endpoint(
    request: SSHConnectionInfoRequest,
    authorization: str = Header(..., description="Kubeconfig token"),
    authorization_bearer: str = Header(
        ..., alias="Authorization-Bearer", description="Devbox token"
    ),
):
    try:
        data = get_ssh_connection_info(
            request.region_url,
            request.devbox_name,
            authorization,
            authorization_bearer,
        )
        return DevboxResponse(data=data)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/v0/devbox/generate-networks", response_model=NetworksResponse)
def generate_networks_endpoint(request: GenerateNetworksRequest):
    try:
        networks = generate_networks_for_devbox(
            request.devbox_name,
            request.template_config,
            request.ingress_domain,
        )
        return NetworksResponse(networks=networks)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    import uvicorn

    print("Starting Chat Agent API on http://0.0.0.0:3050")
    uvicorn.run("api.v0.server:app", host="0.0.0.0", port=3050, reload=True)
