import os
import re
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_community.embeddings import OpenAIEmbeddings
from langchain_community.vectorstores import FAISS
from dotenv import load_dotenv

# Load environment variables (for OpenAI API key)
load_dotenv()

ORDER_DIR = "order_information"
VECTORSTORE_DIR = "rag/vectorstore"


def load_markdown_files(order_dir):
    """Read all .md files and return a list of (filename, content) tuples."""
    docs = []
    for fname in os.listdir(order_dir):
        if fname.endswith(".md"):
            with open(os.path.join(order_dir, fname), "r", encoding="utf-8") as f:
                docs.append((fname, f.read()))
    return docs


def split_by_order(text):
    return [
        chunk.strip() for chunk in re.split(r"(?=Order number:)", text) if chunk.strip()
    ]


def main():
    # 1. Load all order .md files
    docs = load_markdown_files(ORDER_DIR)

    # 2. Split each document into chunks for better retrieval granularity
    #    Here we use RecursiveCharacterTextSplitter from LangChain.
    #    This splits text into ~500 character chunks with 50 character overlap.
    text_splitter = RecursiveCharacterTextSplitter(chunk_size=100, chunk_overlap=50)

    all_chunks = []
    metadatas = []
    for fname, content in docs:
        chunks = split_by_order(content)
        all_chunks.extend(chunks)
        for chunk in chunks:
            match = re.search(r"Order number: (\d+)", chunk)
            order_number = match.group(1) if match else None
            metadatas.append({"source": fname, "order_number": order_number})

    # 3. Generate embeddings for each chunk using OpenAI
    embeddings = OpenAIEmbeddings()

    # 4. Create FAISS vectorstore and persist it to disk
    #    This allows fast similarity search over the order data.
    vectorstore = FAISS.from_texts(all_chunks, embeddings, metadatas=metadatas)
    vectorstore.save_local(VECTORSTORE_DIR)

    print(f"Stored {len(all_chunks)} chunks in FAISS vectorstore at {VECTORSTORE_DIR}")


if __name__ == "__main__":
    main()
