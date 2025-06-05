from pydantic import BaseModel
from typing import Optional, Literal, Dict, List


class SSHCredentials(BaseModel):
    host: Optional[str]
    port: Optional[str]
    username: Optional[str]
    password: Optional[str]


class DevboxInfo(BaseModel):
    project_public_address: Optional[str]
    ssh_credentials: SSHCredentials
    template: Literal["nextjs", "uv"]
    token: Optional[str]


class TaskPool(BaseModel):
    """
    A pool to track all ongoing tasks, mapping a token to a list of DevboxInfo (or task IDs).
    """

    pool: Dict[str, List[DevboxInfo]] = {}


class ProjectState(BaseModel):
    """
    A state to track all projects, mapping a project address to a list of DevboxInfo (or task IDs).
    """

    projects: Dict[str, List[DevboxInfo]] = {}
