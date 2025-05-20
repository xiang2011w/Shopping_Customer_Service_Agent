MVP (Minimum Viable Product) Goal

Build a LangChain-based AI assistant that:

Greets users and asks how to help.

Retrieves local order info from markdown files using RAG.

Fetches live Amazon return policy via a MCP tool.

Determines if an order meets return eligibility criteria.

Provides appropriate return instructions or explanation.

Step-by-Step Task Plan

Phase 1: Project Bootstrapping

1. Initialize Python project environment

Start: In an empty project folder

End: .venv created, dependencies listed in requirements.txt

Test: Can activate virtual environment and run python without error

2. Create base folder structure

Start: In the root directory

End: All folders created as outlined in architecture.md

Test: Folder paths exist with no files inside

3. Add .env and load OpenAI API key

Start: After .env created

End: .env has OPENAI_API_KEY, app loads it

Test: A print statement confirms the key loads successfully

Phase 2: Order Info RAG Setup

4. Use existing files in order_information/

Test: Files exist and contain readable metadata

5. Write rag/ingest.py to convert .md into FAISS vectorstore

Start: order_information/ files ready

Include comments in the code on how to split the data into chunks and store in the vectorstore.

End: FAISS vectorstore is saved in rag/vectorstore/

Test: ingest.py runs and confirms embeddings stored

6. Write rag/retriever.py to load vectorstore and return results

Start: After ingest.py is working

Include comments in the code on how to load the vectorstore and return the results.

End: A function that can take a query and return relevant .md content

Test: Run a manual query and confirm expected markdown content is retrieved

Phase 3: MCP Tool for Return Policy

7. Implement fetch_return_policy.py tool

Start: Create new script under tools/

End: Tool fetches and returns policy text from provided URL

Test: Policy content is printed or logged with meaningful length (~2,000 chars)

8. Register MCP tool using LangChain @tool decorator

Start: Tool is functional independently

End: Exposed as LangChain-compatible tool

Test: Call tool via LangChain agent and return expected result

Phase 4: Agent Construction

9. Create prompts/system_prompt.txt for assistant behavior

Start: Define LLM personality and instructions

End: Prompt contains greeting logic and return-checking logic hints

Test: Prompt can be read in and printed by agent.py

10. Implement agent initialization in agent.py

Start: Prompt, retriever, and tool are ready

End: Agent initializes LLM, loads retriever + tool

Test: Agent can run a dummy query with tool + RAG response

11. Implement logic to compare order date vs return policy

Start: Order metadata and policy content accessible

End: Agent reasons over order + policy to decide eligibility

Test: Agent answers YES/NO correctly for test inputs

Phase 5: CLI Chat Interface

12. Build basic CLI flow in main.py

Start: Agent is functional in script

End: CLI lets user input query, agent replies

Test: Can ask "I want to return a product", and get agent to respond

13. Add logic for greeting → order number prompt → eligibility path

Start: Basic CLI working

End: Handles full flow: greet → ask order → lookup → check return

Test: Use real example .md file to test flow end-to-end

Phase 6: Final Testing & Polish

14. Add logging to track decisions and tool calls

Start: Agent integrated with tool

End: Logs show steps agent took for debugging

Test: Logs show when it queried vector DB or called fetch tool

15. Add 1–2 more edge-case .md files to test different scenarios

Start: Only success case tested

End: Include one expired order, one missing info

Test: Agent can correctly say "not eligible" or "order not found"

16. Freeze dependencies in requirements.txt

Start: All scripts working

End: All used libraries are pinned to specific versions

Test: New environment installs without issue

This plan ensures that every component is testable and modular, ready to be executed sequentially by an LLM engineer.

