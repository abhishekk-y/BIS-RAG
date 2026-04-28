"""
BIS-RAG Pro — Phase 2: The Latency-Annihilating RAG Pipeline (pipeline.py)
============================================================================
Hybrid retrieval (Dense + Sparse) → RRF fusion → Cross-Encoder reranking → Groq LLM generation.
All retrieval paths run in parallel via asyncio.gather() for sub-second latency.
"""

import asyncio
import json
import os
import pickle
import re
import time
from typing import Optional

import numpy as np


# ============================================================
# GLOBAL SINGLETONS (loaded once, reused across all queries)
# ============================================================

_chroma_collection = None
_bm25_data = None
_cross_encoder = None
_groq_client = None
_parent_index = None

BASE_DIR = os.path.dirname(os.path.abspath(__file__))


def _get_chroma_collection():
    """Lazy-load ChromaDB collection."""
    global _chroma_collection
    if _chroma_collection is None:
        import chromadb
        from chromadb.utils import embedding_functions
        
        ef = embedding_functions.SentenceTransformerEmbeddingFunction(
            model_name="BAAI/bge-m3",
            device="cpu"
        )
        client = chromadb.PersistentClient(path=os.path.join(BASE_DIR, "chroma_db"))
        _chroma_collection = client.get_collection(
            name="bis_standards",
            embedding_function=ef
        )
        print(f"[PIPELINE] ChromaDB loaded: {_chroma_collection.count()} chunks")
    return _chroma_collection


def _get_bm25_data():
    """Lazy-load BM25 index + children mapping."""
    global _bm25_data
    if _bm25_data is None:
        bm25_path = os.path.join(BASE_DIR, "bm25_index.pkl")
        with open(bm25_path, "rb") as f:
            _bm25_data = pickle.load(f)
        print(f"[PIPELINE] BM25 loaded: {len(_bm25_data['children'])} chunks")
    return _bm25_data


def _get_cross_encoder():
    """Lazy-load the Cross-Encoder reranker."""
    global _cross_encoder
    if _cross_encoder is None:
        from sentence_transformers import CrossEncoder
        _cross_encoder = CrossEncoder("cross-encoder/ms-marco-MiniLM-L6-v2")
        print("[PIPELINE] Cross-Encoder loaded: ms-marco-MiniLM-L6-v2")
    return _cross_encoder


def _get_groq_client():
    """Lazy-load Groq API client."""
    global _groq_client
    if _groq_client is None:
        from groq import Groq
        api_key = os.environ.get("GROQ_API_KEY", "")
        if not api_key:
            print("[WARNING] GROQ_API_KEY not set. LLM generation will fail.")
        _groq_client = Groq(api_key=api_key)
        print("[PIPELINE] Groq client initialized")
    return _groq_client


def _get_parent_index():
    """Lazy-load parent index for full standard retrieval."""
    global _parent_index
    if _parent_index is None:
        parent_path = os.path.join(BASE_DIR, "parent_index.json")
        with open(parent_path, "r", encoding="utf-8") as f:
            _parent_index = json.load(f)
        print(f"[PIPELINE] Parent index loaded: {len(_parent_index)} standards")
    return _parent_index


# ============================================================
# TOKENIZER (shared with ingest.py)
# ============================================================

def _tokenize(text: str) -> list[str]:
    """Same tokenizer used during ingestion. Must be identical."""
    text = text.lower()
    tokens = re.findall(r'[a-z0-9]+', text)
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
    return [t for t in tokens if t not in stopwords or t == 'is']


# ============================================================
# RETRIEVAL: Dense (ChromaDB) + Sparse (BM25) in parallel
# ============================================================

async def _dense_search(query: str, top_k: int = 20) -> list[dict]:
    """Query ChromaDB with dense embeddings (BAAI/bge-m3)."""
    collection = _get_chroma_collection()
    
    # Run blocking ChromaDB query in thread pool
    loop = asyncio.get_event_loop()
    results = await loop.run_in_executor(
        None,
        lambda: collection.query(
            query_texts=[query],
            n_results=top_k,
            include=["documents", "metadatas", "distances"]
        )
    )
    
    hits = []
    if results and results["ids"] and results["ids"][0]:
        for i, doc_id in enumerate(results["ids"][0]):
            hits.append({
                "child_id": doc_id,
                "text": results["documents"][0][i],
                "metadata": results["metadatas"][0][i],
                "score": 1 - results["distances"][0][i],  # Convert distance to similarity
                "source": "dense",
            })
    return hits


def _inject_synonyms(query: str) -> str:
    synonyms = {
        "cement": "OPC PPC portland IS 269 IS 455",
        "aggregate": "sand gravel coarse IS 383",
    }
    expanded = query
    for k, v in synonyms.items():
        if k in query.lower():
            expanded += f" {v}"
    return expanded

async def _sparse_search(query: str, top_k: int = 20) -> list[dict]:
    """Query BM25 with sparse keyword matching."""
    bm25_data = _get_bm25_data()
    bm25 = bm25_data["bm25"]
    children = bm25_data["children"]
    
    expanded_query = _inject_synonyms(query)
    tokenized_query = _tokenize(expanded_query)
    
    # Run blocking BM25 scoring in thread pool
    loop = asyncio.get_event_loop()
    scores = await loop.run_in_executor(
        None,
        lambda: bm25.get_scores(tokenized_query)
    )
    
    # Get top-k indices
    top_indices = np.argsort(scores)[::-1][:top_k]
    
    hits = []
    for idx in top_indices:
        if scores[idx] > 0:  # Only include relevant results
            child = children[idx]
            hits.append({
                "child_id": child["child_id"],
                "text": child["text"],
                "metadata": {
                    "parent_is_code": child["parent_is_code"],
                    "parent_title": child["parent_title"],
                    "page_start": child["page_start"],
                },
                "score": float(scores[idx]),
                "source": "sparse",
            })
    return hits


# ============================================================
# RECIPROCAL RANK FUSION (RRF)
# ============================================================

def reciprocal_rank_fusion(
    result_lists: list[list[dict]], 
    k: int = 60, 
    top_n: int = 10
) -> list[dict]:
    """
    Merge multiple ranked lists using RRF.
    
    Score = sum over all lists of: 1 / (k + rank)
    where k = 60 is the standard constant.
    """
    fused_scores = {}  # child_id -> (rrf_score, best_doc_dict)
    
    for results in result_lists:
        for rank, doc in enumerate(results):
            cid = doc["child_id"]
            rrf_score = 1.0 / (k + rank + 1)
            
            if cid in fused_scores:
                fused_scores[cid] = (
                    fused_scores[cid][0] + rrf_score,
                    fused_scores[cid][1]  # Keep the first occurrence's doc data
                )
            else:
                fused_scores[cid] = (rrf_score, doc)
    
    # Sort by fused score descending
    sorted_results = sorted(fused_scores.values(), key=lambda x: x[0], reverse=True)
    
    # Return top_n with the rrf score attached
    top_results = []
    for score, doc in sorted_results[:top_n]:
        doc["rrf_score"] = score
        top_results.append(doc)
    
    return top_results


# ============================================================
# CROSS-ENCODER RERANKING
# ============================================================

def cross_encoder_rerank(query: str, candidates: list[dict], top_k: int = 5) -> list[dict]:
    """
    Use the Cross-Encoder to precisely score each (query, candidate) pair.
    Returns the top_k most relevant candidates.
    """
    if not candidates:
        return []
    
    encoder = _get_cross_encoder()
    
    # Create (query, document) pairs
    pairs = [(query, doc["text"]) for doc in candidates]
    
    # Score all pairs
    scores = encoder.predict(pairs)
    
    # Attach scores and sort
    for i, doc in enumerate(candidates):
        doc["cross_encoder_score"] = float(scores[i])
    
    # Sort by cross-encoder score descending
    candidates.sort(key=lambda x: x["cross_encoder_score"], reverse=True)
    
    return candidates[:top_k]


# ============================================================
# LLM GENERATION (Groq + Llama 3)
# ============================================================

SYSTEM_PROMPT = """You are BIS-RAG Pro, an expert AI assistant specializing in Bureau of Indian Standards (BIS) compliance for building materials. You have deep knowledge of IS standards from BIS SP 21.

When a user asks about a product, material, or compliance question, you must:

1. Structure your "answer" field EXACTLY like this:
   - **Introduction Paragraph**: A single deep-dive paragraph acknowledging the query and summarizing the overarching requirements or materials involved.
   - **Bullet Points**: You MUST leave a blank empty line before starting this list. Then provide a bulleted list detailing each relevant standard. For each bullet point, state the **Standard Code** in bold, explain exactly what it covers, and provide specific technical details extracted from the context.
   - **Concluding Paragraph**: You MUST leave a blank empty line before this paragraph. A final paragraph summarizing compliance steps.

2. ONLY recommend standards that are explicitly mentioned in the provided context
3. Format each standard EXACTLY as: "IS {number} : {year}" or "IS {number} (Part {N}) : {year}"
4. Provide 3-5 standards, ranked by relevance
5. Keep your total answer concise enough to generate in under 3 seconds, but packed with technical data.

Return ONLY a JSON object:
{
  "answer": "Your detailed, formatted answer here...",
  "standards": [
    {"code": "IS XXX: YYYY", "rationale": "Specific reason with technical detail"},
    ...
  ]
}
"""


async def llm_generate(query: str, context_chunks: list[dict], is_plain_english: bool = False) -> dict:
    """
    Send the top reranked context to Groq (Llama 3) for standard recommendation.
    Returns a dict with 'codes' (list of IS code strings) and 'answer' (natural language).
    """
    # Build context from parent texts (retrieve full parent for each unique IS code)
    parent_index = _get_parent_index()
    
    # Collect unique IS codes from top chunks
    seen_codes = set()
    context_parts = []
    for chunk in context_chunks:
        code = chunk["metadata"]["parent_is_code"]
        if code not in seen_codes:
            seen_codes.add(code)
            if code in parent_index:
                parent = parent_index[code]
                # Truncate to ~500 words to stay within context window
                words = parent["full_text"].split()[:500]
                context_parts.append(
                    f"--- {code}: {parent['title']} ---\n{' '.join(words)}"
                )
            else:
                # Fallback to chunk text
                context_parts.append(f"--- {code} ---\n{chunk['text']}")
    
    context_text = "\n\n".join(context_parts)
    
    user_prompt = f"""Product/Query: {query}

Context from BIS SP 21:
{context_text}

Based on the context above, recommend the top 3-5 most relevant IS standards for this product/query.
Return ONLY a valid JSON object with both an "answer" and "standards" array."""

    if is_plain_english:
        user_prompt += "\n\nCRITICAL: Explain these requirements simply to a non-technical small business owner, avoiding overly dense engineering jargon where possible."

    try:
        client = _get_groq_client()
        
        # Run blocking Groq call in thread pool
        loop = asyncio.get_event_loop()
        response = await loop.run_in_executor(
            None,
            lambda: client.chat.completions.create(
                model="llama-3.3-70b-versatile",
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=0.2,
                max_tokens=800,
                response_format={"type": "json_object"},
            )
        )
        
        raw_text = response.choices[0].message.content
        result = json.loads(raw_text)
        
        # Extract IS codes and answer from the LLM response
        standards = []
        if "standards" in result:
            for item in result["standards"]:
                if isinstance(item, dict) and "code" in item:
                    standards.append(item["code"])
                elif isinstance(item, str):
                    standards.append(item)
        
        answer = result.get("answer", "")
        
        return {"codes": standards, "answer": answer}
        
    except Exception as e:
        print(f"[LLM ERROR] {e}")
        # Fallback: extract IS codes directly from the top reranked chunks
        return {"codes": _fallback_extract_codes(context_chunks), "answer": ""}


def _fallback_extract_codes(chunks: list[dict]) -> list[str]:
    """
    Fallback when LLM is unavailable: extract unique IS codes from chunks.
    """
    seen = set()
    codes = []
    for chunk in chunks:
        code = chunk["metadata"]["parent_is_code"]
        if code not in seen:
            seen.add(code)
            codes.append(code)
    return codes[:5]


# ============================================================
# THE REGEX NORMALIZER (from inference.py, shared utility)
# ============================================================

def enforce_bis_format(llm_output_list: list[str]) -> list[str]:
    """
    Formats all standards perfectly as "IS XXX: YYYY" or "IS XXX (Part Y): YYYY".
    Must match the eval script's normalize_std behavior.
    """
    cleaned = []
    pattern = r'IS\s*(\d+(?:\s*\(\s*Part\s*\d+\s*\))?)\s*:\s*(\d{4})'
    
    for std in llm_output_list:
        match = re.search(pattern, std, re.IGNORECASE)
        if match:
            code_part = match.group(1).strip()
            # Normalize "(Part X)" spacing
            code_part = re.sub(r'\s*\(\s*Part\s*(\d+)\s*\)', r' (Part \1)', code_part, flags=re.IGNORECASE)
            cleaned.append(f"IS {code_part} : {match.group(2)}")
    
    # Deduplicate while preserving order
    seen = set()
    result = []
    for s in cleaned:
        if s not in seen:
            seen.add(s)
            result.append(s)
    
    return result


# ============================================================
# AGENTIC VALIDATOR (Zero Hallucination Guarantee)
# ============================================================

def agentic_validator(generated_standards: list[str], retrieved_chunks: list[dict]) -> list[str]:
    """
    Verify each generated IS code exists in the retrieved context.
    Silently drop any hallucinated codes.
    """
    # Build a set of all IS codes mentioned in the retrieved chunks
    valid_codes = set()
    for chunk in retrieved_chunks:
        code = chunk["metadata"]["parent_is_code"]
        valid_codes.add(code)
        # Also extract any IS codes mentioned in the chunk text itself
        pattern = r'IS\s*(\d+(?:\s*\(\s*Part\s*\d+\s*\))?)\s*:\s*(\d{4})'
        for m in re.finditer(pattern, chunk["text"], re.IGNORECASE):
            code_part = m.group(1).strip()
            code_part = re.sub(r'\s*\(\s*Part\s*(\d+)\s*\)', r' (Part \1)', code_part, flags=re.IGNORECASE)
            valid_codes.add(f"IS {code_part} : {m.group(2)}")
    
    validated = []
    for std in generated_standards:
        if std in valid_codes:
            validated.append(std)
    
    return validated


# ============================================================
# MAIN SEARCH PIPELINE (The Full Orchestrator)
# ============================================================

async def _hyde_expand(query: str) -> str:
    """HyDE query expansion to generate a fake standard excerpt."""
    try:
        client = _get_groq_client()
        loop = asyncio.get_event_loop()
        response = await loop.run_in_executor(
            None,
            lambda: client.chat.completions.create(
                model="llama-3.3-70b-versatile",
                messages=[
                    {"role": "user", "content": f"Write a 2-sentence BIS standard excerpt for: {query}"}
                ],
                temperature=0.3,
                max_tokens=100,
            )
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        print(f"[HYDE ERROR] {e}")
        return query


async def search(query: str, is_plain_english: bool = False) -> dict:
    """
    Execute the full RAG pipeline:
    1. HyDE Query Expansion
    2. Dense + Sparse retrieval in parallel
    3. RRF fusion
    4. Cross-Encoder reranking
    5. LLM generation via Groq
    6. Regex normalization + Agentic validation
    
    Returns dict with 'standards', 'chunks', and 'latency'.
    """
    t_start = time.time()
    
    # Step 1: HyDE
    hyde_query = await _hyde_expand(query)
    # We use hyde_query for dense search to get better embedding matches.
    # We pass the original query to sparse_search which has its own synonym injection.
    
    # Step 2: Parallel retrieval
    dense_hits, sparse_hits = await asyncio.gather(
        _dense_search(hyde_query, top_k=20),
        _sparse_search(query, top_k=20),
    )
    
    # Step 2: RRF fusion
    fused = reciprocal_rank_fusion([dense_hits, sparse_hits], k=60, top_n=10)
    
    # Step 3: Cross-Encoder reranking
    reranked = cross_encoder_rerank(query, fused, top_k=5)
    
    # Step 4: LLM generation (now returns dict with 'codes' and 'answer')
    llm_result = await llm_generate(query, reranked, is_plain_english)
    raw_standards = llm_result["codes"]
    llm_answer = llm_result.get("answer", "")
    
    # Step 5: Normalize + Validate
    normalized = enforce_bis_format(raw_standards)
    validated = agentic_validator(normalized, reranked)
    
    # Fallback logic removed intentionally to enforce Agentic Validation strictness (Zero Hallucination)
    
    latency = round(time.time() - t_start, 3)
    
    return {
        "standards": validated,
        "chunks": reranked,  # For the forensic audit trail in the UI
        "answer": llm_answer,
        "latency": latency,
    }


# ============================================================
# SYNC WRAPPER (for inference.py)
# ============================================================

def search_sync(query: str) -> dict:
    """Synchronous wrapper around the async search pipeline."""
    return asyncio.run(search(query))


# ============================================================
# QUICK TEST
# ============================================================

if __name__ == "__main__":
    import sys
    query = sys.argv[1] if len(sys.argv) > 1 else "33 Grade Ordinary Portland Cement"
    print(f"\n[TEST] Query: {query}")
    result = search_sync(query)
    print(f"\n[RESULT] Standards: {result['standards']}")
    print(f"[RESULT] Latency: {result['latency']}s")
    print(f"[RESULT] Top chunks:")
    for c in result["chunks"][:3]:
        print(f"  • {c['metadata']['parent_is_code']}: {c['text'][:100]}...")
