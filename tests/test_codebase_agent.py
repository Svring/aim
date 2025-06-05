import pytest
from agents.codebase_agent.codebase_agent import (
    make_config,
    make_codebase_state,
    run_codebase_agent,
)
from langchain_core.messages import HumanMessage


def test_run_codebase_agent_dummy():
    # Dummy config values
    thread_id = "test_thread"
    user_id = "test_user"
    token = "test_token"
    project_address = "0xtest"
    # Dummy state values
    project_structure = {"root": ["file1.py", "file2.py"]}
    task_plan = ["Task 1", "Task 2"]

    config = make_config(thread_id, user_id, token, project_address)
    state = make_codebase_state(project_structure, task_plan)

    # The function should not raise and should invoke the agent
    try:
        run_codebase_agent(config, state)
    except Exception as e:
        pytest.fail(f"run_codebase_agent raised an exception: {e}")
