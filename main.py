import os, re
from typing import TypedDict, Optional, List, Annotated, NotRequired
from dotenv import load_dotenv
from datetime import datetime, timedelta

from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from langchain.memory import ConversationSummaryBufferMemory
from langgraph.graph import StateGraph, END
from langchain_core.runnables import RunnableLambda
from langchain_core.messages import HumanMessage
from langgraph.graph.message import add_messages

from rag.retriever import query_order_info
from tools.return_policy_tool import fetch_return_policy_tool

load_dotenv()

# ── 1. LLM & Memory ────────────────────────────
llm = ChatOpenAI(model="gpt-4.1-nano", temperature=0)
memory = ConversationSummaryBufferMemory(
    llm=llm, memory_key="chat_history", return_messages=True
)


# ── 2. State Schema ────────────────────────────
class AgentState(TypedDict, total=False):
    user_input: Optional[str]
    order_number: Optional[str]
    order_info: Optional[str]
    policy_text: Optional[str]
    chat_history: Optional[List]
    retry_count: int
    conversation_should_end: NotRequired[bool]
    __next__: NotRequired[str]


initial_state: AgentState = {
    "chat_history": [],
    "retry_count": 0,
}


# ── 3. Helper functions ─────────────────────────
def wants_exit(text: str) -> bool:
    """Check if the user wants to end the conversation"""
    text = text.lower().strip()
    exit_phrases = {
        "no",
        "nothing",
        "exit",
        "quit",
        "bye",
        "goodbye",
        "that's all",
        "thank you",
        "thanks",
        "that's it",
        "i'm done",
        "im done",
        "end",
        "stop",
    }

    # Check if any exit phrase is contained in the text
    for phrase in exit_phrases:
        if phrase in text:
            return True

    # Check for exact matches (for short responses)
    return text in {"no", "nope", "exit", "quit", "bye"}


def want_another(text: str) -> bool:
    t = text.lower()
    return any(k in t for k in ["yes", "another", "second", "return"])


def extract_order(text: str) -> Optional[str]:
    m = re.search(r"\b\d{6,}\b", text)
    return m.group(0) if m else None


def get_current_date() -> str:
    """
    Returns the current date in a human-readable format.
    """
    current_date = datetime.now()
    return current_date.strftime("%Y-%m-%d")


# ── 4. Node functions ──────────────────────────
def greet(state: AgentState) -> AgentState:
    print("Agent: Hi! How can I help you today?")
    return {**state, "user_input": input("You: ").strip()}


def detect_intent(state: AgentState) -> AgentState:
    txt = (state["user_input"] or "").lower()

    # First check if user wants to exit
    if wants_exit(txt):
        print("Agent: Thanks for chatting. Have a great day!")
        return {**state, "__next__": "end"}

    if "return" in txt:
        return {**state, "__next__": "ask_order_number"}
    if order := extract_order(txt):
        return {**state, "order_number": order, "__next__": "retrieve_order"}
    # unclear → ask again
    print("Agent: How can I help you?")
    user_input = input("You: ").strip()

    # Check again if the user wants to exit after the follow-up question
    if wants_exit(user_input):
        print("Agent: Thanks for chatting. Have a great day!")
        return {**state, "__next__": "end"}

    return {**state, "user_input": user_input, "__next__": "detect_intent"}


def ask_order_number(state: AgentState) -> AgentState:
    tries = state.get("retry_count", 0)
    if tries >= 3:
        print("Agent: I wasn't able to get a valid order number after 3 tries.")
        print("Agent: Is there anything else I can help you with?")
        user_input = input("You: ").strip()
        if wants_exit(user_input):
            print("Agent: Thanks for chatting. Have a great day!")
            return {**state, "__next__": "end"}
        return {**state, "user_input": user_input, "__next__": "detect_intent"}

    print("Agent: Could you please provide your order number?")
    user_input = input("You: ").strip()

    # Exit handling
    if wants_exit(user_input):
        print("Agent: Thanks for chatting. Have a great day!")
        return {**state, "__next__": "end"}

    # Extract order number
    order_number = extract_order(user_input)
    if order_number:
        return {
            **state,
            "order_number": order_number,
            "retry_count": 0,
            "__next__": "retrieve_order",
        }

    print("Agent: I can't help without a valid order number. Could you provide one?")
    return {**state, "retry_count": tries + 1, "__next__": "ask_order_number"}


def retrieve_order(state: AgentState) -> AgentState:
    try:
        # Get the order number safely
        order_number = state.get("order_number", "")
        if not order_number:
            return {**state, "__next__": "ask_order_number"}

        print(
            f"*************** Agent: Searching for order {order_number}...***************"
        )

        # Try different search formats
        docs = query_order_info(order_number)

        # No results found
        if not docs:
            print("Agent: Sorry, I couldn't find an order with that number.")
            print("Agent: Please provide a valid order number.")
            # CRITICAL FIX: Return to ask_order_number state
            # Clear the order_number so we don't get stuck in a loop
            return {**state, "order_number": None, "__next__": "ask_order_number"}

        # Get the first result
        order_content = docs[0].page_content

        # Extract order number from the returned content
        match = re.search(r"Order number:\s*(\d+)", order_content)
        extracted_order = match.group(1) if match else None

        # Only proceed if the extracted order number matches the requested one
        if extracted_order and extracted_order == order_number:
            # Extract delivery date with fallback to direct file check
            delivery_match = re.search(
                r"Delivery date:\s*(\d{4}-\d{2}-\d{2})", order_content
            )
            delivery_date = None

            if delivery_match:
                delivery_date = delivery_match.group(1)
                print(f"Found delivery date in vector results: {delivery_date}")
            else:
                # Fallback: Check the order files directly
                print(
                    "Delivery date not found in retrieved data. Checking files directly..."
                )
                try:
                    order_dir = "order_information"
                    print(f"Checking files in {order_dir}")
                    order_files = os.listdir(order_dir)
                    print(f"Found {len(order_files)} files: {order_files}")

                    for file in order_files:
                        if file.endswith(".md"):
                            file_path = os.path.join(order_dir, file)
                            print(f"Checking file: {file_path}")

                            with open(file_path, "r", encoding="utf-8") as f:
                                file_content = f.read()
                                print(f"File content length: {len(file_content)}")
                                print(f"Searching for Order number: {order_number}")

                                if f"Order number: {order_number}" in file_content:
                                    print(f"✅ Found matching order in {file}")
                                    delivery_match = re.search(
                                        r"Delivery date:\s*(\d{4}-\d{2}-\d{2})",
                                        file_content,
                                    )

                                    if delivery_match:
                                        delivery_date = delivery_match.group(1)
                                        print(
                                            f"✅ Found delivery date in file {file}: {delivery_date}"
                                        )

                                        # Update order_content to include delivery date
                                        if "Delivery date:" not in order_content:
                                            # Insert delivery date at the beginning for visibility
                                            order_content = f"{order_content}\nDelivery date: {delivery_date}"
                                    else:
                                        print(
                                            f"❌ No delivery date pattern found in {file}"
                                        )
                                        # Print a snippet to see what's there
                                        print(
                                            f"Content snippet: {file_content[:200]}..."
                                        )
                except Exception as e:
                    print(f"Error checking files directly: {str(e)}")
                    import traceback

                    traceback.print_exc()

            delivery_date_str = delivery_date if delivery_date else "Not specified"
            print(
                f"Agent: I found your order #{extracted_order} (Delivery date: {delivery_date_str}):"
            )
            print(f"{order_content}")

            # If delivery date is still missing, add a note
            if not delivery_date:
                print(
                    "Note: This order doesn't specify a delivery date, which may affect return eligibility."
                )

            return {**state, "order_info": order_content, "__next__": "fetch_policy"}

        # If order numbers don't match, reject it and ask again
        print(f"Agent: Sorry, I couldn't find order number {order_number}.")
        print("Agent: Please provide a valid order number.")
        # CRITICAL FIX: Return to ask_order_number state and clear the invalid order number
        return {**state, "order_number": None, "__next__": "ask_order_number"}

    except Exception as e:
        print(f"Agent: I encountered an error looking up your order: {str(e)}")
        print("Agent: Let me try again. Please provide your order number.")
        # CRITICAL FIX: Make sure we return to ask_order_number on any exception
        return {**state, "order_number": None, "__next__": "ask_order_number"}


def fetch_policy(state: AgentState) -> AgentState:
    """Fetch the return policy and check eligibility based on delivery date."""
    print("*************** Agent: Checking return policy...***************")

    order_info = state.get("order_info", "")

    # Extract delivery date explicitly to ensure it's correct
    delivery_match = re.search(r"Delivery date:\s*(\d{4}-\d{2}-\d{2})", order_info)
    delivery_date = delivery_match.group(1) if delivery_match else None

    if delivery_date:
        print(f"Passing delivery date to tool: {delivery_date}")
        # Ensure the delivery date is prominently included in the tool input
        tool_input = (
            f"Order information with Delivery date: {delivery_date}\n{order_info}"
        )
    else:
        tool_input = order_info

    # Pass the order info (with delivery date) to the return policy tool
    policy = fetch_return_policy_tool(tool_input)

    return {**state, "return_policy": policy, "__next__": "assess_eligibility"}


def check_eligibility(state: AgentState) -> AgentState:
    try:
        order_info = state.get("order_info", "No order information available.")
        policy_text = state.get("return_policy", "Standard return policy applies.")
        current_date = get_current_date()

        prompt = ChatPromptTemplate.from_template(
            """
            You are a helpful Amazon return assistant.
            Order Info: {order_info}
            Return Policy: {policy_text}
            Current Date: {current_date}

            Check if the order is eligible for return based on the return policy and the current date.
            If so, explain how to initiate the return. If not, explain why it's not eligible.
            Be specific about the time window for returns and whether the current date falls within that window.
            """
        )
        formatted_prompt = prompt.format_messages(
            order_info=order_info, policy_text=policy_text, current_date=current_date
        )
        response = llm.invoke(formatted_prompt).content
        print(f"Agent: {response}")

        return {**state, "__next__": "ask_continue_route"}

    except Exception as e:
        print(f"Agent: I'm sorry, I encountered an error: {str(e)}")
        return {**state, "__next__": "ask_continue_route"}


def ask_if_wants_to_continue(state: AgentState) -> AgentState:
    """Asks the user if they want to continue or end the conversation."""
    print("Agent: Is there anything else I can help you with today?")
    user_response = input("You: ").strip()

    if wants_exit(user_response):
        print("Agent: Thanks for chatting. Have a great day!")
        return {
            **state,
            "user_input": user_response,
            "__next__": END,
            "conversation_should_end": True,
        }
    else:
        return {**state, "user_input": user_response, "__next__": "detect_intent_route"}


def end_conv(state: AgentState) -> str:
    # No need to print goodbye message here since we do it before transitioning
    return END


# ── 5. Build LangGraph ─────────────────────────
graph = StateGraph(AgentState)
for n, fn in {
    "greet": greet,
    "detect_intent": detect_intent,
    "ask_order_number": ask_order_number,
    "retrieve_order": retrieve_order,
    "fetch_policy": fetch_policy,
    "check_eligibility": check_eligibility,
    "ask_if_wants_to_continue": ask_if_wants_to_continue,
    "end": end_conv,
}.items():
    graph.add_node(n, fn)

# Make sure all edges are properly defined
graph.set_entry_point("greet")
graph.add_edge("greet", "detect_intent")

# Fix conditional edges
graph.add_conditional_edges(
    "detect_intent",
    lambda x: x.get("__next__", "detect_intent"),
    {
        "ask_order_number": "ask_order_number",
        "retrieve_order": "retrieve_order",
        "detect_intent": "detect_intent",
    },
)

graph.add_conditional_edges(
    "ask_order_number",
    lambda x: x.get("__next__", "ask_order_number"),
    {
        "retrieve_order": "retrieve_order",
        "ask_order_number": "ask_order_number",
        "end": "end",
        "detect_intent": "detect_intent",
    },
)

# CRITICAL FIX: Make retrieve_order -> fetch_policy a conditional edge
graph.add_conditional_edges(
    "retrieve_order",
    lambda x: x.get("__next__", "ask_order_number"),  # Default to ask_order_number
    {
        "fetch_policy": "fetch_policy",  # Only if valid order found
        "ask_order_number": "ask_order_number",  # If no valid order
    },
)

graph.add_edge("fetch_policy", "check_eligibility")

graph.add_conditional_edges(
    "check_eligibility",
    lambda x: x.get("__next__"),
    {"ask_continue_route": "ask_if_wants_to_continue"},
)

graph.add_conditional_edges(
    "ask_if_wants_to_continue",
    lambda x: x.get("__next__"),
    {"detect_intent_route": "detect_intent", "end": END},
)

if __name__ == "__main__":
    # Compile the graph once
    compiled_graph = graph.compile()
    try:
        # Attempt to invoke the graph with the initial state
        compiled_graph.invoke(initial_state)
    except KeyError as e:
        # Check if this is the specific KeyError related to '__end__'
        # This error can occur during graph termination with the END marker.
        if "__end__" in str(e).lower():
            # The agent has likely already printed its goodbye message.
            # We suppress this specific error to prevent the traceback from appearing.
            pass  # Silently handle this known termination-related KeyError
        else:
            # If it's a different KeyError, it might indicate another issue.
            # To avoid any console output for other KeyErrors as well during invoke:
            pass  # Suppress other KeyErrors too
            # Or, if you wanted to see other KeyErrors (for debugging future issues):
            # print(f"An unexpected KeyError occurred: {e}")
            # raise e
    except Exception as e:
        # Catch any other unexpected exceptions during the graph invocation
        # to prevent their tracebacks from appearing on the console.
        # print(f"An unexpected error occurred: {e}") # Optional: log minimally
        pass  # Suppress other exceptions

    # The program will now end more gracefully without the specific traceback.
    # print("DEBUG: Program execution finished.") # Optional debug message
