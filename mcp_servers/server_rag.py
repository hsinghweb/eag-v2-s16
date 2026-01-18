from mcp.server.fastmcp import FastMCP, Image
from mcp.server.fastmcp.prompts import base
from mcp.types import TextContent
from mcp import types
from PIL import Image as PILImage
import math
import sys
import os
import json
import faiss
import numpy as np
from pathlib import Path
import requests
from markitdown import MarkItDown
import time
from models import AddInput, AddOutput, SqrtInput, SqrtOutput, StringsToIntsInput, StringsToIntsOutput, ExpSumInput, ExpSumOutput, PythonCodeInput, PythonCodeOutput, UrlInput, FilePathInput, MarkdownInput, MarkdownOutput, ChunkListOutput, SearchDocumentsInput
from tqdm import tqdm
import hashlib
from pydantic import BaseModel
import subprocess
import sqlite3
import trafilatura
import pymupdf4llm
import re
import base64 # ollama needs base64-encoded-image
import asyncio



mcp = FastMCP("Local Storage RAG")

EMBED_URL = "http://localhost:11434/api/embeddings"
OLLAMA_CHAT_URL = "http://localhost:11434/api/chat"
OLLAMA_URL = "http://localhost:11434/api/generate"
EMBED_MODEL = "nomic-embed-text"
GEMMA_MODEL = "gemma3:12b"
PHI_MODEL = "phi4:latest"
QWEN_MODEL = "qwen2.5:32b-instruct-q4_0 "
CHUNK_SIZE = 256
CHUNK_OVERLAP = 40
MAX_CHUNK_LENGTH = 512  # characters
TOP_K = 3  # FAISS top-K matches
ROOT = Path(__file__).parent.resolve()


def get_embedding(text: str) -> np.ndarray:
    result = requests.post(EMBED_URL, json={"model": EMBED_MODEL, "prompt": text})
    result.raise_for_status()
    return np.array(result.json()["embedding"], dtype=np.float32)

def chunk_text(text, size=CHUNK_SIZE, overlap=CHUNK_OVERLAP):
    words = text.split()
    for i in range(0, len(words), size - overlap):
        yield " ".join(words[i:i+size])

def mcp_log(level: str, message: str) -> None:
    if level in ["ERROR", "WARN"]:
        sys.stderr.write(f"{level}: {message}\n")
        sys.stderr.flush()

# === CHUNKING ===





def are_related(chunk1: str, chunk2: str, index: int) -> bool:
    prompt = f"""
You are helping to segment a document into topic-based chunks. Unfortunately, the sentences are mixed up.

CHUNK 1: "{chunk1}"
CHUNK 2: "{chunk2}"

Should these two chunks appear in the **same paragraph or flow of writing**?

Even if the subject changes slightly (e.g., One person to another), treat them as related **if they belong to the same broader context or topic** (like cricket, AI, or real estate). 

Also consider cues like continuity words (e.g., "However", "But", "Also") or references that link the sentences.

Answer with:
Yes – if the chunks should appear together in the same paragraph or section  
No – if they are about different topics and should be separated

Just respond in one word (Yes or No), and do not provide any further explanation.
"""
    print(f"\nComparing chunk {index} and {index+1}")
    print(f"  Chunk {index} → {chunk1[:60]}{'...' if len(chunk1) > 60 else ''}")
    print(f"  Chunk {index+1} → {chunk2[:60]}{'...' if len(chunk2) > 60 else ''}")

    result = requests.post(OLLAMA_CHAT_URL, json={
        "model": PHI_MODEL,
        "messages": [{"role": "user", "content": prompt}],
        "stream": False
    })
    result.raise_for_status()
    reply = result.json().get("message", {}).get("content", "").strip().lower()
    print(f"Model reply: {reply}")
    return reply.startswith("yes")



@mcp.tool()
def search_stored_documents_rag(input: SearchDocumentsInput) -> list[str]:
    """Search old stored documents like PDF, DOCX, TXT, etc. to get relevant extracts. """

    ensure_faiss_ready()
    query = input.query
    mcp_log("SEARCH", f"Query: {query}")
    try:
        index = faiss.read_index(str(ROOT / "faiss_index" / "index.bin"))
        metadata = json.loads((ROOT / "faiss_index" / "metadata.json").read_text())
        query_vec = get_embedding(query ).reshape(1, -1)
        D, I = index.search(query_vec, k=5)
        results = []
        for idx in I[0]:
            data = metadata[idx]
            results.append(f"{data['chunk']}\n[Source: {data['doc']}, ID: {data['chunk_id']}]")
        return results
    except Exception as e:
        return [f"ERROR: Failed to search: {str(e)}"]


def caption_image(img_url_or_path: str) -> str:
    mcp_log("CAPTION", f"Attempting to caption image: {img_url_or_path}")

    # Check if input is a URL
    if img_url_or_path.startswith("http://") or img_url_or_path.startswith("https://"):
        try:
            result = requests.get(img_url_or_path)
            if result.status_code != 200:
                raise Exception(f"HTTP {result.status_code}")
            encoded_image = base64.b64encode(result.content).decode("utf-8")
        except Exception as e:
            mcp_log("ERROR", f"Failed to download image from URL: {e}")
            return f"[Image could not be downloaded: {img_url_or_path}]"
    else:
        full_path = Path(__file__).parent / "documents" / img_url_or_path
        full_path = full_path.resolve()

        if not full_path.exists():
            mcp_log("ERROR", f"Image file not found: {full_path}")
            return f"[Image file not found: {img_url_or_path}]"

        with open(full_path, "rb") as img_file:
            encoded_image = base64.b64encode(img_file.read()).decode("utf-8")


    try:
        if img_url_or_path.startswith("http"): # for extract_web_pages
            result = requests.get(img_url_or_path)
            encoded_image = base64.b64encode(result.content).decode("utf-8")
        else:
            with open(full_path, "rb") as img_file:
                encoded_image = base64.b64encode(img_file.read()).decode("utf-8")

        # Set stream=True to get the full generator-style output
        with requests.post(OLLAMA_URL, json={
                "model": GEMMA_MODEL,
                "prompt": "Look only at the attached image. If it's code, output it exactly as text. If it's a visual scene, describe it as you would for an image alt-text. Never generate new code. Return only the contents of the image.",
                "images": [encoded_image],
                "stream": True
            }, stream=True) as result:

            caption_parts = []
            for line in result.iter_lines():
                if not line:
                    continue
                try:
                    data = json.loads(line)
                    caption_parts.append(data.get("response", ""))  # ✅ fixed key
                    if data.get("done", False):
                        break
                except json.JSONDecodeError:
                    continue  # skip malformed lines

            caption = "".join(caption_parts).strip()
            mcp_log("CAPTION", f"Caption generated: {caption}")
            return caption if caption else "[No caption returned]"

    except Exception as e:
        mcp_log("ERROR", f"Failed to caption image {img_url_or_path}: {e}")
        return f"[Image could not be processed: {img_url_or_path}]"





def replace_images_with_captions(markdown: str) -> str:
    def replace(match):
        alt, src = match.group(1), match.group(2)
        try:
            caption = caption_image(src)
            # Attempt to delete only if local and file exists
            if not src.startswith("http"):
                img_path = Path(__file__).parent / "documents" / src
                if img_path.exists():
                    img_path.unlink()
                    mcp_log("INFO", f"Deleted image after captioning: {img_path}")
            return f"**Image:** {caption}"
        except Exception as e:
            mcp_log("WARN", f"Image deletion failed: {e}")
            return f"[Image could not be processed: {src}]"

    return re.sub(r'!\[(.*?)\]\((.*?)\)', replace, markdown)


# @mcp.tool()
# def convert_webpage_url_into_markdown(input: UrlInput) -> MarkdownOutput:
#     """Return clean webpage content without Ads, and clutter. """

#     downloaded = trafilatura.fetch_url(input.url)
#     if not downloaded:
#         return MarkdownOut@mcp.tool()
def convert_pdf_to_markdown(string: str) -> MarkdownOutput:
    """Convert PDF to markdown. """


    if not os.path.exists(string):
        return MarkdownOutput(markdown=f"File not found: {string}")

    ROOT = Path(__file__).parent.resolve()
    global_image_dir = ROOT / "documents" / "images"
    global_image_dir.mkdir(parents=True, exist_ok=True)

    # Actual markdown with relative image paths
    markdown = pymupdf4llm.to_markdown(
        string,
        write_images=True,
        image_path=str(global_image_dir)
    )


    # Re-point image links in the markdown
    markdown = re.sub(
        r'!\[\]\((.*?/images/)([^)]+)\)',
        r'![](images/\2)',
        markdown.replace("\\", "/")
    )

    markdown = replace_images_with_captions(markdown)
    return MarkdownOutput(markdown=markdown)


@mcp.tool()
def caption_images(img_url_or_path: str) -> str:
    caption = caption_image(img_url_or_path)
    return "The contents of this image are: " + caption


def semantic_merge(text: str) -> list[str]:
    """Splits text semantically using LLM: detects second topic and reuses leftover intelligently."""
    WORD_LIMIT = 512
    words = text.split()
    i = 0
    final_chunks = []

    while i < len(words):
        # 1. Take next chunk of words (and prepend leftovers if any)
        chunk_words = words[i:i + WORD_LIMIT]
        chunk_text = " ".join(chunk_words).strip()

        prompt = f"""
You are a markdown document segmenter.

Here is a portion of a markdown document:

---
{chunk_text}
---

If this chunk clearly contains **more than one distinct topic or section**, reply ONLY with the **second part**, starting from the first sentence or heading of the new topic.

If it's only one topic, reply with NOTHING.

Keep markdown formatting intact.
"""

        try:
            result = requests.post(OLLAMA_CHAT_URL, json={
                "model": PHI_MODEL,
                "messages": [{"role": "user", "content": prompt}],
                "stream": False
            })
            reply = result.json().get("message", {}).get("content", "").strip()

            if reply:
                # If LLM returned second part, separate it
                split_point = chunk_text.find(reply)
                if split_point != -1:
                    first_part = chunk_text[:split_point].strip()
                    second_part = reply.strip()

                    final_chunks.append(first_part)

                    # Get remaining words from second_part and re-use them in next batch
                    leftover_words = second_part.split()
                    words = leftover_words + words[i + WORD_LIMIT:]
                    i = 0  # restart loop with leftover + remaining
                    continue
                else:
                    # fallback: if split point not found
                    final_chunks.append(chunk_text)
            else:
                final_chunks.append(chunk_text)

        except Exception as e:
            mcp_log("ERROR", f"Semantic chunking LLM error: {e}")
            final_chunks.append(chunk_text)

        i += WORD_LIMIT

    return final_chunks







import threading
from concurrent.futures import ThreadPoolExecutor, as_completed

# Thread Safety Lock for PyMuPDF
pdf_lock = threading.Lock()

def process_single_file(file, cache_meta):
    """Worker function to process a single file"""
    try:
        # Check cache inside worker (read-only access to cache_meta is safe)
        fhash = hashlib.md5(Path(file).read_bytes()).hexdigest()
        if file.name in cache_meta and cache_meta[file.name] == fhash:
            return None # Skip

        mcp_log("PROC", f"Processing: {file.name}")
        ext = file.suffix.lower()
        markdown = ""

        if ext == ".pdf":
            # 🔒 LOCK REQUIRED for PyMuPDF
            with pdf_lock:
                mcp_log("INFO", f"Using MuPDF4LLM to extract {file.name}")
                markdown = convert_pdf_to_markdown(FilePathInput(file_path=str(file))).markdown

        elif ext in [".html", ".htm", ".url"]:
            mcp_log("INFO", f"Using Trafilatura to extract {file.name}")
            markdown = extract_webpage(UrlInput(url=file.read_text().strip())).markdown

        else:
            # Fallback
            converter = MarkItDown()
            mcp_log("INFO", f"Using MarkItDown fallback for {file.name}")
            markdown = converter.convert(str(file)).text_content

        if not markdown.strip():
            mcp_log("WARN", f"No content extracted from {file.name}")
            return None

        # Semantic Chunking
        if len(markdown.split()) < 10:
             chunks = [markdown.strip()]
        else:
             chunks = semantic_merge(markdown)

        # Embedding (Thread-safe usually)
        embeddings_for_file = []
        new_metadata = []
        
        # Don't use tqdm here to avoid interleaved bars
        for i, chunk in enumerate(chunks):
            embedding = get_embedding(chunk)
            embeddings_for_file.append(embedding)
            new_metadata.append({
                "doc": file.name,
                "chunk": chunk,
                "chunk_id": f"{file.stem}_{i}"
            })

        return {
            "file_name": file.name,
            "fhash": fhash,
            "embeddings": embeddings_for_file,
            "metadata": new_metadata
        }

    except Exception as e:
        mcp_log("ERROR", f"Failed to process {file.name}: {e}")
        return None

def process_documents():
    """Process documents and create FAISS index using unified multimodal strategy."""
    mcp_log("INFO", "Indexing documents with unified RAG pipeline (Parallel)...")
    ROOT = Path(__file__).parent.resolve()
    DOC_PATH = ROOT / "documents"
    INDEX_CACHE = ROOT / "faiss_index"
    INDEX_CACHE.mkdir(exist_ok=True)
    INDEX_FILE = INDEX_CACHE / "index.bin"
    METADATA_FILE = INDEX_CACHE / "metadata.json"
    CACHE_FILE = INDEX_CACHE / "doc_index_cache.json"

    CACHE_META = json.loads(CACHE_FILE.read_text()) if CACHE_FILE.exists() else {}
    metadata = json.loads(METADATA_FILE.read_text()) if METADATA_FILE.exists() else []
    index = faiss.read_index(str(INDEX_FILE)) if INDEX_FILE.exists() else None

    # Collect files
    files = list(DOC_PATH.glob("*.*"))
    
    # Parallel Processing
    with ThreadPoolExecutor(max_workers=2) as executor:
        # Submit all tasks
        future_to_file = {executor.submit(process_single_file, f, CACHE_META): f for f in files}
        
        for future in tqdm(as_completed(future_to_file), total=len(files), desc="Indexing Files"):
            result = future.result()
            if result:
                # Update FAISS (Sequentially in main thread)
                embeddings = result["embeddings"]
                new_meta = result["metadata"]
                
                if embeddings:
                    if index is None:
                        dim = len(embeddings[0])
                        index = faiss.IndexFlatL2(dim)
                    
                    index.add(np.stack(embeddings))
                    metadata.extend(new_meta)
                    CACHE_META[result["file_name"]] = result["fhash"]
                    mcp_log("SAVE", f"Indexed {result['file_name']} ({len(embeddings)} chunks)")

    # Save final state
    if index:
        CACHE_FILE.write_text(json.dumps(CACHE_META, indent=2))
        METADATA_FILE.write_text(json.dumps(metadata, indent=2))
        faiss.write_index(index, str(INDEX_FILE))
        mcp_log("SUCCESS", "FAISS index saved.")
    
    mcp_log("INFO", "READY")



def ensure_faiss_ready():
    from pathlib import Path
    index_path = ROOT / "faiss_index" / "index.bin"
    meta_path = ROOT / "faiss_index" / "metadata.json"
    if not (index_path.exists() and meta_path.exists()):
        mcp_log("INFO", "Index not found — running process_documents()...")
        process_documents()
    else:
        mcp_log("INFO", "Index already exists. Skipping regeneration.")


async def main():
    mcp_log("INFO", "STARTING THE SERVER AT AMAZING LOCATION")

    if len(sys.argv) > 1 and sys.argv[1] == "dev":
        mcp.run()  # Run without transport for dev server
    else:
        # Start the server in a separate thread
        import threading
        server_thread = threading.Thread(target=lambda: mcp.run(transport="stdio"))
        server_thread.daemon = True
        server_thread.start()
        
        # Wait a moment for the server to start
        await asyncio.sleep(2)
        
        # Process documents after server is running
        # process_documents()
        
        # Keep the main thread alive
        try:
            while True:
                await asyncio.sleep(1)
        except KeyboardInterrupt:
            mcp_log("INFO", "\nShutting down...")

if __name__ == "__main__":
    asyncio.run(main())
