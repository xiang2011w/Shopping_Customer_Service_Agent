import os
from dotenv import load_dotenv
import re

load_dotenv()  # Ensure .env is loaded

from langchain_community.vectorstores import FAISS
from langchain_openai import OpenAIEmbeddings
from langchain.text_splitter import RecursiveCharacterTextSplitter

VECTORSTORE_DIR = "rag/vectorstore"


def load_vectorstore():
    """
    Loads the FAISS vectorstore from disk.
    Returns the vectorstore object directly to allow multiple query strategies.
    """
    embeddings = OpenAIEmbeddings()

    try:
        # Load the persisted FAISS vectorstore
        vectorstore = FAISS.load_local(
            VECTORSTORE_DIR, embeddings, allow_dangerous_deserialization=True
        )
        return vectorstore  # Return the vectorstore itself
    except Exception as e:
        print(f"Error loading vectorstore: {e}")
        return None


def query_order_info(query, k=1):
    """
    Given a user query, returns the most relevant order info.
    Uses advanced search strategies to improve retrieval quality.
    """
    # Print debug information
    print(f"Searching for order: {query}")

    # Load the vectorstore
    vectorstore = load_vectorstore()
    if not vectorstore:
        print("Failed to load vectorstore")
        return []

    # Try various query formulations to find the best match
    query_variations = [
        query,  # Raw query
        f"Order number: {query}",  # Formatted as in document
        f"Order {query}",  # Another common format
        f"return order {query}",  # Context-relevant query
        f"Customer order {query}",  # Another variation
    ]

    # Track all results to avoid duplicates
    seen = set()
    all_results = []

    # First try each query variation
    for variation in query_variations:
        print(f"Trying query: '{variation}'")
        try:
            # Use a reasonable k to avoid processing too many documents
            results = vectorstore.similarity_search(variation, k=5)

            if results:
                print(f"Found {len(results)} results for '{variation}'")

                # Process each document
                for doc in results:
                    # Check for exact match first
                    if f"Order number: {query}" in doc.page_content:
                        print(f"✓ Found exact match for order {query}")
                        return [doc]  # Return immediately on exact match

                    # Otherwise add to collected results if not seen before
                    content_hash = hash(doc.page_content)
                    if content_hash not in seen:
                        seen.add(content_hash)
                        all_results.append(doc)

        except Exception as e:
            print(f"Error querying with '{variation}': {e}")

    # If we got here, no exact match was found
    if all_results:
        print(f"No exact match found. Returning top {k} most similar documents.")
        return all_results[:k]

    print("No results found for any query variation.")
    return []


if __name__ == "__main__":
    # Example manual test with diagnostics
    test_order = "9345018724"
    print(f"==== TESTING RETRIEVAL FOR ORDER {test_order} ====")
    results = query_order_info(test_order)

    print(f"\nResults for order {test_order}:")
    for i, doc in enumerate(results):
        print(f"\n--- Result {i+1} ---")
        print(doc.page_content)

        # Check if it's an exact match
        if f"Order number: {test_order}" in doc.page_content:
            print("✓ EXACT MATCH - Contains the requested order number")
        else:
            print("✗ NOT EXACT - Does not contain the requested order number")
            # Extract order number if present
            match = re.search(r"Order number: (\d+)", doc.page_content)
            if match:
                found_order = match.group(1)
                print(f"  Found order number: {found_order} instead")

    # 1. Load your document(s)
    document_text = "Order number: 1234\nProduct: Widget\nDetails: ..."

    # 2. Split into chunks
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=300,  # Adjust as needed
        chunk_overlap=50,  # Overlap to preserve context
    )
    chunks = splitter.split_text(document_text)

    # 3. Embed and add to vectorstore
    embeddings = OpenAIEmbeddings()
    vectorstore = FAISS.from_texts(chunks, embeddings)
    vectorstore.save_local("rag/vectorstore")
