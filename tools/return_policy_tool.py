from langchain.tools import tool
import os


@tool("fetch_return_policy", return_direct=True)
def fetch_return_policy_tool(tool_input: str) -> str:
    """
    Fetches the Amazon return policy from a local markdown file and truncates it for LLM input.
    Ignores the tool_input, but required for LangChain tool compatibility.
    """
    max_chars = 2000  # Hardcoded for now; can be adjusted if needed
    policy_path = os.path.join(os.path.dirname(__file__), "amazon_return_policy.md")
    with open(policy_path, "r", encoding="utf-8") as f:
        text = f.read()
    return text[:max_chars]
