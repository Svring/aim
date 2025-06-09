# python -m agents.browser_agent.browser_agent
import asyncio
import json
import os
import base64
from datetime import datetime
from typing import Optional, Dict, Any

from browser_use import Agent, AgentHistoryList
from browser_use import BrowserSession, BrowserProfile

from providers.backbone.backbone_provider import get_sealos_model


def obj_to_json_safe(obj, check_circular=False):
    """Safely convert object to JSON, handling non-serializable objects"""
    try:
        if hasattr(obj, "model_dump"):
            return obj.model_dump()
        elif hasattr(obj, "__dict__"):
            return {k: str(v) for k, v in obj.__dict__.items()}
        else:
            return str(obj)
    except Exception as e:
        return f"Serialization error: {str(e)}"


def save_agent_history_step(
    data: Dict[str, Any],
    session_id: Optional[str] = None,
    run_dir: Optional[str] = None,
):
    """Save the agent step data to a local JSON file in the run's folder"""
    if session_id is None:
        session_id = datetime.now().strftime("%Y%m%d_%H%M%S")
    if run_dir is None:
        logs_dir = "logs/browser_activity"
    else:
        logs_dir = f"{run_dir}/browser_activity"
    os.makedirs(logs_dir, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")[:-3]  # milliseconds
    filename = f"{logs_dir}/step_{session_id}_{timestamp}.json"
    try:
        with open(filename, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False, default=str)
        print(f"✅ Saved step data to: {filename}")
        return {"status": "success", "file": filename}
    except Exception as e:
        print(f"❌ Error saving step data: {e}")
        return {"status": "error", "error": str(e)}


def save_session_summary(
    session_data: Dict[str, Any], session_id: str, run_dir: Optional[str] = None
):
    """Save a summary of the entire browser session in the run's folder"""
    if run_dir is None:
        logs_dir = "logs/browser_activity"
    else:
        logs_dir = f"{run_dir}/browser_activity"
    os.makedirs(logs_dir, exist_ok=True)
    filename = f"{logs_dir}/session_summary_{session_id}.json"
    try:
        with open(filename, "w", encoding="utf-8") as f:
            json.dump(session_data, f, indent=2, ensure_ascii=False, default=str)
        print(f"✅ Saved session summary to: {filename}")
        return {"status": "success", "file": filename}
    except Exception as e:
        print(f"❌ Error saving session summary: {e}")
        return {"status": "error", "error": str(e)}


async def record_browser_activity(
    agent_obj, session_id: Optional[str] = None, run_dir: Optional[str] = None
):
    """Hook function that captures and records agent activity at each step"""
    website_screenshot = None
    screenshot_path = None
    urls_json_last_elem = None
    model_thoughts_last_elem = None
    model_outputs_json_last_elem = None
    model_actions_json_last_elem = None
    extracted_content_json_last_elem = None

    print("--- RECORDING BROWSER STEP ---")

    try:
        # Capture current page state (removed website_html)
        website_screenshot = await agent_obj.browser_session.take_screenshot()
        # Save screenshot as independent image
        if run_dir is not None:
            os.makedirs(f"{run_dir}/images", exist_ok=True)
            screenshot_filename = f"{run_dir}/images/screenshot_{session_id}_{datetime.now().strftime('%Y%m%d_%H%M%S_%f')}.png"
        else:
            os.makedirs("logs/images", exist_ok=True)
            screenshot_filename = f"logs/images/screenshot_{session_id}_{datetime.now().strftime('%Y%m%d_%H%M%S_%f')}.png"

        if website_screenshot:
            # Decode base64 string to binary data before saving
            try:
                if isinstance(website_screenshot, str):
                    # It's a base64 string, decode it
                    screenshot_binary = base64.b64decode(website_screenshot)
                else:
                    # It's already binary data
                    screenshot_binary = website_screenshot

                with open(screenshot_filename, "wb") as img_file:
                    img_file.write(screenshot_binary)
                screenshot_path = screenshot_filename
                print(f"🖼️ Saved screenshot to: {screenshot_path}")
            except Exception as decode_error:
                print(f"Warning: Could not decode/save screenshot: {decode_error}")
    except Exception as e:
        print(f"Warning: Could not capture page state: {e}")

    # Make sure we have state history
    if hasattr(agent_obj, "state") and agent_obj.state:
        history = agent_obj.state.history
    else:
        print("Warning: Agent has no state history")
        return

    try:
        # Process model thoughts
        model_thoughts = history.model_thoughts()
        model_thoughts_json = obj_to_json_safe(model_thoughts)
        if isinstance(model_thoughts_json, list) and len(model_thoughts_json) > 0:
            model_thoughts_last_elem = model_thoughts_json[-1]

        # Process model outputs
        model_outputs = history.model_outputs()
        model_outputs_json = obj_to_json_safe(model_outputs)
        if isinstance(model_outputs_json, list) and len(model_outputs_json) > 0:
            model_outputs_json_last_elem = model_outputs_json[-1]

        # Process model actions
        model_actions = history.model_actions()
        model_actions_json = obj_to_json_safe(model_actions)
        if isinstance(model_actions_json, list) and len(model_actions_json) > 0:
            model_actions_json_last_elem = model_actions_json[-1]

        # Process extracted content
        extracted_content = history.extracted_content()
        extracted_content_json = obj_to_json_safe(extracted_content)
        if isinstance(extracted_content_json, list) and len(extracted_content_json) > 0:
            extracted_content_json_last_elem = extracted_content_json[-1]

        # Process URLs
        urls = history.urls()
        urls_json = obj_to_json_safe(urls)
        if isinstance(urls_json, list) and len(urls_json) > 0:
            urls_json_last_elem = urls_json[-1]

    except Exception as e:
        print(f"Warning: Error processing history data: {e}")

    # Create a summary of all data for this step (removed website_html)
    model_step_summary = {
        "timestamp": datetime.now().isoformat(),
        "website_screenshot": website_screenshot,
        "screenshot_path": screenshot_path,
        "url": urls_json_last_elem,
        "model_thoughts": model_thoughts_last_elem,
        "model_outputs": model_outputs_json_last_elem,
        "model_actions": model_actions_json_last_elem,
        "extracted_content": extracted_content_json_last_elem,
    }

    print(f"📍 Current URL: {urls_json_last_elem}")

    # Save data locally
    result = save_agent_history_step(
        data=model_step_summary, session_id=session_id, run_dir=run_dir
    )
    print(f"💾 Recording result: {result}")


async def run_browser_agent(
    prompt: str, project_address: str, record_activity: bool = False
) -> AgentHistoryList:
    # Initialize BrowserSession as specified

    # Generate session ID for this run
    session_id = datetime.now().strftime("%Y%m%d_%H%M%S")

    # Create a dedicated folder for this run
    run_dir = f"logs/sessions/{session_id}"
    os.makedirs(run_dir, exist_ok=True)
    os.makedirs(f"{run_dir}/images", exist_ok=True)
    os.makedirs(f"{run_dir}/video", exist_ok=True)
    os.makedirs(f"{run_dir}/gif", exist_ok=True)
    os.makedirs(f"{run_dir}/browser_activity", exist_ok=True)
    os.makedirs(f"{run_dir}/conversation", exist_ok=True)

    browser_config = BrowserProfile(
        headless=False,
        viewport={"width": 1920, "height": 1080},
        record_video_dir=f"{run_dir}/video",
    )
    browser_session = BrowserSession(
        browser_profile=browser_config,
    )

    gif_path = f"{run_dir}/gif/agent_history_{session_id}.gif"

    # Create recording hook if requested
    recording_hook = None
    if record_activity:
        recording_hook = lambda agent_obj: record_browser_activity(
            agent_obj, session_id, run_dir
        )

    agent = Agent(
        task=prompt,
        llm=get_sealos_model("claude-3-5-sonnet-20240620"),
        browser_session=browser_session,
        save_conversation_path=f"{run_dir}/conversation/conversation",
        extend_system_message="",
        message_context="",
        # initial_actions=[{"open_tab": {"url": project_address}}],
        generate_gif=gif_path,
    )

    print(f"🚀 Starting Browser Agent (Session: {session_id})")
    if record_activity:
        print("📹 Activity recording enabled")

    try:
        if record_activity:
            history = await agent.run(max_steps=20, on_step_start=recording_hook)
        else:
            history = await agent.run(max_steps=20)

        # Save session summary if recording
        if record_activity:
            session_summary = {
                "session_id": session_id,
                "task": prompt,
                "project_address": project_address,
                "start_time": session_id,
                "end_time": datetime.now().isoformat(),
                "total_steps": len(history.history) if history else 0,
                "status": "completed",
            }
            save_session_summary(session_summary, session_id, run_dir)

        return history

    except Exception as e:
        print(f"❌ Error running browser agent: {e}")

        # Save error session summary if recording
        if record_activity:
            error_summary = {
                "session_id": session_id,
                "task": prompt,
                "project_address": project_address,
                "start_time": session_id,
                "end_time": datetime.now().isoformat(),
                "status": "error",
                "error": str(e),
            }
            save_session_summary(error_summary, session_id, run_dir)

        raise


# Example usage for testing
async def run_recorded_browser_agent_example():
    """Example of running browser agent with activity recording"""
    prompt = (
        "Navigate to the homepage and check if the navigation menu is working properly"
    )
    project_address = "https://mpiadxtjesgr.sealosbja.site/"

    history = await run_browser_agent(
        prompt=prompt, project_address=project_address, record_activity=True
    )

    print(
        f"🎯 Browser agent completed with {len(history.history) if history else 0} steps"
    )
    return history


async def test_stock_price_comparison():
    """Test function to search and compare stock prices of Tesla, Apple, and Nvidia"""
    prompt = """
    Search for the current stock prices of Tesla (TSLA) and Apple (AAPL).
    
    For each stock:
    1. Go to a financial website like Yahoo Finance or Google Finance
    2. Search for the stock ticker symbol
    3. Find the current stock price
    4. Note any percentage change for the day
    
    After gathering all three stock prices, provide a comparison summary including:
    - Current price of each stock
    - Which stock has the highest price
    - Which stock has performed best today (highest percentage gain)
    - Any notable trends or observations
    
    Take screenshots at key moments to document the search process.
    """

    # Use a financial website as the starting point
    project_address = "https://finance.yahoo.com"

    print("🔍 Starting stock price comparison test...")
    print("📊 Searching for: Tesla (TSLA), Apple (AAPL)")

    try:
        history = await run_browser_agent(
            prompt=prompt, project_address=project_address, record_activity=True
        )

        print(
            f"✅ Stock price comparison completed with {len(history.history) if history else 0} steps"  # noqa: E501
        )
        print("📁 Check logs/sessions/ for detailed recording of the search process")
        return history

    except Exception as e:
        print(f"❌ Error during stock price comparison: {e}")
        raise


async def test_stock_price_comparison_simple():
    """Simplified test function for stock price comparison with basic search"""
    prompt = """
    Go to Yahoo Finance and search for the stock prices of:
    1. Tesla (TSLA)
    2. Apple (AAPL) 
    3. Nvidia (NVDA)
    
    For each stock, find the current price and daily change percentage.
    Compare which stock is performing best today.
    """

    project_address = "https://finance.yahoo.com"

    print("🚀 Running simplified stock price comparison...")

    history = await run_browser_agent(
        prompt=prompt, project_address=project_address, record_activity=True
    )

    print(
        f"📈 Stock comparison completed! Steps taken: {len(history.history) if history else 0}"
    )
    return history


if __name__ == "__main__":
    #     # Run the stock price comparison test
    asyncio.run(test_stock_price_comparison())
#
#     # Or run the simple version
#     # asyncio.run(test_stock_price_comparison_simple())
#
#     # Or run the original example
#     # asyncio.run(run_recorded_browser_agent_example())
