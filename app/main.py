import json
import logging
from pathlib import Path
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException
from fastapi.responses import StreamingResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from app.config import MODEL, DATA_PATH, BASE_DIR
from app.models import ChatRequest
from app.rag import init_chroma_db, load_trees_catalog
from app.agent import stream_agent, run_agent

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("rootsafe.main")

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: Load catalog and warm up ChromaDB
    logger.info("Initializing RootSafe Arborist application...")
    trees = load_trees_catalog()
    logger.info(f"Loaded {len(trees)} trees from catalog.")
    init_chroma_db()
    yield
    logger.info("Shutting down RootSafe Arborist.")

app = FastAPI(
    title="RootSafe Arborist API",
    description="Agentic LLM System for Residential Landscape Tree Selection & Structural Hazard Prevention",
    version="1.0.0",
    lifespan=lifespan
)

@app.get("/api/health")
def health():
    trees = load_trees_catalog()
    return {
        "status": "ok",
        "service": "RootSafe Arborist",
        "model": MODEL,
        "catalog_size": len(trees)
    }

@app.get("/api/trees")
def list_trees():
    """Retrieve catalog for tree explorer UI."""
    return load_trees_catalog()

@app.post("/api/chat")
async def chat_sse(req: ChatRequest):
    """Real-time SSE streaming chat with tool calling events and token streaming."""
    try:
        return StreamingResponse(
            stream_agent(
                user_message=req.message,
                history=req.history,
                temperature=req.temperature,
                min_score=req.min_score
            ),
            media_type="text/event-stream"
        )
    except Exception as e:
        logger.error(f"Chat streaming error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/consult-sync")
def consult_sync(req: ChatRequest):
    """Synchronous JSON endpoint for evaluation and testing."""
    try:
        result = run_agent(
            user_message=req.message,
            history=req.history,
            temperature=req.temperature,
            min_score=req.min_score
        )
        return result
    except Exception as e:
        logger.error(f"Consult sync error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/eval-summary")
def get_eval_summary():
    """Returns evaluation metrics if run_eval.py has been executed."""
    eval_file = BASE_DIR / "eval" / "results" / "summary.json"
    if eval_file.exists():
        with open(eval_file, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"status": "not_run", "message": "Run 'python eval/run_eval.py' to generate benchmark results."}

# Mount static folder for web UI
static_dir = BASE_DIR / "static"
if static_dir.exists():
    app.mount("/", StaticFiles(directory=str(static_dir), html=True), name="static")
