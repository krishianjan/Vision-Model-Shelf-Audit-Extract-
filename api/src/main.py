from contextlib import asynccontextmanager
import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

load_dotenv()

from src.persistence.db import create_pool, close_pool
from src.persistence.storage import StorageClient
from src.perception.guardrail import Guardrail
from src.perception.detection import BottleDetector
from src.grounding.matcher import SKUMatcher
from src.grounding.judge import Judge
from src.perception.vlm import VLMOrchestrator
from src.agent.graph import ShelfAuditAgent
from src.routes import audits, accounts, review, crm, chat, auth_routes, dashboard

@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.db = await create_pool(os.environ["DATABASE_URL"])
    app.state.storage = StorageClient()

    # CLIP guardrail — ~400MB, ~2s startup
    app.state.guardrail = Guardrail()

    # Optional YOLO detector for cost optimization (can be disabled)
    if os.environ.get("YOLO_ENABLED", "1") == "1":
        try:
            model_size = os.environ.get("YOLO_MODEL_SIZE", "n")
            app.state.detector = BottleDetector(model_size=model_size)
            print(f"[INFO] YOLO detector loaded (size={model_size})")
        except ImportError:
            print("[WARN] YOLO not available; set YOLO_ENABLED=0 to skip")
            app.state.detector = None
    else:
        app.state.detector = None
        print("[INFO] YOLO detection disabled (YOLO_ENABLED=0)")

    # SKU matcher (without embedder for now — using simple text matching)
    matcher = SKUMatcher()
    app.state.matcher = matcher
    print("[INFO] SKU matcher initialized (text-based matching)")

    # VLM orchestrator and judge
    vlm = VLMOrchestrator()
    judge = Judge()

    # LangGraph agent — wires all components together
    app.state.agent = ShelfAuditAgent(
        db_pool=app.state.db,
        storage=app.state.storage,
        guardrail=app.state.guardrail,
        matcher=matcher,
        vlm=vlm,
        judge=judge,
    )

    yield
    await close_pool(app.state.db)


app = FastAPI(title="Kosha Shelf Audit API", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://valid-subgroup-sturdy.ngrok-free.dev",
        "http://localhost:3000",
        "http://localhost:8081",
        "http://localhost:5173",
        "https://kosha-shelf-audit.vercel.app",
    ],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)

app.include_router(auth_routes.router)
app.include_router(audits.router)
app.include_router(accounts.router)
app.include_router(review.router)
app.include_router(crm.router)
app.include_router(chat.router)
app.include_router(dashboard.router)

# Serve local uploads when USE_LOCAL_STORAGE=1
if os.environ.get("USE_LOCAL_STORAGE") == "1":
    from fastapi.staticfiles import StaticFiles
    from pathlib import Path
    upload_dir = Path(os.environ.get("LOCAL_UPLOAD_DIR", "uploads")).resolve()
    upload_dir.mkdir(parents=True, exist_ok=True)
    app.mount("/uploads", StaticFiles(directory=str(upload_dir)), name="uploads")


@app.get("/health")
async def health():
    return {"status": "ok"}
