from pydantic import BaseModel, Field
from typing import Dict, Any, Optional
from enum import Enum
from datetime import datetime


class CodebaseOperation(Enum):
    """Defines operations related to codebase management."""

    ADD_USER_PROJECT = "add_user_project"
    ADD_USER_PROJECT_HEALTH_CHECK_FAILED = "add_user_project_health_check_failed"
    ADD_USER_PROJECT_HTTP_ERROR = "add_user_project_http_error"
    REMOVE_USER_PROJECT = "remove_user_project"
    REMOVE_USER_PROJECT_NOT_FOUND = "remove_user_project_not_found"
    GET_USER_PROJECT = "get_user_project"
    GET_USER_PROJECT_NOT_FOUND = "get_user_project_not_found"
    UPDATE_USER_PROJECT_METADATA = "update_user_project_metadata"
    UPDATE_USER_PROJECT_METADATA_NOT_FOUND = "update_user_project_metadata_not_found"


class CodebaseError(BaseModel):
    """Generic error for codebase provider operations."""

    message: str
    operation_name: CodebaseOperation
    user_id: Optional[str] = None
    project_address: Optional[str] = None
    details: Optional[str] = None

    class Config:
        frozen = True
        arbitrary_types_allowed = True


class UserProject(BaseModel):
    """
    A user's project address.
    """

    project_address: str
    metadata: Optional[Dict[str, Any]] = None
    last_active_timestamp: datetime = Field(default_factory=datetime.utcnow)

    class Config:
        frozen = True
        arbitrary_types_allowed = True


class CodebaseState(BaseModel):
    """
    Manages the state of a codebase.
    """

    user_projects: Dict[str, UserProject] = Field(default_factory=dict)

    class Config:
        frozen = True
        arbitrary_types_allowed = True
