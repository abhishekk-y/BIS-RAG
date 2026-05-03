"""
BIS-RAG Pro — Phase 2.5: FastAPI Backend (server.py)
=====================================================
Raw FastAPI backend with async endpoints for the Next.js frontend.
Exposes the RAG pipeline via REST API.
"""

import asyncio
import os
import sys
import time
from contextlib import asynccontextmanager

# Load .env file for GROQ_API_KEY
try:
    from dotenv import load_dotenv
    load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))
except ImportError:
    pass  # python-dotenv not installed, use system env vars

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


# ============================================================
# PYDANTIC MODELS (Strict JSON enforcement)
# ============================================================

class QueryRequest(BaseModel):
    query: str = Field(..., description="Product description or compliance query")
    is_plain_english: bool = Field(default=False, description="Simplify LLM output for MSME owners")


class StandardResult(BaseModel):
    code: str = Field(..., description="IS standard code, e.g. 'IS 269: 1989'")
    title: str = Field(default="", description="Standard title")
    rationale: str = Field(default="", description="Brief explanation of relevance")
    evidence_snippet: str = Field(default="", description="Exact text snippet from PDF used as evidence")
    page_number: int = Field(default=0, description="Page number in the PDF")
    confidence_score: int = Field(default=95, description="Dynamic confidence score derived from cross-encoder")


class QueryResponse(BaseModel):
    id: str = Field(default="", description="Query ID")
    query: str = Field(..., description="Original query text")
    answer: str = Field(default="", description="Natural language LLM answer")
    standards: list[StandardResult] = Field(default_factory=list)
    latency_seconds: float = Field(..., description="Pipeline execution time")


class HealthResponse(BaseModel):
    status: str
    chroma_chunks: int = 0
    bm25_chunks: int = 0
    parent_standards: int = 0


# ============================================================
# APP LIFESPAN (Warm up models on startup)
# ============================================================

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Allow server to start instantly; models will lazy-load on first request."""
    print("[SERVER] Starting instantly (lazy-loading enabled)...")
    # Warmup disabled for Render Free Tier to avoid startup timeout
    # from pipeline import _get_chroma_collection, _get_bm25_data, _get_cross_encoder, _get_parent_index
    # _get_chroma_collection()
    # _get_bm25_data()
    # _get_cross_encoder()
    # _get_parent_index()
    yield
    print("[SERVER] Shutting down...")


# ============================================================
# FASTAPI APP
# ============================================================

app = FastAPI(
    title="BIS-RAG Pro",
    description="AI-Powered BIS Standard Recommendation Engine",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS for Next.js frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:3001", "*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ============================================================
# ENDPOINTS
# ============================================================

@app.get("/api/health", response_model=HealthResponse)
async def health_check():
    """Check system health and loaded indices."""
    try:
        from pipeline import _get_chroma_collection, _get_bm25_data, _get_parent_index
        
        chroma = _get_chroma_collection()
        bm25_data = _get_bm25_data()
        parent = _get_parent_index()
        
        return HealthResponse(
            status="healthy",
            chroma_chunks=chroma.count(),
            bm25_chunks=len(bm25_data["children"]),
            parent_standards=len(parent),
        )
    except Exception as e:
        return HealthResponse(status=f"degraded: {str(e)}")


@app.post("/api/search", response_model=QueryResponse)
async def search_standards(request: QueryRequest):
    """
    Main search endpoint. Runs the full hybrid RAG pipeline.
    Returns recommended standards with evidence snippets.
    """
    try:
        from pipeline import search, _get_parent_index
        
        result = await search(request.query, request.is_plain_english)
        parent_index = _get_parent_index()
        
        from pipeline import enforce_bis_format

        # Build rich response with evidence
        standards = []
        for chunk in result.get("chunks", []):
            raw_code = chunk["metadata"]["parent_is_code"]
            title = chunk["metadata"].get("parent_title", "")
            
            # Normalize the code to match what pipeline.py returns
            norm_res = enforce_bis_format([raw_code])
            code = norm_res[0] if norm_res else raw_code
            
            # Check if this code is in the validated standards list
            if code in result["standards"] or raw_code in result["standards"]:
                # Get evidence snippet (first 300 chars of chunk text)
                evidence = chunk["text"][:300].strip()
                
                # Calculate dynamic score from cross-encoder output
                ce_score = chunk.get("cross_encoder_score", 0)
                # Normalize CE score to a 85-99 percentage range for presentation
                score = min(99, max(85, int(85 + (ce_score * 2))))
                
                standards.append(StandardResult(
                    code=code,
                    title=title,
                    rationale=f"Matched via hybrid retrieval (dense + sparse + cross-encoder reranking)",
                    evidence_snippet=evidence,
                    page_number=chunk["metadata"].get("page_start", 0),
                    confidence_score=score,
                ))
        
        # Add any standards from LLM that aren't in chunks
        seen_codes = {s.code for s in standards}
        
        # Create a normalized lookup map for parent_index
        normalized_parent_index = {}
        for k, v in parent_index.items():
            norm_k_res = enforce_bis_format([k])
            norm_k = norm_k_res[0] if norm_k_res else k
            normalized_parent_index[norm_k] = v

        for code in result["standards"]:
            if code not in seen_codes:
                parent_data = normalized_parent_index.get(code, {})
                standards.append(StandardResult(
                    code=code,
                    title=parent_data.get("title", ""),
                    rationale="Recommended by LLM based on context analysis",
                    evidence_snippet=parent_data.get("full_text", "")[:300],
                    page_number=parent_data.get("page_start", 0),
                    confidence_score=85,
                ))
        
        # Build a natural language answer from the LLM
        answer = result.get("answer", "")
        if not answer and standards:
            codes = [s.code for s in standards[:5]]
            answer = (
                f"Based on your query about \"{request.query}\", "
                f"I found {len(codes)} relevant BIS standards: {', '.join(codes)}. "
                f"These standards cover the specifications, testing methods, and compliance "
                f"requirements applicable to your product. Click any citation below to "
                f"examine the full forensic audit trail and extracted evidence from the PDF."
            )
        
        return QueryResponse(
            query=request.query,
            answer=answer,
            standards=standards[:5],
            latency_seconds=result["latency"],
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/standards")
async def list_all_standards():
    """List all available IS standards in the knowledge base."""
    try:
        from pipeline import _get_parent_index
        parent_index = _get_parent_index()
        
        standards = []
        for code, data in parent_index.items():
            standards.append({
                "code": code,
                "title": data.get("title", ""),
                "page_start": data.get("page_start", 0),
            })
        
        return {"total": len(standards), "standards": standards}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# ============================================================
# FRONTEND STATIC FILES (Single Unit Deployment)
# ============================================================

# Mount static files
frontend_dist = os.path.join(os.path.dirname(os.path.abspath(__file__)), "frontend", "dist")

if os.path.exists(frontend_dist):
    # Mount assets directory separately so they don't get caught by the catch-all
    app.mount("/assets", StaticFiles(directory=os.path.join(frontend_dist, "assets")), name="assets")
    
    @app.get("/{full_path:path}")
    async def serve_frontend(full_path: str):
        # Serve index.html for all other routes to support client-side routing
        index_path = os.path.join(frontend_dist, "index.html")
        if os.path.exists(index_path):
            return FileResponse(index_path)
        return {"error": "Frontend not built properly."}
else:
    print("[SERVER WARNING] Frontend dist folder not found. API only mode.")


# ============================================================
# RUN SERVER
# ============================================================

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "server:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info",
    )
