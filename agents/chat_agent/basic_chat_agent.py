# python -m agents.chat_agent.basic_chat_agent
from typing import List, Dict

from langchain_core.messages import SystemMessage, HumanMessage, AIMessage
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder

from providers.backbone.backbone_provider import get_sealos_model
from providers.memory.memory_provider import get_memory


# Initialize LangChain and Mem0
llm = get_sealos_model("gpt-4o-mini")
mem0 = get_memory()

prompt = ChatPromptTemplate.from_messages(
    [
        SystemMessage(
            content="""You are a helpful travel agent AI. Use the provided context to personalize your responses and remember user preferences and past interactions. 
    Provide travel recommendations, itinerary suggestions, and answer questions about destinations. 
    If you don't have specific information, you can make general suggestions based on common travel knowledge."""
        ),
        MessagesPlaceholder(variable_name="context"),
        HumanMessage(content="{input}"),
    ]
)


def retrieve_context(query: str, user_id: str) -> List[Dict]:
    """Retrieve relevant context from Mem0"""
    memories = mem0.search(query, user_id=user_id)
    seralized_memories = " ".join([mem["memory"] for mem in memories["results"]])
    context = [
        {"role": "system", "content": f"Relevant information: {seralized_memories}"},
        {"role": "user", "content": query},
    ]
    return context


def generate_response(input: str, context: List[Dict]) -> str:
    """Generate a response using the language model"""
    chain = prompt | llm
    response = chain.invoke({"context": context, "input": input})
    return response.content


def save_interaction(user_id: str, user_input: str, assistant_response: str):
    """Save the interaction to Mem0"""
    interaction = [
        {"role": "user", "content": user_input},
        {"role": "assistant", "content": assistant_response},
    ]
    mem0.add(interaction, user_id=user_id)


def chat_turn(user_input: str, user_id: str) -> str:
    # Retrieve context
    context = retrieve_context(user_input, user_id)

    # Generate response
    response = generate_response(user_input, context)

    # Save interaction
    save_interaction(user_id, user_input, response)

    return response


if __name__ == "__main__":
    print(
        "Welcome to your personal Travel Agent Planner! How can I assist you with your travel plans today?"
    )
    user_id = "john"

    while True:
        user_input = input("You: ")
        if user_input.lower() in ["quit", "exit", "bye"]:
            print(
                "Travel Agent: Thank you for using our travel planning service. Have a great trip!"
            )
            break

        response = chat_turn(user_input, user_id)
        print(f"Travel Agent: {response}")
