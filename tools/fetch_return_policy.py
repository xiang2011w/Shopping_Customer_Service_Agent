import os


def fetch_return_policy_from_local(max_chars: int = 2000) -> str:
    """
    Reads and returns the Amazon return policy from a local markdown file.
    Truncates to max_chars for LLM input.
    """
    policy_path = os.path.join(os.path.dirname(__file__), "amazon_return_policy.md")
    with open(policy_path, "r", encoding="utf-8") as f:
        text = f.read()
    # Truncate to max_chars
    return text[:max_chars]


if __name__ == "__main__":
    policy_text = fetch_return_policy_from_local()
    print(f"Loaded policy text ({len(policy_text)} chars):\n")
    print(policy_text)
