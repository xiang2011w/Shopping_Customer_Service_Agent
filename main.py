import os, re
from typing import TypedDict, Optional, List
from dotenv import load_dotenv
from datetime import datetime, timedelta

from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from langchain.memory import ConversationSummaryBufferMemory
from langgraph.graph import StateGraph, END
from langchain_core.runnables import RunnableLambda
from langchain_core.messages import HumanMessage

from rag.retriever import query_order_info
from tools.return_policy_tool import fetch_return_policy_tool

load_dotenv()

# ── 1. LLM & Memory ────────────────────────────
llm = ChatOpenAI(model="gpt-4", temperature=0)
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
            print(f"Agent: I found your order:\n{order_content}")
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
    try:
        print("*************** Agent: Checking return policy...***************")
        policy_text = fetch_return_policy_tool.invoke("")
        return {
            **state,
            "policy_text": policy_text,
            "__next__": "check_eligibility",
        }
    except Exception as e:
        print(f"Agent: I had trouble retrieving the return policy: {str(e)}")
        print("Agent: Let me see what I can tell you about your order anyway.")
        return {
            **state,
            "policy_text": "Standard 30-day return policy applies.",
            "__next__": "check_eligibility",
        }


def check_eligibility(state: AgentState) -> AgentState:
    try:
        order_info = state.get("order_info", "No order information available.")
        policy_text = state.get("policy_text", "Standard return policy applies.")

        # Get the current date
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

        print("Agent: Is there anything else I can help you with?")
        follow = input("You: ").strip()

        # IMPORTANT FIX: Improved exit detection
        if wants_exit(follow):
            print("Agent: Thanks for chatting. Have a great day!")
            return {**state, "__next__": "end"}

        if want_another(follow):
            return {
                **state,
                "order_number": None,
                "retry_count": 0,
                "__next__": "ask_order_number",
            }
        # fallback to greeting loop
        return {**state, "user_input": follow, "__next__": "detect_intent"}
    except Exception as e:
        print(f"Agent: I'm sorry, I encountered an error: {str(e)}")
        print("Agent: Is there anything else I can help you with?")
        user_input = input("You: ").strip()
        if wants_exit(user_input):
            return {**state, "__next__": "end"}
        return {**state, "user_input": user_input, "__next__": "detect_intent"}


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
    lambda x: x.get("__next__", "detect_intent"),
    {
        "ask_order_number": "ask_order_number",
        "detect_intent": "detect_intent",
        "end": "end",
    },
)

if __name__ == "__main__":
    graph.compile().invoke(initial_state)
