"""
MODULE: Main Application Entry Point
PURPOSE: Compose FastAPI app, wire routers, and bind lifecycle hooks.
DOES: Keep top-level framework wiring explicit and easy to follow.
DOES NOT: Contain domain logic or business workflows.
INVARIANTS: Existing public routes and startup behavior remain stable.
SAFE CHANGE: Add wiring-only changes; move logic into src layers first.
"""

import logging
import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from src.adapters.api.router_registry import register_api_routers
from src.adapters.api.status_routes import router as status_router
from src.infra.lifecycle import run_shutdown_sequence, run_startup_sequence

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="Aiworkfor.me API",
    description="Backend API for the Aiworkfor.me AI Chatbot System.",
    version="0.1.0-refactored",
)

register_api_routers(app)
app.include_router(status_router)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
async def on_startup() -> None:
    await run_startup_sequence()


@app.on_event("shutdown")
async def on_shutdown() -> None:
    await run_shutdown_sequence()


FRONTEND_DIR = os.path.join(os.path.dirname(__file__), "frontend-dist")
INDEX_PATH = os.path.join(FRONTEND_DIR, "index.html")

if os.path.isdir(FRONTEND_DIR):
    assets_dir = os.path.join(FRONTEND_DIR, "assets")
    if os.path.isdir(assets_dir):
        app.mount("/assets", StaticFiles(directory=assets_dir), name="frontend-assets")


@app.get("/", include_in_schema=False)
def serve_frontend_index():
    if os.path.isfile(INDEX_PATH):
        return FileResponse(INDEX_PATH)
    return {"status": "Z.ai Backend API is running (frontend not built)"}


@app.get("/{full_path:path}", include_in_schema=False)
def serve_frontend_spa(full_path: str):
    if full_path.startswith("api/"):
        from fastapi import HTTPException

        raise HTTPException(status_code=404, detail="Not found")
    if os.path.isfile(INDEX_PATH):
        return FileResponse(INDEX_PATH)
    from fastapi import HTTPException

    raise HTTPException(status_code=404, detail="Not found")


if __name__ == "__main__":
    import uvicorn

    port = int(os.getenv("PORT", 8080))
    uvicorn.run(app, host="0.0.0.0", port=port)
