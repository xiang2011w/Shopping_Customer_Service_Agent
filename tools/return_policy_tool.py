from langchain.tools import tool
import os
from datetime import datetime


@tool("fetch_return_policy", return_direct=True)
def fetch_return_policy_tool(tool_input: str) -> str:
    """
    Fetches the Amazon return policy from a local markdown file and checks return eligibility
    based on the delivery date and current date.

    Args:
        tool_input: A string containing order information including delivery date.

    Returns:
        The return policy text with eligibility information based on current date.
    """
    # Print what we actually received
    print(f"******************* Tool input received: {tool_input} *******************")

    # Get the current date
    current_date = datetime.now()
    current_date_str = current_date.strftime("%Y-%m-%d")

    # Extract delivery date from the tool_input
    delivery_date = None

    # Try to find delivery date in the tool_input
    try:
        import re

        date_match = re.search(r"Delivery date:\s*(\d{4}-\d{2}-\d{2})", tool_input)
        if date_match:
            delivery_date_str = date_match.group(1)
            print(f"Found delivery date in tool input: {delivery_date_str}")
            delivery_date = datetime.strptime(delivery_date_str, "%Y-%m-%d")

            # Calculate days since delivery
            days_since_delivery = (current_date - delivery_date).days

            # Add eligibility information
            eligibility_info = f"\n\nCurrent date: {current_date_str}\n"
            eligibility_info += f"Delivery date: {delivery_date_str}\n"
            eligibility_info += f"Days since delivery: {days_since_delivery}\n"

            if days_since_delivery <= 30:
                eligibility_info += (
                    "Return status: ELIGIBLE - Within 30-day return window\n"
                )
            else:
                eligibility_info += (
                    "Return status: NOT ELIGIBLE - Beyond 30-day return window\n"
                )
        else:
            eligibility_info = f"\n\nCurrent date: {current_date_str}\nNo delivery date found in order information.\n"
            print("No delivery date found in tool input!")
    except Exception as e:
        eligibility_info = f"\n\nCurrent date: {current_date_str}\nUnable to determine return eligibility: {str(e)}\n"
        print(f"Error processing delivery date: {str(e)}")

    # Load base return policy
    max_chars = 2000
    policy_path = os.path.join(os.path.dirname(__file__), "amazon_return_policy.md")
    with open(policy_path, "r", encoding="utf-8") as f:
        text = f.read()

    # Combine policy with eligibility information
    return text[:max_chars] + eligibility_info
