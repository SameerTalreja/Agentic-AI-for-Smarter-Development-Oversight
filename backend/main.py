"""
backend/main.py
FastAPI application entrypoint.
"""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from db.database import init_db
from db.seed import seed_default_dataset
from backend.routes import query, audit, review_board, history, datasets

app = FastAPI(
    title="Agentic Infrastructure Analyst API",
    description="Track A/B/C agents over the PMTS Projects dataset.",
    version="0.1.0",
)

# In production, set ALLOWED_ORIGINS to your deployed frontend URL(s),
# comma-separated (e.g. "https://your-app.vercel.app"). Falls back to "*"
# for local development so nothing breaks if it's unset.
_origins_env = os.environ.get("ALLOWED_ORIGINS", "*")
allowed_origins = ["*"] if _origins_env == "*" else [o.strip() for o in _origins_env.split(",")]

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(query.router)
app.include_router(audit.router)
app.include_router(review_board.router)
app.include_router(history.router)
app.include_router(datasets.router)


@app.on_event("startup")
def on_startup() -> None:
    init_db()
    seed_default_dataset()


@app.get("/api/health")
def health() -> dict:
    return {"status": "ok"}