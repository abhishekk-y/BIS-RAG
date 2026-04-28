"""
BIS-RAG Pro — Phase 1: Offline Ingestion Engine (ingest.py)
============================================================
Parses the 929-page BIS SP 21 PDF into a search-ready knowledge base.

Strategy:
  1. Extract full text via PyMuPDF.
  2. Split into individual standard summaries using regex on "SUMMARY OF IS XXX".
  3. Parent = full standard text. Child = 150-word overlapping chunks.
  4. Dual-index children into ChromaDB (Dense) + BM25 (Sparse).
"""

import fitz  # PyMuPDF
import re
import json
import pickle
import os
import time
import sys

# ============================================================
# 1. PDF TEXT EXTRACTION
# ============================================================

def extract_full_text(pdf_path: str) -> str:
    """Extract all text from the PDF, page by page."""
    doc = fitz.open(pdf_path)
    full_text = ""
    for i, page in enumerate(doc):
        text = page.get_text()
        full_text += f"\n[PAGE {i+1}]\n{text}"
    doc.close()
    print(f"[EXTRACT] Extracted text from {i+1} pages ({len(full_text):,} characters)")
    return full_text


# ============================================================
# 2. STANDARD EXTRACTION (Parent Documents)
# ============================================================

def extract_standards(full_text: str) -> list[dict]:
    """
    Split the full PDF text into individual IS standard summaries.
    
    The PDF uses the pattern:
        SUMMARY OF
        IS XXX : YYYY  TITLE TEXT
    or  SUMMARY OF
        IS XXX (Part N) : YYYY  TITLE TEXT
    
    We use regex to find all such occurrences and split the text.
    """
    # Pattern to find "SUMMARY OF\n IS XXXX..." blocks
    # Some have extra spaces, some have "SUMMARY OF\n" then IS on next line
    summary_pattern = re.compile(
        r'SUMMARY\s+OF\s*\n\s*IS\s+'
        r'(\d+(?:\s*\(Part\s*\d+\))?)\s*'  # IS code with optional Part
        r'[:\-]\s*'                          # colon or dash separator
        r'(\d{4})\s+'                        # year
        r'([A-Z][^\n]*(?:\n[A-Z][^\n]*)*)',  # title (may span multiple lines of caps)
        re.IGNORECASE
    )
    
    # Find all matches with their positions
    matches = list(summary_pattern.finditer(full_text))
    print(f"[EXTRACT] Found {len(matches)} standard summaries via regex")
    
    standards = []
    for i, match in enumerate(matches):
        # Determine the text boundary: from this match to the next match (or end)
        start = match.start()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(full_text)
        
        # Extract the raw code parts
        code_raw = match.group(1).strip()
        year = match.group(2).strip()
        title_raw = match.group(3).strip()
        
        # Normalize the IS code format: "IS XXX : YYYY" or "IS XXX (Part N) : YYYY"
        code_raw = re.sub(r'\s*\(\s*Part\s*(\d+)\s*\)', r' (Part \1)', code_raw, flags=re.IGNORECASE)
        is_code = f"IS {code_raw} : {year}"
        
        # Clean the title
        title = re.sub(r'\s+', ' ', title_raw).strip()
        
        # Extract the full body text for this standard
        body = full_text[start:end].strip()
        
        # Remove the page markers for cleaner text
        body = re.sub(r'\[PAGE \d+\]', '', body)
        body = re.sub(r'SP\s+21\s*:\s*2005', '', body)
        body = re.sub(r'\d+\.\d+\s*$', '', body, flags=re.MULTILINE)  # Remove page numbers like "1.5"
        
        # Clean excessive whitespace
        body = re.sub(r'\n{3,}', '\n\n', body)
        body = re.sub(r' {2,}', ' ', body)
        body = body.strip()
        
        standards.append({
            "is_code": is_code,
            "title": title,
            "full_text": body,
            "page_start": _find_page_number(full_text, start),
        })
    
    return standards


def _find_page_number(full_text: str, position: int) -> int:
    """Find the page number for a given character position."""
    text_before = full_text[:position]
    page_markers = re.findall(r'\[PAGE (\d+)\]', text_before)
    return int(page_markers[-1]) if page_markers else 1


# ============================================================
# 3. CHILD CHUNKING (150-word overlapping chunks)
# ============================================================

def create_child_chunks(standards: list[dict], max_words: int = 150, overlap_words: int = 30) -> list[dict]:
    """
    Split each parent standard into overlapping child chunks.
    Each child gets contextual prepending with the IS code.
    """
    children = []
    child_id = 0
    
    for parent in standards:
        words = parent["full_text"].split()
        is_code = parent["is_code"]
        title = parent["title"]
        
        if len(words) <= max_words:
            # Small enough to be a single chunk
            chunk_text = f"This text belongs to {is_code} — {title}. {parent['full_text']}"
            children.append({
                "child_id": f"chunk_{child_id:05d}",
                "parent_is_code": is_code,
                "parent_title": title,
                "text": chunk_text,
                "page_start": parent["page_start"],
            })
            child_id += 1
        else:
            # Split into overlapping chunks
            step = max_words - overlap_words
            for start_idx in range(0, len(words), step):
                chunk_words = words[start_idx:start_idx + max_words]
                if len(chunk_words) < 30:  # Skip tiny trailing chunks
                    break
                chunk_body = " ".join(chunk_words)
                chunk_text = f"This text belongs to {is_code} — {title}. {chunk_body}"
                children.append({
                    "child_id": f"chunk_{child_id:05d}",
                    "parent_is_code": is_code,
                    "parent_title": title,
                    "text": chunk_text,
                    "page_start": parent["page_start"],
                })
                child_id += 1
    
    print(f"[CHUNK] Created {len(children)} child chunks from {len(standards)} parent standards")
    return children


# ============================================================
# 4. BUILD CHROMADB INDEX (Dense Vectors via BGE-M3)
# ============================================================

def build_chromadb_index(children: list[dict], collection_name: str = "bis_standards"):
    """
    Embed child chunks and store in ChromaDB using BAAI/bge-m3.
    """
    import chromadb
    from chromadb.utils import embedding_functions
    
    # Use the sentence-transformer embedding function built into ChromaDB
    # This wraps BAAI/bge-m3 as the embedding model
    print("[CHROMA] Loading BAAI/bge-m3 embedding model (this may take a minute on first run)...")
    ef = embedding_functions.SentenceTransformerEmbeddingFunction(
        model_name="BAAI/bge-m3",
        device="cpu"  # Use GPU if available: "cuda"
    )
    
    # Create persistent ChromaDB client
    db_path = os.path.join(os.path.dirname(__file__), "chroma_db")
    client = chromadb.PersistentClient(path=db_path)
    
    # Delete existing collection if it exists (for clean re-ingestion)
    try:
        client.delete_collection(name=collection_name)
    except Exception:
        pass
    
    collection = client.get_or_create_collection(
        name=collection_name,
        embedding_function=ef,
        metadata={"hnsw:space": "cosine"}  # Use cosine similarity
    )
    
    # Add documents in batches (ChromaDB has a batch limit)
    batch_size = 100
    total = len(children)
    for i in range(0, total, batch_size):
        batch = children[i:i + batch_size]
        collection.add(
            ids=[c["child_id"] for c in batch],
            documents=[c["text"] for c in batch],
            metadatas=[{
                "parent_is_code": c["parent_is_code"],
                "parent_title": c["parent_title"],
                "page_start": c["page_start"],
            } for c in batch],
        )
        print(f"[CHROMA] Indexed batch {i // batch_size + 1}/{(total + batch_size - 1) // batch_size}")
    
    print(f"[CHROMA] Successfully indexed {total} chunks into ChromaDB at {db_path}")
    return collection


# ============================================================
# 5. BUILD BM25 INDEX (Sparse Keywords)
# ============================================================

def build_bm25_index(children: list[dict]):
    """
    Build a BM25 sparse index over all child chunk texts.
    Saved as a pickle for fast loading during inference.
    """
    from rank_bm25 import BM25Okapi
    
    # Tokenize each document (simple whitespace + lowercase)
    tokenized_corpus = [_tokenize(c["text"]) for c in children]
    
    bm25 = BM25Okapi(tokenized_corpus)
    
    # Save BM25 index and the mapping
    bm25_path = os.path.join(os.path.dirname(__file__), "bm25_index.pkl")
    with open(bm25_path, "wb") as f:
        pickle.dump({
            "bm25": bm25,
            "children": children,  # Store children alongside for retrieval
            "tokenized_corpus": tokenized_corpus,
        }, f)
    
    print(f"[BM25] Successfully built BM25 index over {len(children)} chunks -> {bm25_path}")
    return bm25


def _tokenize(text: str) -> list[str]:
    """Simple tokenizer: lowercase, split on non-alphanumeric, remove stopwords."""
    text = text.lower()
    tokens = re.findall(r'[a-z0-9]+', text)
    # Keep IS codes and numbers intact - don't filter them as stopwords
    stopwords = {
        'the', 'a', 'an', 'is', 'are', 'was', 'were', 'be', 'been', 'being',
        'have', 'has', 'had', 'do', 'does', 'did', 'will', 'would', 'could',
        'should', 'may', 'might', 'shall', 'can', 'of', 'in', 'to', 'for',
        'with', 'on', 'at', 'by', 'from', 'as', 'into', 'through', 'during',
        'before', 'after', 'above', 'below', 'and', 'but', 'or', 'nor', 'not',
        'so', 'yet', 'both', 'either', 'neither', 'each', 'every', 'all',
        'any', 'few', 'more', 'most', 'other', 'some', 'such', 'no', 'only',
        'own', 'same', 'than', 'too', 'very', 'this', 'that', 'these', 'those',
        'it', 'its', 'he', 'she', 'they', 'them', 'their', 'we', 'us', 'our',
    }
    # Don't filter 'is' when it's part of "IS" (Indian Standard) - check context
    return [t for t in tokens if t not in stopwords or t == 'is']


# ============================================================
# 6. SAVE PARENT INDEX (for LLM context retrieval)
# ============================================================

def save_parent_index(standards: list[dict]):
    """
    Save the full parent standard texts as a JSON lookup.
    During retrieval, we look up the parent by IS code to send full context to the LLM.
    """
    parent_index = {}
    for std in standards:
        parent_index[std["is_code"]] = {
            "title": std["title"],
            "full_text": std["full_text"],
            "page_start": std["page_start"],
        }
    
    parent_path = os.path.join(os.path.dirname(__file__), "parent_index.json")
    with open(parent_path, "w", encoding="utf-8") as f:
        json.dump(parent_index, f, indent=2, ensure_ascii=False)
    
    print(f"[PARENT] Saved {len(parent_index)} parent standards to {parent_path}")
    return parent_index


# ============================================================
# MAIN INGESTION PIPELINE
# ============================================================

def main():
    t_start = time.time()
    
    pdf_path = os.path.join(os.path.dirname(__file__), "Assets", "dataset.pdf")
    if not os.path.exists(pdf_path):
        print(f"[ERROR] PDF not found at {pdf_path}")
        sys.exit(1)
    
    print("=" * 60)
    print("BIS-RAG Pro — Ingestion Engine")
    print("=" * 60)
    
    # Step 1: Extract raw text
    print("\n[STEP 1/5] Extracting text from PDF...")
    full_text = extract_full_text(pdf_path)
    
    # Step 2: Parse into individual standards
    print("\n[STEP 2/5] Extracting individual IS standards...")
    standards = extract_standards(full_text)
    
    if not standards:
        print("[ERROR] No standards found! Check regex pattern.")
        sys.exit(1)
    
    # Print first 5 for verification
    print(f"\n[VERIFY] First 5 extracted standards:")
    for s in standards[:5]:
        print(f"  • {s['is_code']} — {s['title'][:60]}... (page {s['page_start']}, {len(s['full_text'])} chars)")
    
    # Step 3: Create child chunks
    print("\n[STEP 3/5] Creating child chunks (150-word, 30-word overlap)...")
    children = create_child_chunks(standards, max_words=150, overlap_words=30)
    
    # Step 4: Build ChromaDB index
    print("\n[STEP 4/5] Building ChromaDB dense index (BAAI/bge-m3)...")
    build_chromadb_index(children)
    
    # Step 5: Build BM25 index
    print("\n[STEP 5/5] Building BM25 sparse index...")
    build_bm25_index(children)
    
    # Save parent index
    print("\n[BONUS] Saving parent index for LLM context...")
    save_parent_index(standards)
    
    elapsed = round(time.time() - t_start, 1)
    print(f"\n{'=' * 60}")
    print(f"INGESTION COMPLETE in {elapsed}s")
    print(f"  Standards extracted: {len(standards)}")
    print(f"  Child chunks created: {len(children)}")
    print(f"  ChromaDB path: ./chroma_db/")
    print(f"  BM25 path: ./bm25_index.pkl")
    print(f"  Parent index: ./parent_index.json")
    print(f"{'=' * 60}")


if __name__ == "__main__":
    main()
