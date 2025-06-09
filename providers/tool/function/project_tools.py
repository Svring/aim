from langchain_core.tools import tool
from pydantic import BaseModel, Field
import os
import json
from typing import List, Optional, Union


class ProjectFile(BaseModel):
    path: str = Field(description="File or directory path")
    usage: str = Field(description="Description of the file or directory usage")
    children: Optional[Union[List[Union[str, "ProjectFile"]], List[str]]] = Field(
        default=None,
        description="List of child files/directories or file names (for directories)",
    )

    class Config:
        arbitrary_types_allowed = True


ProjectFile.update_forward_refs()


class ProjectStructure(BaseModel):
    project: List[ProjectFile] = Field(
        description="List of top-level files and directories in the project"
    )


@tool
def generate_project_structure(structure: ProjectStructure) -> dict:
    """
    Generate and save a project structure as a JSON file based on the provided structure.

    Args:
        structure: A ProjectStructure object containing the project structure details.

    Returns:
        A dict containing status, project_name, and file_path (or error message).
    """
    # Convert the structure to JSON
    structure_json = structure.model_dump_json(indent=2)

    # Use the first file/dir as the project name for the filename
    if not structure.project or not hasattr(structure.project[0], "path"):
        return {
            "status": "error",
            "error": "No top-level project file or directory provided",
        }
    project_name = os.path.splitext(os.path.basename(structure.project[0].path))[0]
    base_dir = "archive/project_structure"
    base_name = project_name.lower().replace(" ", "_")
    file_path = os.path.join(base_dir, f"{base_name}_structure.json")
    # Collision avoidance
    if not os.path.exists(base_dir):
        os.makedirs(base_dir, exist_ok=True)
    suffix = 1
    while os.path.exists(file_path):
        file_path = os.path.join(base_dir, f"{base_name}_structure_{suffix}.json")
        suffix += 1
    try:
        with open(file_path, "w") as f:
            f.write(structure_json)
        return {
            "status": "success",
            "project_name": project_name,
            "file_path": file_path,
        }
    except Exception as e:
        return {"status": "error", "project_name": project_name, "error": str(e)}
