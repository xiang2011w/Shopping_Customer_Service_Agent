import sys
import os

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from langchain.agents import initialize_agent, AgentType
from langchain.tools import Tool
from langchain.memory import ConversationBufferMemory

# Load environment variables (for OpenAI API key)
load_dotenv()

# Load system prompt
with open("prompts/system_prompt.txt", "r") as f:
    system_prompt = f.read()

# Import RAG retriever and return policy tool
from rag.retriever import query_order_info
from tools.return_policy_tool import fetch_return_policy_tool

# Define a LangChain Tool for order info retrieval
order_info_tool = Tool(
    name="OrderInfoRetriever",
    func=lambda query: "\n\n".join(
        [doc.page_content for doc in query_order_info(query)]
    ),
    description="Retrieves order information from local markdown files given an order number or query.",
)

# Prepare the list of tools for the agent
tools = [
    order_info_tool,
    fetch_return_policy_tool,  # Already a LangChain tool
]

# Initialize the LLM
llm = ChatOpenAI(model="gpt-3.5-turbo", temperature=0)

# Add conversational memory
memory = ConversationBufferMemory(memory_key="chat_history", return_messages=True)

# Use a conversational agent type
agent = initialize_agent(
    tools=tools,
    llm=llm,
    agent=AgentType.CONVERSATIONAL_REACT_DESCRIPTION,
    verbose=True,
    agent_kwargs={"system_message": system_prompt},
    memory=memory,
)

if __name__ == "__main__":
    print("Welcome to the Amazon Return Assistant!\n")
    while True:
        user_input = input("You: ")
        if user_input.lower() in {"exit", "quit"}:
            print("Goodbye!")
            break
        response = agent.run(input=user_input)
        print(f"Agent: {response}\n")
