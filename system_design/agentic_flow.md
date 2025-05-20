Agentic Workflow: Online Shopping Return Assistant

This workflow defines a LangGraph-based AI return assistant capable of handling realistic, multi-turn conversations for returning online orders. It incorporates natural conversation patterns, retry logic, and multiple return requests per session. Use this as a blueprint to update main.py.

## 1. States & Responsibilities

| State                  | Responsibility                                                                                   |
| ---------------------- | ------------------------------------------------------------------------------------------------ |
| **greet**              | Send greeting prompt. Collect initial user input.                                                |
| **detect\_intent**     | Determine if user wants to return an item or provided an order number inadvertently.             |
| **ask\_order\_number** | Prompt for a valid order number, with up to 3 retries.                                           |
| **retrieve\_order**    | Query RAG store for order data. Handle missing or invalid orders.                                |
| **fetch\_policy**      | Invoke MCP tool to fetch and clean the latest return policy.                                     |
| **check\_eligibility** | Use LLM to compare order date vs. policy window. Show result and ask if user has another return. |
| **end**                | Send closing message. End conversation.                                                          |

---

## 2. Transition Logic & Looping

```mermaid
flowchart TD
  greet --> detect_intent

  detect_intent -->|Return intent detected| ask_order_number
  detect_intent -->|Order# detected early| retrieve_order
  detect_intent -->|No intent| greet

  ask_order_number -->|Valid order#| retrieve_order
  ask_order_number -->|Invalid (retry<3)| ask_order_number
  ask_order_number -->|Invalid (retry≥3)| end

  retrieve_order -->|Found| fetch_policy
  retrieve_order -->|Not found| ask_order_number

  fetch_policy --> check_eligibility

  check_eligibility -->|Eligible & wants another?| ask_order_number
  check_eligibility -->|Not eligible & wants another?| ask_order_number
  check_eligibility -->|No further returns| end

  end
```

* **Loop-backs** ensure natural dialogs: unclear inputs return to `greet`, invalid orders retry in `ask_order_number`, and multi-item flows re-enter `ask_order_number` from `check_eligibility`.

---

## 3. Conversation Patterns & Test Cases

Integrate sample test conversations (derived from `example1.md`, `example2.md`, `example3.md`) to validate behavior:

### 3.1 Simple Single-Item Return (example1)

1. **greet**: “Hi!” → user says “I want to return my Amazon item.”
2. **ask\_order\_number**: user provides `9823417654` → valid →
3. **retrieve\_order**: order found →
4. **fetch\_policy** + **check\_eligibility**: eligible →
5. **end**: user says “That’s all.” → Closing.

### 3.2 Two-Item Mixed Flow (example2)

1–4. As above for first item → after eligibility, user says “I have second item want to return.”
5\. **ask\_order\_number**: user gives `4102379581` → valid →
6\. **retrieve\_order**: order found →
7\. **fetch\_policy** + **check\_eligibility**: ineligible →
8\. **end**: user says “Ok” → Closing.

### 3.3 Retry & Invalid Orders (example3)

* At **ask\_order\_number**, user says “I don’t know” / “I forgot” → trigger 2 retries.
* User first enters `1234567` → not found → back to **ask\_order\_number**
* Second valid `9823417654` → success → return →
* Second-item: enters invalid `1234567891` twice, then says “that’s all” → exit gracefully.

---

## 4. Implementation Notes

* **State Schema** must include: `user_input`, `order_number`, `order_info`, `policy_text`, `retry_count`, `continue_conversation`, plus `__next__` pointer.
* **Retry Logic**: Increment `retry_count` in `ask_order_number`; on ≥3, end with a polite message.
* **Intent Detection**: Keyword-based OR early order number detection in `detect_intent`.
* **Tool Integration**: `fetch_policy_node` prints “checking return policy .....” then calls `fetch_return_policy_tool()`.
* **Multi-Return Flow**: In `eligibility_node`, after presenting result, capture user response; if they indicate another return, loop to `ask_order_number`.
* **Exit Conditions**: `continue_conversation` flag can guard immediate end; all node functions must return dict with `__next__` except `end` returns `END`.

---

Use this workflow as a guide for Cursor-driven updates to `main.py`. Each node in the workflow corresponds to a function, and transitions map to `graph.add_edge()` calls. Ensure your state updates align with the branching logic above.
