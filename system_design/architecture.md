Online shopping customer service agent - Architecture Overview

File & Folder Structure

AI_Return_Assistant/
├── order_information/            # Local folder storing all order `.md` files (one per order)
│   ├── order_123456.md
│   └── order_654321.md
│
├── tools/
│   └── fetch_return_policy.py    # MCP Tool to fetch return policy from Amazon URL
│
├── rag/
│   ├── ingest.py                 # Script to convert `.md` files into vector store
│   ├── vectorstore/             # Persisted vector DB from LangChain
│   └── retriever.py             # LangChain retriever wrapper
│
├── agent/
│   └── agent.py                  # Main AI agent logic (LLM, tools, RAG integration)
│
├── prompts/
│   └── system_prompt.txt         # Initial prompt given to the LLM for system behavior
│
├── main.py                       # Entry point for conversation with user
├── requirements.txt              # Python dependencies
└── .env                          # Store API keys (OpenAI, etc)

🔧 Purpose of Each Part

order_information/

Contains order data in Markdown format.

Each .md file includes:

Order number

Purchase date

Product details

Customer name/address

tools/fetch_return_policy.py

LangChain MCP-compatible tool.

Fetches HTML/text from Amazon return policy page.

Cleans and truncates text for LLM input.

rag/

ingest.py: Reads .md files, generates embeddings, and stores in vectorstore (e.g., FAISS).

vectorstore/: Local persistence of the RAG knowledge base.

retriever.py: Provides RAG document retriever for LangChain agent.

agent/agent.py

Initializes ChatOpenAI (or other LLM).

Loads RAG retriever and registers MCP tool (fetch_return_policy).

Handles system prompt, memory (optional), and tool calling.

prompts/system_prompt.txt

Provides the initial behavior guide to the AI agent.

Example: "You are a helpful Amazon return assistant. Always ask for the order number and validate return eligibility."

main.py

Starts CLI/chat interface.

Displays greeting and handles user input/output.

Delegates reasoning to LangChain agent with RAG + tool access.

.env

Stores environment variables, such as OpenAI API key and base URL.

🧠 State Management & Service Connection

State Location

Long-term state: Vector DB (RAG), updated via ingest.py

Short-term memory (optional): In-memory conversational history within LangChain agent

User session state: Managed in main.py (e.g., order number, dialog flow)

Service Flow

Startup

main.py greets user.

Waits for user query (e.g., return a product).

Order Validation via RAG

Agent asks for order number.

RAG searches vectorstore using retriever for the specific order .md file.

Return Policy Retrieval

MCP fetch_return_policy tool is called to scrape Amazon return policy.

Result truncated/cleaned and used as part of reasoning.

Return Eligibility Check

Agent compares order date and policy requirements (e.g., within 30–60 days).

If eligible, provides steps for return.

If ineligible, gives explanation and any alternative suggestions.

Final Output

Output is streamed back to user via main.py.

✅ Notes for Cursor Setup

Run ingest.py first to build RAG vector store.

Ensure .env has required OpenAI key.

Start app via: python main.py

MCP tool can be extended with more policies in future.

🛠️ Suggested Tech Stack

Component

Tech

LLM

OpenAI (gpt-4/gpt-3.5)

Embeddings

OpenAI / HuggingFace

Vector DB

FAISS (local, free)

Tool call interface

LangChain Tools + @tool

Markdown parsing

Python markdown module

Web scraping

requests, BeautifulSoup

This architecture enables a simple but powerful retrieval-augmented agent with real-time policy comparison using LangChain and external tools.

