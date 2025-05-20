import os
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI

load_dotenv()


def get_sealos_model(model_name: str):
    return ChatOpenAI(
        model=model_name,
        base_url=os.getenv("SEALOS_BASE_URL"),
        api_key=os.getenv("SEALOS_API_KEY"),
    )
